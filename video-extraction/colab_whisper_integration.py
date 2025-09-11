#!/usr/bin/env python3
"""
Google Colab Whisper Integration Script
This runs on your local machine to coordinate with Colab
"""

import sqlite3
import json
import boto3
from pathlib import Path
import requests
import time
from datetime import datetime

class ColabWhisperIntegration:
    def __init__(self, db_path="../library_videos.db"):
        self.db_path = db_path
        self.s3_client = boto3.client('s3')
        self.bucket_name = 'xenodex-video-archive'
        
    def get_videos_needing_transcription(self, limit=10):
        """Get videos that need transcription"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, s3_key, title, streamable_id
            FROM videos 
            WHERE s3_key IS NOT NULL 
            AND (transcription_status IS NULL OR transcription_status = 'pending')
            ORDER BY id
            LIMIT ?
        """, (limit,))
        
        videos = []
        for row in cursor.fetchall():
            videos.append({
                'id': row[0],
                's3_key': row[1],
                'title': row[2],
                'streamable_id': row[3]
            })
        
        conn.close()
        return videos
    
    def generate_presigned_url(self, s3_key, expiration=3600):
        """Generate presigned URL for Colab to access S3 file"""
        try:
            url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket_name, 'Key': s3_key},
                ExpiresIn=expiration
            )
            return url
        except Exception as e:
            print(f"Error generating presigned URL: {e}")
            return None
    
    def update_transcription_status(self, video_id, status, transcript_s3_key=None):
        """Update transcription status in database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if transcript_s3_key:
            cursor.execute("""
                UPDATE videos 
                SET transcription_status = ?, 
                    transcript_s3_key = ?,
                    transcribed_at = ?
                WHERE id = ?
            """, (status, transcript_s3_key, datetime.utcnow().isoformat(), video_id))
        else:
            cursor.execute("""
                UPDATE videos 
                SET transcription_status = ?
                WHERE id = ?
            """, (status, video_id))
        
        conn.commit()
        conn.close()
    
    def save_transcript_to_s3(self, video_id, transcript_text):
        """Save transcript to S3"""
        s3_key = f"transcripts/{video_id}_transcript.txt"
        
        try:
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=transcript_text,
                ContentType='text/plain',
                StorageClass='GLACIER_IR'
            )
            return s3_key
        except Exception as e:
            print(f"Error saving transcript to S3: {e}")
            return None
    
    def prepare_colab_batch(self, batch_size=10):
        """Prepare a batch of videos for Colab processing"""
        videos = self.get_videos_needing_transcription(batch_size)
        
        batch_data = {
            'videos': [],
            'timestamp': datetime.utcnow().isoformat(),
            'total': len(videos)
        }
        
        for video in videos:
            presigned_url = self.generate_presigned_url(video['s3_key'])
            if presigned_url:
                batch_data['videos'].append({
                    'id': video['id'],
                    'title': video['title'],
                    'url': presigned_url,
                    's3_key': video['s3_key']
                })
                # Mark as in-progress
                self.update_transcription_status(video['id'], 'processing')
        
        # Save batch info
        batch_file = f"colab_batch_{int(time.time())}.json"
        with open(batch_file, 'w') as f:
            json.dump(batch_data, f, indent=2)
        
        print(f"✅ Prepared batch of {len(batch_data['videos'])} videos")
        print(f"📄 Batch file: {batch_file}")
        
        return batch_file, batch_data
    
    def process_colab_results(self, results_file):
        """Process results from Colab"""
        with open(results_file, 'r') as f:
            results = json.load(f)
        
        success_count = 0
        for result in results['transcripts']:
            video_id = result['id']
            
            if result['status'] == 'success':
                # Save transcript to S3
                s3_key = self.save_transcript_to_s3(video_id, result['transcript'])
                if s3_key:
                    self.update_transcription_status(video_id, 'completed', s3_key)
                    success_count += 1
                else:
                    self.update_transcription_status(video_id, 'failed')
            else:
                self.update_transcription_status(video_id, 'failed')
        
        print(f"✅ Processed {success_count}/{len(results['transcripts'])} transcripts")

# Create the Colab notebook content
COLAB_NOTEBOOK = '''
# Create this as a new notebook in Google Colab Pro

# Cell 1: Setup
!pip install openai-whisper boto3

# Cell 2: Import and Initialize
import whisper
import requests
import json
from google.colab import files
import os
import time

# Load Whisper model (base model is good balance of speed/accuracy)
print("Loading Whisper model...")
model = whisper.load_model("base")
print("✅ Model loaded!")

# Cell 3: Download batch file from your local machine
print("Upload your batch JSON file:")
uploaded = files.upload()
batch_file = list(uploaded.keys())[0]

with open(batch_file, 'r') as f:
    batch_data = json.load(f)

print(f"📊 Loaded batch with {len(batch_data['videos'])} videos")

# Cell 4: Process videos
results = {
    'batch_file': batch_file,
    'start_time': time.time(),
    'transcripts': []
}

for i, video in enumerate(batch_data['videos']):
    print(f"\\n[{i+1}/{len(batch_data['videos'])}] Processing: {video['title'][:50]}...")
    
    try:
        # Download audio from presigned URL
        audio_file = f"temp_{video['id']}.mp3"
        response = requests.get(video['url'], stream=True)
        with open(audio_file, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        # Transcribe with Whisper
        result = model.transcribe(audio_file, language='en')
        
        results['transcripts'].append({
            'id': video['id'],
            'title': video['title'],
            'transcript': result['text'],
            'status': 'success'
        })
        
        # Clean up
        os.remove(audio_file)
        print(f"✅ Completed: {len(result['text'])} characters")
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        results['transcripts'].append({
            'id': video['id'],
            'title': video['title'],
            'error': str(e),
            'status': 'failed'
        })

results['end_time'] = time.time()
results['duration'] = results['end_time'] - results['start_time']

# Cell 5: Save and download results
results_file = f"results_{batch_file}"
with open(results_file, 'w') as f:
    json.dump(results, f, indent=2)

print(f"\\n✅ Completed {len(results['transcripts'])} videos in {results['duration']:.1f} seconds")
print(f"📥 Downloading results...")
files.download(results_file)
'''

def main():
    print("🚀 Google Colab Whisper Integration")
    print("=" * 60)
    
    # Save the Colab notebook
    notebook_path = "whisper_colab_notebook.txt"
    with open(notebook_path, 'w') as f:
        f.write(COLAB_NOTEBOOK)
    
    print("📝 Instructions:")
    print("1. Sign up for Google Colab Pro ($10/month)")
    print("2. Create a new notebook and paste the code from whisper_colab_notebook.txt")
    print("3. Run this script to prepare batches")
    print("4. Upload batch file to Colab")
    print("5. Run Colab notebook")
    print("6. Download results and run process_results command")
    
    print("\n📊 Commands:")
    print("python3 colab_whisper_integration.py prepare    # Create batch")
    print("python3 colab_whisper_integration.py process <results.json>  # Process results")
    
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        main()
    else:
        integration = ColabWhisperIntegration()
        
        if sys.argv[1] == "prepare":
            batch_size = int(sys.argv[2]) if len(sys.argv) > 2 else 10
            integration.prepare_colab_batch(batch_size)
            
        elif sys.argv[1] == "process" and len(sys.argv) > 2:
            integration.process_colab_results(sys.argv[2])
        else:
            main()