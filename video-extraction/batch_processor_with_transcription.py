#!/usr/bin/env python3
"""
Enhanced batch processor that includes transcription after S3 upload
"""
import sys
import os
import time
import sqlite3
import signal
import json
from datetime import datetime
import argparse

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from process_with_ids import StreamableProcessor
from transcription_pipeline import TranscriptionPipeline

class EnhancedBatchVideoProcessor:
    def __init__(self, enable_transcription=False, transcription_service="openai", api_key=None):
        self.db_path = "../library_videos.db"
        self.state_file = "batch_progress.json"
        self.processor = StreamableProcessor()
        self.enable_transcription = enable_transcription
        
        # Initialize transcription pipeline if enabled
        if self.enable_transcription:
            self.transcription_pipeline = TranscriptionPipeline(
                service=transcription_service,
                api_key=api_key
            )
        
        self.load_state()
        
        # Handle Ctrl+C gracefully
        signal.signal(signal.SIGINT, self.signal_handler)
        
    def load_state(self):
        """Load previous state if exists"""
        if os.path.exists(self.state_file):
            with open(self.state_file, 'r') as f:
                self.state = json.load(f)
        else:
            self.state = {
                'processed': 0,
                'success': 0,
                'failed': 0,
                'last_id': None,
                'failed_ids': [],
                'transcribed': 0,
                'transcription_failed': 0
            }
    
    def save_state(self):
        """Save current state"""
        with open(self.state_file, 'w') as f:
            json.dump(self.state, f, indent=2)
    
    def get_next_batch(self, batch_size=10):
        """Get next batch of videos to process"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                query = """
                    SELECT id, title, video_url, streamable_id
                    FROM videos 
                    WHERE streamable_id IS NOT NULL 
                    AND s3_key IS NULL
                """
                
                params = []
                if self.state['last_id']:
                    query += " AND id > ?"
                    params.append(self.state['last_id'])
                
                query += " ORDER BY id LIMIT ?"
                params.append(batch_size)
                
                cursor.execute(query, params)
                
                videos = []
                for row in cursor.fetchall():
                    videos.append({
                        'id': row[0],
                        'title': row[1],
                        'video_url': row[2],
                        'streamable_id': row[3]
                    })
                
                return videos
                
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return []
    
    def transcribe_if_enabled(self, video_id):
        """Transcribe video if transcription is enabled"""
        if not self.enable_transcription:
            return True
            
        try:
            # Get video info from database
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id, title, s3_key
                    FROM videos
                    WHERE id = ?
                """, (video_id,))
                
                row = cursor.fetchone()
                if not row or not row[2]:  # No S3 key
                    return False
                    
                video_info = {
                    'id': row[0],
                    'title': row[1],
                    's3_key': row[2]
                }
                
            # Transcribe the video
            print(f"\n🎤 Transcribing video...")
            success = self.transcription_pipeline.transcribe_video(video_info)
            
            if success:
                self.state['transcribed'] += 1
                print(f"✅ Transcription complete!")
            else:
                self.state['transcription_failed'] += 1
                print(f"⚠️  Transcription failed (will retry later)")
                
            return success
            
        except Exception as e:
            print(f"Transcription error: {e}")
            self.state['transcription_failed'] += 1
            return False
    
    def process_videos(self, total_limit=100, batch_size=10):
        """Process videos with optional transcription"""
        print(f"\n🎬 Starting Enhanced Batch Processor")
        print(f"   Target: {total_limit} videos")
        print(f"   Batch size: {batch_size}")
        print(f"   Transcription: {'ENABLED' if self.enable_transcription else 'DISABLED'}")
        print(f"   Resume from: {self.state['processed']} already processed")
        
        start_time = time.time()
        videos_processed_this_run = 0
        
        try:
            while videos_processed_this_run < total_limit:
                # Get next batch
                videos = self.get_next_batch(batch_size)
                if not videos:
                    print("\n✅ No more unprocessed videos found!")
                    break
                
                print(f"\n📦 Processing batch of {len(videos)} videos...")
                
                # Process each video in the batch
                for i, video in enumerate(videos, 1):
                    print(f"\n{'='*60}")
                    print(f"Processing {self.state['processed'] + 1}/{total_limit}: {video['title']}")
                    print(f"Batch progress: {i}/{len(videos)}")
                    print(f"{'='*60}")
                    
                    try:
                        # Upload to S3
                        success = self.processor.stream_video_to_s3(video, video['streamable_id'])
                        
                        if success:
                            self.state['success'] += 1
                            print(f"✅ Upload Success #{self.state['success']}")
                            
                            # Transcribe if enabled
                            if self.enable_transcription:
                                self.transcribe_if_enabled(video['id'])
                        else:
                            self.state['failed'] += 1
                            self.state['failed_ids'].append(video['id'])
                            print(f"❌ Upload Failed #{self.state['failed']}")
                        
                        self.state['processed'] += 1
                        self.state['last_id'] = video['id']
                        videos_processed_this_run += 1
                        
                        # Save state after each video
                        self.save_state()
                        
                        # Show running statistics
                        elapsed = time.time() - start_time
                        rate = (videos_processed_this_run * 3600) / elapsed  # videos per hour
                        print(f"\n📊 Stats: {self.state['success']} uploaded, {self.state['failed']} failed")
                        
                        if self.enable_transcription:
                            print(f"🎤 Transcribed: {self.state['transcribed']} success, {self.state['transcription_failed']} failed")
                            
                        print(f"⚡ Rate: {rate:.1f} videos/hour")
                        
                        if videos_processed_this_run >= total_limit:
                            break
                            
                    except Exception as e:
                        print(f"Error processing video: {e}")
                        self.state['failed'] += 1
                        self.state['failed_ids'].append(video['id'])
                        self.state['processed'] += 1
                        self.state['last_id'] = video['id']
                        videos_processed_this_run += 1
                        self.save_state()
                
        except KeyboardInterrupt:
            print("\n\n🛑 Interrupted! Saving state...")
            self.save_state()
            
        # Final summary
        print("\n" + "="*60)
        print("📊 FINAL SUMMARY")
        print("="*60)
        print(f"Total processed this run: {videos_processed_this_run}")
        print(f"Overall progress: {self.state['processed']} videos")
        print(f"Successful uploads: {self.state['success']}")
        print(f"Failed uploads: {self.state['failed']}")
        
        if self.enable_transcription:
            print(f"Successful transcriptions: {self.state['transcribed']}")
            print(f"Failed transcriptions: {self.state['transcription_failed']}")
            
        if self.state['failed_ids']:
            print(f"\n❌ Failed video IDs: {self.state['failed_ids']}")
        
        elapsed = time.time() - start_time
        print(f"\n⏱️  Total time: {elapsed/60:.1f} minutes")
        print(f"⚡ Average rate: {(videos_processed_this_run * 3600) / elapsed:.1f} videos/hour")
        
    def signal_handler(self, signum, frame):
        """Handle Ctrl+C gracefully"""
        print("\n\n🛑 Received interrupt signal. Saving state...")
        self.save_state()
        print("✅ State saved. You can resume later.")
        sys.exit(0)


def main():
    """Main entry point with CLI arguments"""
    parser = argparse.ArgumentParser(description='Enhanced batch video processor with transcription')
    parser.add_argument('--limit', type=int, default=100, 
                       help='Total number of videos to process')
    parser.add_argument('--batch', type=int, default=10, 
                       help='Number of videos per batch')
    parser.add_argument('--transcribe', action='store_true',
                       help='Enable transcription after upload')
    parser.add_argument('--transcription-service', default='openai',
                       choices=['openai', 'replicate', 'huggingface'],
                       help='Transcription service to use')
    parser.add_argument('--api-key', help='API key for transcription service')
    
    args = parser.parse_args()
    
    # Check for API key if transcription is enabled
    if args.transcribe and not args.api_key:
        api_key = os.environ.get(f"{args.transcription_service.upper()}_API_KEY")
        if not api_key and args.transcription_service != "huggingface":
            print(f"❌ No API key provided for {args.transcription_service}")
            print(f"   Set {args.transcription_service.upper()}_API_KEY environment variable or use --api-key")
            return
            
    # Create and run processor
    processor = EnhancedBatchVideoProcessor(
        enable_transcription=args.transcribe,
        transcription_service=args.transcription_service,
        api_key=args.api_key
    )
    
    processor.process_videos(total_limit=args.limit, batch_size=args.batch)


if __name__ == "__main__":
    main()