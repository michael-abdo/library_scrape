#!/usr/bin/env python3
"""
Upload existing transcripts to S3 and update database with S3 links

This script finds videos that have transcripts but no S3 transcript links,
uploads them to S3, and updates the database with the S3 URLs.
"""

import argparse
import json
import logging
import sqlite3
import sys
from datetime import datetime
from typing import Dict, List, Optional
import boto3
from botocore.exceptions import ClientError

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TranscriptUploader:
    """Upload existing transcripts to S3"""
    
    def __init__(self, db_path: str, bucket_name: str = 'xenodx-video-archive', profile: str = 'zenex'):
        """Initialize the uploader"""
        self.db_path = db_path
        self.bucket_name = bucket_name
        
        # Initialize S3 client
        session = boto3.Session(profile_name=profile)
        self.s3_client = session.client('s3')
        
        # Ensure database has required columns
        self.ensure_database_schema()
    
    def ensure_database_schema(self):
        """Ensure database has S3 transcript columns"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Get current columns
                cursor.execute("PRAGMA table_info(videos)")
                columns = [row[1] for row in cursor.fetchall()]
                
                # Add missing columns
                if 'transcript_s3_key' not in columns:
                    cursor.execute('ALTER TABLE videos ADD COLUMN transcript_s3_key TEXT')
                    logger.info("Added transcript_s3_key column")
                
                if 'transcript_s3_url' not in columns:
                    cursor.execute('ALTER TABLE videos ADD COLUMN transcript_s3_url TEXT')
                    logger.info("Added transcript_s3_url column")
                
                conn.commit()
        except Exception as e:
            logger.error(f"Error updating schema: {e}")
    
    def get_videos_needing_s3_upload(self, limit: Optional[int] = None) -> List[Dict]:
        """Get videos that have transcripts but no S3 links"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                # Check what columns exist
                cursor.execute("PRAGMA table_info(videos)")
                columns = [row[1] for row in cursor.fetchall()]
                
                # Build query based on available columns
                select_cols = ['id', 'title']
                where_conditions = []
                
                # Check for transcript column (different databases may have different column names)
                transcript_col = None
                for col in ['transcript', 'transcript_text', 'transcription']:
                    if col in columns:
                        transcript_col = col
                        break
                
                if not transcript_col:
                    logger.warning("No transcript column found in database")
                    return []
                
                select_cols.append(transcript_col)
                where_conditions.extend([
                    f"{transcript_col} IS NOT NULL",
                    f"{transcript_col} != ''"
                ])
                
                # Add optional columns if they exist
                optional_cols = ['segments', 'has_timestamps', 'transcription_service', 
                               'transcribed_at', 'transcript_s3_key', 'transcript_s3_url']
                for col in optional_cols:
                    if col in columns:
                        select_cols.append(col)
                
                # Add S3 key condition if column exists
                if 'transcript_s3_key' in columns:
                    where_conditions.append("(transcript_s3_key IS NULL OR transcript_s3_key = '')")
                
                query = f"""
                    SELECT {', '.join(select_cols)}
                    FROM videos 
                    WHERE {' AND '.join(where_conditions)}
                    ORDER BY id
                """
                
                if limit:
                    query += f" LIMIT {limit}"
                
                cursor.execute(query)
                videos = []
                for row in cursor.fetchall():
                    video_dict = dict(row)
                    # Normalize transcript column name
                    if transcript_col != 'transcript':
                        video_dict['transcript'] = video_dict.get(transcript_col, '')
                    videos.append(video_dict)
                
                return videos
                
        except Exception as e:
            logger.error(f"Database error: {e}")
            return []
    
    def create_transcript_json(self, video: Dict) -> Dict:
        """Create JSON object for S3 storage"""
        transcript_obj = {
            'video_id': video['id'],
            'title': video['title'],
            'transcript': video['transcript'],
            'metadata': {
                'service': video.get('transcription_service', 'unknown'),
                'transcribed_at': video.get('transcribed_at', str(datetime.now())),
                'has_timestamps': bool(video.get('has_timestamps', False))
            }
        }
        
        # Add segments if available
        if video.get('segments'):
            try:
                segments = json.loads(video['segments'])
                transcript_obj['segments'] = segments
                transcript_obj['metadata']['total_segments'] = len(segments)
            except:
                logger.warning(f"Could not parse segments for video {video['id']}")
        
        return transcript_obj
    
    def upload_to_s3(self, video_id: str, transcript_obj: Dict) -> Optional[str]:
        """Upload transcript to S3 and return the key"""
        try:
            # Create S3 key
            s3_key = f"transcripts/{video_id}/transcript_with_timestamps.json"
            
            # Convert to JSON
            json_content = json.dumps(transcript_obj, indent=2)
            
            # Upload to S3
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=json_content,
                ContentType='application/json'
            )
            
            logger.info(f"Uploaded transcript to S3: {s3_key}")
            return s3_key
            
        except Exception as e:
            logger.error(f"Failed to upload to S3: {e}")
            return None
    
    def update_database(self, video_id: str, s3_key: str) -> bool:
        """Update database with S3 information"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Create S3 URL
                s3_url = f"https://{self.bucket_name}.s3.amazonaws.com/{s3_key}"
                
                cursor.execute("""
                    UPDATE videos 
                    SET transcript_s3_key = ?,
                        transcript_s3_url = ?
                    WHERE id = ?
                """, (s3_key, s3_url, video_id))
                
                conn.commit()
                return True
                
        except Exception as e:
            logger.error(f"Failed to update database: {e}")
            return False
    
    def process_videos(self, limit: Optional[int] = None, dry_run: bool = False):
        """Process videos needing S3 upload"""
        videos = self.get_videos_needing_s3_upload(limit)
        
        if not videos:
            logger.info("No videos found that need S3 upload")
            return
        
        logger.info(f"Found {len(videos)} videos to process")
        
        if dry_run:
            logger.info("DRY RUN - No actual uploads will be performed")
            for video in videos:
                print(f"Would upload: Video {video['id']} - {video['title']}")
            return
        
        # Process each video
        successful = 0
        failed = 0
        
        for i, video in enumerate(videos, 1):
            print(f"\n{'='*60}")
            print(f"Processing video {i}/{len(videos)}")
            print(f"Video ID: {video['id']}")
            print(f"Title: {video['title']}")
            print(f"Has timestamps: {video.get('has_timestamps', False)}")
            print(f"{'='*60}")
            
            try:
                # Create transcript JSON
                transcript_obj = self.create_transcript_json(video)
                
                # Upload to S3
                s3_key = self.upload_to_s3(str(video['id']), transcript_obj)
                
                if s3_key:
                    # Update database
                    if self.update_database(str(video['id']), s3_key):
                        successful += 1
                        logger.info(f"Successfully processed video {video['id']}")
                    else:
                        failed += 1
                        logger.error(f"Failed to update database for video {video['id']}")
                else:
                    failed += 1
                    logger.error(f"Failed to upload transcript for video {video['id']}")
                    
            except Exception as e:
                failed += 1
                logger.error(f"Error processing video {video['id']}: {e}")
        
        print(f"\n{'='*60}")
        print(f"Upload Summary:")
        print(f"  Total processed: {len(videos)}")
        print(f"  Successful: {successful}")
        print(f"  Failed: {failed}")
        print(f"{'='*60}")


def main():
    parser = argparse.ArgumentParser(
        description='Upload existing transcripts to S3 and update database with S3 links'
    )
    
    parser.add_argument('--db', default='test_videos.db',
                        help='Path to SQLite database (default: test_videos.db)')
    parser.add_argument('--bucket', default='xenodx-video-archive',
                        help='S3 bucket name (default: xenodx-video-archive)')
    parser.add_argument('--profile', default='zenex',
                        help='AWS profile to use (default: zenex)')
    parser.add_argument('--limit', type=int,
                        help='Limit number of videos to process')
    parser.add_argument('--dry-run', action='store_true',
                        help='Show what would be uploaded without actually uploading')
    
    args = parser.parse_args()
    
    # Create uploader and process videos
    uploader = TranscriptUploader(args.db, args.bucket, args.profile)
    uploader.process_videos(args.limit, args.dry_run)


if __name__ == '__main__':
    main()