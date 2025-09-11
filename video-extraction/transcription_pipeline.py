#!/usr/bin/env python3
"""
Transcription Pipeline - Integrates transcription into video processing workflow
"""
import os
import sys
import json
import sqlite3
import logging
import time
from datetime import datetime
from typing import Optional, Dict, Any, List
import boto3
from pathlib import Path

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from whisper_api_client import WhisperAPIClient
from s3_manager import S3Manager

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class TranscriptionPipeline:
    """Handles transcription of videos in the pipeline"""
    
    def __init__(self, db_path: str = "../library_videos.db", 
                 service: str = "openai",
                 api_key: Optional[str] = None):
        """
        Initialize transcription pipeline
        
        Args:
            db_path: Path to SQLite database
            service: Transcription service to use
            api_key: API key for the service
        """
        self.db_path = db_path
        self.service = service
        self.whisper_client = WhisperAPIClient(api_key=api_key, service=service)
        self.s3_manager = S3Manager()
        
        # Stats tracking
        self.stats = {
            'processed': 0,
            'success': 0,
            'failed': 0,
            'skipped': 0,
            'total_cost': 0.0
        }
        
    def get_videos_for_transcription(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get videos that need transcription"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, title, s3_key, streamable_id
                FROM videos 
                WHERE s3_key IS NOT NULL 
                AND (transcription_status IS NULL OR transcription_status = 'pending')
                ORDER BY id
                LIMIT ?
            """, (limit,))
            
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
            
    def update_transcription_status(self, video_id: str, status: str, 
                                  transcript_s3_key: Optional[str] = None,
                                  error_message: Optional[str] = None):
        """Update video transcription status in database"""
        with sqlite3.connect(self.db_path) as conn:
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
                # For failed or processing status
                cursor.execute("""
                    UPDATE videos 
                    SET transcription_status = ?
                    WHERE id = ?
                """, (status, video_id))
                
            conn.commit()
            
    def save_transcript_to_s3(self, video_id: str, transcript: str) -> Optional[str]:
        """Save transcript to S3"""
        try:
            s3_key = f"transcripts/{video_id}_transcript.txt"
            
            self.s3_manager.s3_client.put_object(
                Bucket=self.s3_manager.bucket_name,
                Key=s3_key,
                Body=transcript.encode('utf-8'),
                ContentType='text/plain',
                StorageClass='GLACIER_IR',
                Metadata={
                    'video_id': video_id,
                    'transcribed_at': datetime.utcnow().isoformat(),
                    'service': self.service
                }
            )
            
            logger.info(f"Saved transcript to S3: {s3_key}")
            return s3_key
            
        except Exception as e:
            logger.error(f"Failed to save transcript to S3: {e}")
            return None
            
    def transcribe_video(self, video: Dict[str, Any]) -> bool:
        """Transcribe a single video"""
        video_id = video['id']
        title = video['title']
        s3_key = video['s3_key']
        
        logger.info(f"Transcribing: {title[:50]}...")
        
        try:
            # Update status to processing
            self.update_transcription_status(video_id, 'processing')
            
            # Transcribe using API
            result = self.whisper_client.transcribe(s3_key)
            transcript = result.get('text', '')
            
            if not transcript:
                raise ValueError("Empty transcript returned")
                
            # Save to S3
            transcript_s3_key = self.save_transcript_to_s3(video_id, transcript)
            if not transcript_s3_key:
                raise Exception("Failed to save transcript to S3")
                
            # Update database
            self.update_transcription_status(video_id, 'completed', transcript_s3_key)
            
            # Update stats
            self.stats['success'] += 1
            
            # Estimate cost (assuming average 75 min per video)
            estimated_cost = self.whisper_client.estimate_cost(75)
            self.stats['total_cost'] += estimated_cost
            
            logger.info(f"✅ Transcribed: {title[:50]} ({len(transcript)} chars)")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to transcribe {title}: {e}")
            self.update_transcription_status(video_id, 'failed')
            self.stats['failed'] += 1
            return False
            
    def process_batch(self, batch_size: int = 10, max_retries: int = 3):
        """Process a batch of videos"""
        videos = self.get_videos_for_transcription(batch_size)
        
        if not videos:
            logger.info("No videos need transcription")
            return
            
        logger.info(f"Processing batch of {len(videos)} videos...")
        
        for video in videos:
            self.stats['processed'] += 1
            
            # Check file size before processing
            try:
                s3_obj = self.s3_manager.s3_client.head_object(
                    Bucket=self.s3_manager.bucket_name,
                    Key=video['s3_key']
                )
                size_mb = s3_obj['ContentLength'] / (1024 * 1024)
                
                if self.service == "openai" and size_mb > 25:
                    logger.warning(f"Skipping {video['title']}: File too large ({size_mb:.1f} MB)")
                    self.update_transcription_status(video['id'], 'skipped_too_large')
                    self.stats['skipped'] += 1
                    continue
                    
            except Exception as e:
                logger.error(f"Failed to check file size: {e}")
                
            # Transcribe with retries
            success = False
            for attempt in range(max_retries):
                if self.transcribe_video(video):
                    success = True
                    break
                    
                if attempt < max_retries - 1:
                    wait_time = 30 * (attempt + 1)
                    logger.info(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                    
            # Add delay between videos to avoid rate limits
            time.sleep(5)
            
    def get_progress_report(self) -> Dict[str, Any]:
        """Get transcription progress from database"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN s3_key IS NOT NULL THEN 1 ELSE 0 END) as in_s3,
                    SUM(CASE WHEN transcription_status = 'completed' THEN 1 ELSE 0 END) as completed,
                    SUM(CASE WHEN transcription_status = 'processing' THEN 1 ELSE 0 END) as processing,
                    SUM(CASE WHEN transcription_status = 'failed' THEN 1 ELSE 0 END) as failed,
                    SUM(CASE WHEN transcription_status = 'skipped_too_large' THEN 1 ELSE 0 END) as skipped
                FROM videos
            """)
            
            row = cursor.fetchone()
            return {
                'total_videos': row[0],
                'videos_in_s3': row[1],
                'transcribed': row[2],
                'processing': row[3],
                'failed': row[4],
                'skipped': row[5],
                'pending': row[1] - row[2] - row[3] - row[4] - row[5] if row[1] else 0,
                'session_stats': self.stats
            }
            
    def run_continuous(self, batch_size: int = 10, wait_between_batches: int = 60):
        """Run continuous transcription processing"""
        logger.info(f"Starting continuous transcription pipeline (service: {self.service})")
        
        while True:
            try:
                # Get current progress
                progress = self.get_progress_report()
                logger.info(f"Progress: {progress['transcribed']}/{progress['videos_in_s3']} transcribed")
                
                if progress['pending'] == 0:
                    logger.info("All videos transcribed! Waiting for new videos...")
                    time.sleep(wait_between_batches * 5)
                    continue
                    
                # Process next batch
                self.process_batch(batch_size)
                
                # Show session stats
                logger.info(f"Session stats: {self.stats}")
                logger.info(f"Estimated cost so far: ${self.stats['total_cost']:.2f}")
                
                # Wait before next batch
                time.sleep(wait_between_batches)
                
            except KeyboardInterrupt:
                logger.info("Stopping transcription pipeline...")
                break
            except Exception as e:
                logger.error(f"Pipeline error: {e}")
                time.sleep(300)  # Wait 5 minutes on error


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Run transcription pipeline')
    parser.add_argument('--service', default='openai', 
                       choices=['openai', 'replicate', 'huggingface'],
                       help='Transcription service to use')
    parser.add_argument('--batch-size', type=int, default=10,
                       help='Number of videos per batch')
    parser.add_argument('--continuous', action='store_true',
                       help='Run continuously')
    parser.add_argument('--api-key', help='API key for the service')
    
    args = parser.parse_args()
    
    # Create pipeline
    pipeline = TranscriptionPipeline(
        service=args.service,
        api_key=args.api_key
    )
    
    # Show current progress
    progress = pipeline.get_progress_report()
    print(f"\nTranscription Progress:")
    print(f"  Total videos: {progress['total_videos']}")
    print(f"  Videos in S3: {progress['videos_in_s3']}")
    print(f"  Transcribed: {progress['transcribed']}")
    print(f"  Pending: {progress['pending']}")
    print(f"  Failed: {progress['failed']}")
    print(f"  Skipped: {progress['skipped']}")
    
    if args.continuous:
        pipeline.run_continuous(batch_size=args.batch_size)
    else:
        pipeline.process_batch(batch_size=args.batch_size)
        print(f"\nBatch complete!")
        print(f"Session stats: {pipeline.stats}")
        print(f"Estimated cost: ${pipeline.stats['total_cost']:.2f}")


if __name__ == "__main__":
    main()