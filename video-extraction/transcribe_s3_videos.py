#!/usr/bin/env python3
"""
Transcribe S3 Videos Script

This script finds videos in the database that have s3_key but no transcript,
transcribes them using OpenAI Whisper, saves transcripts to S3, and updates
the database with transcript S3 links.

Usage:
    python3 transcribe_s3_videos.py 10              # Process 10 videos (positional)
    python3 transcribe_s3_videos.py --limit 10      # Process 10 videos (flag)
    python3 transcribe_s3_videos.py                 # Process all videos
    python3 transcribe_s3_videos.py --status        # Show transcription status
    python3 transcribe_s3_videos.py --video-id <id> # Process specific video
    python3 transcribe_s3_videos.py 5 --dry-run     # Preview what would be processed
    python3 transcribe_s3_videos.py 20 --service google  # Use Google Speech-to-Text
"""

import argparse
import json
import logging
import os
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

from openai_whisper_transcriber import OpenAIWhisperTranscriber
from google_gpu_transcriber import GoogleGPUTranscriber
from s3_manager import S3Manager
from transcription_config import TranscriptionConfig

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TranscribeS3Videos:
    """Handle transcription of videos already in S3"""
    
    def __init__(self):
        """Initialize the transcription processor"""
        self.s3_manager = S3Manager()
        self.db_path = self._find_database()
        
        # Initialize transcription service based on config
        self.service = TranscriptionConfig.DEFAULT_SERVICE
        logger.info(f"Using transcription service: {self.service}")
        
        if self.service == 'openai':
            self.transcriber = OpenAIWhisperTranscriber()
            logger.info("Using OpenAI Whisper (87.5% cost savings)")
        else:
            self.transcriber = GoogleGPUTranscriber()
            logger.info("Using Google Speech-to-Text (high accuracy)")
    
    def _find_database(self) -> str:
        """Find the database file in possible locations"""
        possible_paths = [
            "../library_scrape/library_videos.db",
            "../../library_scrape/library_videos.db",
            "../../../library_scrape/library_videos.db",
            "/home/Mike/projects/Xenodex/ops_scraping/library_scrape/library_videos.db",
            "../library_videos.db",
            "../../library_videos.db",
            "library_videos.db"
        ]
        
        for db_path in possible_paths:
            if os.path.exists(db_path):
                logger.info(f"Found database at: {db_path}")
                return db_path
        
        raise Exception("Could not find library_videos.db database")
    
    def get_videos_needing_transcription(self, limit: Optional[int] = None) -> List[Dict]:
        """Get videos that have s3_key but no transcript"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # First check if transcript column exists
                cursor.execute("PRAGMA table_info(videos)")
                columns = [row[1] for row in cursor.fetchall()]
                has_transcript_column = 'transcript' in columns
                
                # Query for videos with s3_key but no transcript
                if has_transcript_column:
                    query = """
                        SELECT id, title, s3_key, s3_bucket, streamable_id, video_url
                        FROM videos 
                        WHERE s3_key IS NOT NULL 
                        AND s3_key != ''
                        AND (transcript IS NULL OR transcript = '')
                        AND (transcript_s3_key IS NULL OR transcript_s3_key = '')
                    """
                else:
                    # If no transcript column, just check transcript_s3_key
                    query = """
                        SELECT id, title, s3_key, s3_bucket, streamable_id, video_url
                        FROM videos 
                        WHERE s3_key IS NOT NULL 
                        AND s3_key != ''
                        AND (transcript_s3_key IS NULL OR transcript_s3_key = '')
                    """
                
                if limit:
                    query += f" LIMIT {limit}"
                
                cursor.execute(query)
                results = cursor.fetchall()
                
                videos = []
                for row in results:
                    videos.append({
                        'id': row[0],
                        'title': row[1],
                        's3_key': row[2],
                        's3_bucket': row[3] or self.s3_manager.bucket_name,
                        'streamable_id': row[4],
                        'video_url': row[5]
                    })
                
                return videos
                
        except Exception as e:
            logger.error(f"Database error: {e}")
            return []
    
    def save_transcript_to_s3(self, video_id: str, transcript: str, metadata: Dict) -> Optional[str]:
        """Save transcript to S3 and return the S3 key"""
        try:
            # Generate S3 key for transcript
            s3_key = f"transcripts/{video_id}/transcript.json"
            
            # Prepare transcript data
            transcript_data = {
                'video_id': video_id,
                'transcript': transcript,
                'metadata': metadata,
                'created_at': datetime.now().isoformat(),
                'service': metadata.get('service', 'unknown'),
                'confidence': metadata.get('confidence', 0),
                'language': metadata.get('language_detected', 'en'),
                'word_timestamps': metadata.get('word_timestamps', []),
                'segments': metadata.get('segments', [])
            }
            
            # Convert to JSON
            transcript_json = json.dumps(transcript_data, indent=2)
            
            # Upload to S3
            logger.info(f"Uploading transcript to S3: {s3_key}")
            
            # Create a file-like object from the string
            from io import BytesIO
            transcript_bytes = BytesIO(transcript_json.encode('utf-8'))
            
            extra_args = {
                'ContentType': 'application/json',
                'Metadata': {
                    'video_id': video_id,
                    'service': metadata.get('service', 'unknown'),
                    'confidence': str(metadata.get('confidence', 0))
                }
            }
            
            self.s3_manager.s3_client.upload_fileobj(
                transcript_bytes,
                self.s3_manager.bucket_name,
                s3_key,
                ExtraArgs=extra_args
            )
            
            logger.info(f"Successfully uploaded transcript to: s3://{self.s3_manager.bucket_name}/{s3_key}")
            return s3_key
            
        except Exception as e:
            logger.error(f"Failed to save transcript to S3: {e}")
            return None
    
    def update_database_with_transcript(self, video_id: str, transcript: str, 
                                      transcript_s3_key: str, metadata: Dict) -> bool:
        """Update database with transcript and S3 information"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Check if transcript column exists
                cursor.execute("PRAGMA table_info(videos)")
                columns = [row[1] for row in cursor.fetchall()]
                has_transcript_column = 'transcript' in columns
                
                # Generate S3 URL
                transcript_s3_url = f"https://{self.s3_manager.bucket_name}.s3.{self.s3_manager.region}.amazonaws.com/{transcript_s3_key}"
                
                # Update database based on available columns
                if has_transcript_column:
                    cursor.execute("""
                        UPDATE videos 
                        SET transcript = ?,
                            transcript_s3_key = ?,
                            transcript_s3_url = ?,
                            transcription_status = 'completed',
                            transcribed_at = datetime('now'),
                            transcription_service = ?
                        WHERE id = ?
                    """, (
                        transcript,
                        transcript_s3_key,
                        transcript_s3_url,
                        metadata.get('service', 'unknown'),
                        video_id
                    ))
                else:
                    # Update without transcript column
                    cursor.execute("""
                        UPDATE videos 
                        SET transcript_s3_key = ?,
                            transcript_s3_url = ?,
                            transcription_status = 'completed',
                            transcribed_at = datetime('now'),
                            transcription_service = ?
                        WHERE id = ?
                    """, (
                        transcript_s3_key,
                        transcript_s3_url,
                        metadata.get('service', 'unknown'),
                        video_id
                    ))
                
                conn.commit()
                
                if cursor.rowcount > 0:
                    logger.info(f"Updated database for video: {video_id}")
                    return True
                else:
                    logger.warning(f"No database rows updated for video: {video_id}")
                    return False
                    
        except Exception as e:
            logger.error(f"Database update error: {e}")
            return False
    
    def transcribe_video(self, video: Dict) -> bool:
        """Transcribe a single video and update database"""
        try:
            logger.info(f"\nProcessing: {video['title']}")
            logger.info(f"S3 Key: {video['s3_key']}")
            
            # Generate presigned URL for the video
            presigned_url = self.s3_manager.get_presigned_url(
                video['s3_key'], 
                expiration=7200  # 2 hours
            )
            
            if not presigned_url:
                logger.error(f"Failed to generate presigned URL for {video['s3_key']}")
                return False
            
            # Transcribe using selected service
            logger.info(f"Starting transcription with {self.service}...")
            start_time = time.time()
            
            result = self.transcriber.transcribe_from_url(presigned_url)
            
            if not result or not result.get('success'):
                error = result.get('error', 'Unknown error') if result else 'No result'
                logger.error(f"Transcription failed: {error}")
                
                # Try fallback service
                fallback_service = 'google' if self.service == 'openai' else 'openai'
                logger.info(f"Attempting fallback to {fallback_service}...")
                
                if fallback_service == 'openai':
                    fallback_transcriber = OpenAIWhisperTranscriber()
                else:
                    fallback_transcriber = GoogleGPUTranscriber()
                
                result = fallback_transcriber.transcribe_from_url(presigned_url)
                
                if not result or not result.get('success'):
                    logger.error("Fallback transcription also failed")
                    return False
            
            # Extract transcript and metadata
            transcript = result.get('transcript', '').strip()
            if not transcript:
                logger.error("Empty transcript received")
                return False
            
            duration = time.time() - start_time
            logger.info(f"Transcription completed in {duration:.1f}s")
            logger.info(f"Transcript length: {len(transcript)} chars")
            logger.info(f"Confidence: {result.get('confidence', 0):.2f}")
            
            # Save transcript to S3
            transcript_s3_key = self.save_transcript_to_s3(
                video['id'],
                transcript,
                result
            )
            
            if not transcript_s3_key:
                logger.error("Failed to save transcript to S3")
                return False
            
            # Update database
            success = self.update_database_with_transcript(
                video['id'],
                transcript,
                transcript_s3_key,
                result
            )
            
            if success:
                logger.info(f"✅ Successfully transcribed: {video['title']}")
                return True
            else:
                logger.error("Failed to update database")
                return False
                
        except Exception as e:
            logger.error(f"Error processing video {video['id']}: {e}")
            return False
    
    def process_batch(self, limit: Optional[int] = None):
        """Process multiple videos in batch"""
        logger.info("Starting batch transcription process...")
        
        # Get videos needing transcription
        videos = self.get_videos_needing_transcription(limit)
        
        if not videos:
            logger.info("No videos found that need transcription")
            return
        
        logger.info(f"Found {len(videos)} videos to transcribe")
        
        # Process each video
        success_count = 0
        failed_count = 0
        
        for i, video in enumerate(videos, 1):
            logger.info(f"\n{'='*60}")
            logger.info(f"Processing {i}/{len(videos)}")
            logger.info(f"{'='*60}")
            
            if self.transcribe_video(video):
                success_count += 1
            else:
                failed_count += 1
            
            # Brief pause between videos
            if i < len(videos):
                time.sleep(1)
        
        # Summary
        logger.info(f"\n{'='*60}")
        logger.info("BATCH SUMMARY:")
        logger.info(f"✅ Successful: {success_count}")
        logger.info(f"❌ Failed: {failed_count}")
        logger.info(f"📊 Total processed: {len(videos)}")
        logger.info(f"{'='*60}")
    
    def show_dry_run(self, limit: Optional[int] = None):
        """Show what videos would be processed without actually processing them"""
        logger.info("DRY RUN MODE - No videos will be processed")
        logger.info("="*60)
        
        videos = self.get_videos_needing_transcription(limit)
        
        if not videos:
            logger.info("No videos found that need transcription")
            return
        
        logger.info(f"Would process {len(videos)} videos:")
        logger.info("")
        
        total_size = 0
        for i, video in enumerate(videos, 1):
            logger.info(f"{i}. {video['title']}")
            logger.info(f"   ID: {video['id']}")
            logger.info(f"   S3 Key: {video['s3_key']}")
            
            # Try to get file size
            try:
                response = self.s3_manager.s3_client.head_object(
                    Bucket=video['s3_bucket'],
                    Key=video['s3_key']
                )
                size_mb = response['ContentLength'] / (1024 * 1024)
                total_size += size_mb
                logger.info(f"   Size: {size_mb:.1f} MB")
            except Exception:
                logger.info(f"   Size: Unknown")
            
            logger.info("")
        
        logger.info("="*60)
        logger.info(f"Total videos to process: {len(videos)}")
        if total_size > 0:
            logger.info(f"Total size: {total_size:.1f} MB")
            logger.info(f"Estimated cost (OpenAI Whisper @ $0.006/min, ~1MB/min): ${total_size * 0.006:.2f}")
        logger.info("="*60)
    
    def show_status(self):
        """Show transcription status from database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Check if transcript column exists
                cursor.execute("PRAGMA table_info(videos)")
                columns = [row[1] for row in cursor.fetchall()]
                has_transcript_column = 'transcript' in columns
                
                # Total videos
                cursor.execute("SELECT COUNT(*) FROM videos")
                total = cursor.fetchone()[0]
                
                # Videos with S3 keys
                cursor.execute("SELECT COUNT(*) FROM videos WHERE s3_key IS NOT NULL AND s3_key != ''")
                with_s3 = cursor.fetchone()[0]
                
                # Videos with transcripts (check both transcript column if exists and transcript_s3_key)
                if has_transcript_column:
                    cursor.execute("SELECT COUNT(*) FROM videos WHERE transcript IS NOT NULL AND transcript != ''")
                    with_transcript = cursor.fetchone()[0]
                else:
                    with_transcript = 0
                
                # Videos with S3 but no transcript S3 key
                cursor.execute("""
                    SELECT COUNT(*) FROM videos 
                    WHERE s3_key IS NOT NULL AND s3_key != ''
                    AND (transcript_s3_key IS NULL OR transcript_s3_key = '')
                """)
                need_transcript = cursor.fetchone()[0]
                
                # Videos with transcript in S3
                cursor.execute("SELECT COUNT(*) FROM videos WHERE transcript_s3_key IS NOT NULL AND transcript_s3_key != ''")
                transcript_in_s3 = cursor.fetchone()[0]
                
                logger.info("\n📊 Transcription Status:")
                logger.info(f"   Total videos: {total}")
                logger.info(f"   Videos in S3: {with_s3}")
                if has_transcript_column:
                    logger.info(f"   Videos with transcript text: {with_transcript}")
                logger.info(f"   Videos needing transcript: {need_transcript}")
                logger.info(f"   Transcripts saved to S3: {transcript_in_s3}")
                
                if need_transcript > 0:
                    # Show next few videos to transcribe
                    cursor.execute("""
                        SELECT title, s3_key 
                        FROM videos 
                        WHERE s3_key IS NOT NULL AND s3_key != ''
                        AND (transcript_s3_key IS NULL OR transcript_s3_key = '')
                        LIMIT 5
                    """)
                    next_videos = cursor.fetchall()
                    
                    logger.info(f"\n🎯 Next videos to transcribe:")
                    for i, (title, s3_key) in enumerate(next_videos, 1):
                        logger.info(f"   {i}. {title[:50]}...")
                        logger.info(f"      S3: {s3_key}")
                
        except Exception as e:
            logger.error(f"Status error: {e}")
    
    def process_specific_video(self, video_id: str):
        """Process a specific video by ID"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT id, title, s3_key, s3_bucket, streamable_id, video_url
                    FROM videos 
                    WHERE id = ?
                """, (video_id,))
                
                row = cursor.fetchone()
                if not row:
                    logger.error(f"Video not found: {video_id}")
                    return
                
                video = {
                    'id': row[0],
                    'title': row[1],
                    's3_key': row[2],
                    's3_bucket': row[3] or self.s3_manager.bucket_name,
                    'streamable_id': row[4],
                    'video_url': row[5]
                }
                
                if not video['s3_key']:
                    logger.error(f"Video {video_id} has no S3 key")
                    return
                
                self.transcribe_video(video)
                
        except Exception as e:
            logger.error(f"Error processing video {video_id}: {e}")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Transcribe videos already in S3',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Process 10 videos
    python3 transcribe_s3_videos.py 10
    python3 transcribe_s3_videos.py --limit 10
    
    # Process all videos without limit
    python3 transcribe_s3_videos.py
    
    # Show transcription status
    python3 transcribe_s3_videos.py --status
    
    # Process specific video
    python3 transcribe_s3_videos.py --video-id abc123
    
    # Use specific service
    python3 transcribe_s3_videos.py 5 --service google
        """
    )
    
    # Positional argument for number of videos (optional)
    parser.add_argument('count', nargs='?', type=int, 
                       help='Number of videos to process (optional)')
    parser.add_argument('-l', '--limit', type=int, 
                       help='Limit number of videos to process (alternative to positional argument)')
    parser.add_argument('-s', '--status', action='store_true', 
                       help='Show transcription status')
    parser.add_argument('-v', '--video-id', 
                       help='Process specific video by ID')
    parser.add_argument('--service', choices=['openai', 'google'], 
                       help='Override default transcription service')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be processed without actually processing')
    
    args = parser.parse_args()
    
    # Handle both positional count and --limit flag
    limit = args.count if args.count is not None else args.limit
    
    # Override service if specified
    if args.service:
        TranscriptionConfig.DEFAULT_SERVICE = args.service
    
    try:
        processor = TranscribeS3Videos()
        
        if args.status:
            processor.show_status()
        elif args.video_id:
            processor.process_specific_video(args.video_id)
        elif args.dry_run:
            processor.show_dry_run(limit)
        else:
            processor.process_batch(limit)
            
    except KeyboardInterrupt:
        logger.info("\nInterrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()