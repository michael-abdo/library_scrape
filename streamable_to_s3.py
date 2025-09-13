#!/usr/bin/env python3
"""
Download videos from Streamable and upload to S3
"""
import os
import sys
import json
import time
import sqlite3
import requests
import boto3
from datetime import datetime
from typing import Optional, Dict, List
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class StreamableToS3:
    def __init__(self, bucket_name: str = None, s3_prefix: str = "objectivepersonality/videos/"):
        """Initialize the downloader with S3 configuration"""
        self.bucket_name = bucket_name or os.environ.get('S3_BUCKET_NAME', 'op-videos-storage')
        self.s3_prefix = s3_prefix
        
        # Initialize S3 client with zenex profile
        try:
            session = boto3.Session(profile_name='zenex')
            self.s3_client = session.client('s3')
            # Test S3 access
            self.s3_client.list_buckets()
            logger.info(f"✅ Connected to S3, will use bucket: {self.bucket_name}")
        except Exception as e:
            logger.error(f"❌ AWS S3 initialization failed: {e}")
            self.s3_client = None
            
        # Create download directory
        self.download_dir = "downloads"
        os.makedirs(self.download_dir, exist_ok=True)
        
        # Track statistics
        self.stats = {
            'attempted': 0,
            'downloaded': 0,
            'uploaded': 0,
            'failed': 0,
            'already_exists': 0
        }
        
    def get_streamable_info(self, video_id: str) -> Optional[Dict]:
        """Get video information from Streamable API"""
        try:
            # Try the public API first
            url = f"https://api.streamable.com/videos/{video_id}"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"✅ Got info for {video_id}: {data.get('title', 'No title')}")
                return data
            else:
                logger.warning(f"⚠️  API returned {response.status_code} for {video_id}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error getting info for {video_id}: {e}")
            return None
            
    def download_video(self, video_id: str, video_info: Dict) -> Optional[str]:
        """Download video from Streamable"""
        try:
            # Get the best quality video URL
            video_url = None
            
            if 'files' in video_info:
                # Try to get the highest quality with URL
                if 'mp4' in video_info['files'] and video_info['files']['mp4'].get('url'):
                    video_url = video_info['files']['mp4']['url']
                elif 'mp4-mobile' in video_info['files'] and video_info['files']['mp4-mobile'].get('url'):
                    video_url = video_info['files']['mp4-mobile']['url']
                    
            if not video_url:
                logger.error(f"❌ No video URL found in API response for {video_id}")
                return None
                
            logger.info(f"📥 Downloading from: {video_url}")
            
            # Download the file
            response = requests.get(video_url, stream=True, timeout=30)
            
            if response.status_code != 200:
                logger.error(f"❌ Download failed with status {response.status_code}")
                return None
                
            # Save to local file
            filename = f"{video_id}.mp4"
            filepath = os.path.join(self.download_dir, filename)
            
            total_size = int(response.headers.get('content-length', 0))
            
            with open(filepath, 'wb') as f:
                downloaded = 0
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        if total_size > 0:
                            progress = (downloaded / total_size) * 100
                            print(f"\r  Progress: {progress:.1f}%", end='', flush=True)
                            
            print()  # New line after progress
            
            file_size = os.path.getsize(filepath)
            logger.info(f"✅ Downloaded {filename} ({file_size / 1024 / 1024:.1f} MB)")
            
            return filepath
            
        except Exception as e:
            logger.error(f"❌ Download error for {video_id}: {e}")
            return None
            
    def upload_to_s3(self, filepath: str, video_id: str, metadata: Dict = None) -> bool:
        """Upload video to S3"""
        if not self.s3_client:
            logger.error("❌ S3 client not initialized")
            return False
            
        try:
            filename = os.path.basename(filepath)
            s3_key = f"{self.s3_prefix}{video_id}/{filename}"
            
            # Check if already exists
            try:
                self.s3_client.head_object(Bucket=self.bucket_name, Key=s3_key)
                logger.info(f"⏭️  Video already exists in S3: {s3_key}")
                self.stats['already_exists'] += 1
                return True
            except:
                pass  # File doesn't exist, proceed with upload
            
            # Prepare metadata
            upload_metadata = {
                'video_id': video_id,
                'upload_date': datetime.now().isoformat(),
                'source': 'streamable'
            }
            
            if metadata:
                upload_metadata.update(metadata)
                
            # Upload to S3
            logger.info(f"☁️  Uploading to S3: s3://{self.bucket_name}/{s3_key}")
            
            file_size = os.path.getsize(filepath)
            
            with open(filepath, 'rb') as f:
                self.s3_client.upload_fileobj(
                    f,
                    self.bucket_name,
                    s3_key,
                    ExtraArgs={
                        'Metadata': {k: str(v) for k, v in upload_metadata.items()},
                        'ContentType': 'video/mp4'
                    },
                    Callback=lambda bytes_transferred: print(
                        f"\r  Upload progress: {(bytes_transferred / file_size) * 100:.1f}%", 
                        end='', 
                        flush=True
                    )
                )
                
            print()  # New line after progress
            logger.info(f"✅ Uploaded to S3: {s3_key}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ S3 upload error: {e}")
            return False
            
    def process_video(self, video_id: str, title: str = None) -> bool:
        """Process a single video: download and upload to S3"""
        self.stats['attempted'] += 1
        
        logger.info(f"\n{'='*60}")
        logger.info(f"Processing: {video_id} - {title or 'Unknown title'}")
        
        try:
            # Get video info
            video_info = self.get_streamable_info(video_id)
            if not video_info:
                self.stats['failed'] += 1
                return False
                
            # Download video
            filepath = self.download_video(video_id, video_info)
            if not filepath:
                self.stats['failed'] += 1
                return False
                
            self.stats['downloaded'] += 1
            
            # Upload to S3
            metadata = {
                'title': title or video_info.get('title', ''),
                'duration': video_info.get('duration', 0),
                'created_at': video_info.get('created_at', '')
            }
            
            if self.upload_to_s3(filepath, video_id, metadata):
                self.stats['uploaded'] += 1
                
                # Clean up local file
                os.remove(filepath)
                logger.info(f"🧹 Cleaned up local file: {filepath}")
                
                return True
            else:
                self.stats['failed'] += 1
                return False
                
        except Exception as e:
            logger.error(f"❌ Processing error for {video_id}: {e}")
            self.stats['failed'] += 1
            return False
            
    def process_batch(self, videos: List[tuple], max_workers: int = 3):
        """Process multiple videos in parallel"""
        logger.info(f"\n🚀 Starting batch processing of {len(videos)} videos")
        logger.info(f"🔧 Using {max_workers} parallel workers")
        
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            future_to_video = {
                executor.submit(self.process_video, video_id, title): (video_id, title)
                for video_id, title in videos
            }
            
            # Process completed tasks
            for future in as_completed(future_to_video):
                video_id, title = future_to_video[future]
                try:
                    result = future.result()
                    if result:
                        logger.info(f"✅ Completed: {video_id}")
                    else:
                        logger.warning(f"⚠️  Failed: {video_id}")
                except Exception as e:
                    logger.error(f"❌ Exception for {video_id}: {e}")
                    
        # Print statistics
        elapsed = time.time() - start_time
        logger.info(f"\n{'='*60}")
        logger.info("📊 BATCH PROCESSING COMPLETE")
        logger.info(f"⏱️  Total time: {elapsed:.1f} seconds")
        logger.info(f"📈 Statistics:")
        logger.info(f"   - Attempted: {self.stats['attempted']}")
        logger.info(f"   - Downloaded: {self.stats['downloaded']}")
        logger.info(f"   - Uploaded: {self.stats['uploaded']}")
        logger.info(f"   - Already exists: {self.stats['already_exists']}")
        logger.info(f"   - Failed: {self.stats['failed']}")
        logger.info(f"   - Success rate: {(self.stats['uploaded'] / self.stats['attempted'] * 100):.1f}%")

def test_five_videos():
    """Test the script with 5 videos from the database"""
    # Get 5 videos from database
    db_path = 'library_videos.db' if os.path.exists('library_videos.db') else '../library_videos.db'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get 5 random videos with streamable IDs that don't have S3 keys
    cursor.execute("""
        SELECT streamable_id, title 
        FROM videos 
        WHERE streamable_id IS NOT NULL 
        AND streamable_id != 'MANUAL_CHECK_REQUIRED'
        AND (s3_key IS NULL OR s3_key = '')
        ORDER BY RANDOM()
        LIMIT 5
    """)
    
    videos = cursor.fetchall()
    conn.close()
    
    if not videos:
        logger.error("No videos found in database")
        return
        
    logger.info(f"Selected {len(videos)} test videos:")
    for video_id, title in videos:
        logger.info(f"  - {video_id}: {title}")
        
    # Process the videos
    downloader = StreamableToS3()
    downloader.process_batch(videos, max_workers=2)

def process_n_videos(n):
    """Process N videos from the database"""
    # Get N videos from database
    db_path = 'library_videos.db' if os.path.exists('library_videos.db') else '../library_videos.db'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get N random videos with streamable IDs that don't have S3 keys
    cursor.execute("""
        SELECT streamable_id, title 
        FROM videos 
        WHERE streamable_id IS NOT NULL 
        AND streamable_id != 'MANUAL_CHECK_REQUIRED'
        AND (s3_key IS NULL OR s3_key = '')
        ORDER BY RANDOM()
        LIMIT ?
    """, (n,))
    
    videos = cursor.fetchall()
    conn.close()
    
    if not videos:
        logger.error(f"No videos found in database")
        return
        
    logger.info(f"Selected {len(videos)} videos to process:")
    for video_id, title in videos:
        logger.info(f"  - {video_id}: {title}")
        
    # Process the videos
    downloader = StreamableToS3()
    downloader.process_batch(videos, max_workers=2)

def main():
    """Main function to handle command line usage"""
    if len(sys.argv) > 1:
        if sys.argv[1] == '--test':
            test_five_videos()
        elif sys.argv[1].startswith('--') and sys.argv[1][2:].isdigit():
            # Handle --N format
            n = int(sys.argv[1][2:])
            process_n_videos(n)
        else:
            # Process specific video ID
            video_id = sys.argv[1]
            title = sys.argv[2] if len(sys.argv) > 2 else None
            downloader = StreamableToS3()
            downloader.process_video(video_id, title)
    else:
        print("Usage:")
        print("  python3 streamable_to_s3.py --test           # Test with 5 random videos")
        print("  python3 streamable_to_s3.py --N              # Process N random videos (e.g., --10, --200)")
        print("  python3 streamable_to_s3.py VIDEO_ID [TITLE] # Process specific video")
        print("Examples:")
        print("  python3 streamable_to_s3.py --200            # Process 200 videos")
        print("  python3 streamable_to_s3.py thfwyf 'Elyse Myers'")

if __name__ == "__main__":
    main()