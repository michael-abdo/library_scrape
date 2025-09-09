#!/usr/bin/env python3
"""
Batch Streamable ID Processor
Processes all videos without streamable_ids using the proven extraction method
"""

import sqlite3
import time
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
from proven_extractor import ProvenExtractor

class BatchProcessor:
    def __init__(self, db_path: str = "library_videos.db", chrome_port: int = 9222):
        """Initialize batch processor"""
        self.db_path = Path(db_path)
        self.chrome_port = chrome_port
        self.extractor = ProvenExtractor(chrome_port=chrome_port)
        
        # Setup logging
        self.logs_dir = Path("extraction_logs")
        self.logs_dir.mkdir(exist_ok=True)
        
        # Create session log file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = self.logs_dir / f"extraction_session_{timestamp}.log"
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(self.log_file),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
        # Load or create progress file
        self.progress_file = self.logs_dir / "progress.json"
        self.progress = self._load_progress()
        
        self.logger.info(f"🚀 Batch Processor initialized")
        self.logger.info(f"📂 Database: {self.db_path}")
        self.logger.info(f"📋 Logs: {self.log_file}")
        self.logger.info(f"🌐 Chrome Port: {self.chrome_port}")
    
    def _load_progress(self) -> Dict:
        """Load processing progress from file"""
        if self.progress_file.exists():
            with open(self.progress_file, 'r') as f:
                progress = json.load(f)
                self.logger.info(f"📈 Loaded progress: {progress.get('processed', 0)} processed")
                return progress
        
        return {
            'processed': 0,
            'successful': 0,
            'failed': 0,
            'last_processed_id': None,
            'start_time': datetime.now().isoformat(),
            'session_count': 0
        }
    
    def _save_progress(self):
        """Save processing progress to file"""
        with open(self.progress_file, 'w') as f:
            json.dump(self.progress, f, indent=2)
    
    def get_videos_without_streamable_ids(self, limit: Optional[int] = None, start_from_id: Optional[str] = None) -> List[Dict]:
        """Get videos that need Streamable IDs extracted"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            base_query = """
                SELECT id, title, video_url 
                FROM videos 
                WHERE (streamable_id IS NULL OR streamable_id = '') 
                AND video_url IS NOT NULL
                AND video_url != ''
            """
            
            # Resume from last processed ID if specified
            if start_from_id:
                base_query += f" AND id > '{start_from_id}'"
            
            base_query += " ORDER BY id"
            
            if limit:
                base_query += f" LIMIT {limit}"
            
            cursor.execute(base_query)
            results = cursor.fetchall()
            
            return [{'id': r[0], 'title': r[1], 'video_url': r[2]} for r in results]
    
    def update_database_with_streamable_id(self, video_id: str, streamable_id: str) -> bool:
        """Update database with found Streamable ID"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE videos SET streamable_id = ? WHERE id = ?",
                    (streamable_id, video_id)
                )
                conn.commit()
                
                self.logger.info(f"💾 Database updated: {video_id} -> {streamable_id}")
                return True
                
        except Exception as e:
            self.logger.error(f"❌ Database update failed for {video_id}: {e}")
            return False
    
    def process_single_video(self, video: Dict) -> Optional[str]:
        """Process a single video and return Streamable ID"""
        video_id = video['id']
        video_url = video['video_url']
        title = video.get('title', 'Unknown')[:50] + "..." if len(video.get('title', '')) > 50 else video.get('title', 'Unknown')
        
        self.logger.info(f"🎬 Processing: {title} (ID: {video_id})")
        self.logger.info(f"🔗 URL: {video_url}")
        
        try:
            streamable_id = self.extractor.extract_streamable_id(video_url)
            
            if streamable_id:
                # Update database
                if self.update_database_with_streamable_id(video_id, streamable_id):
                    self.logger.info(f"✅ SUCCESS: {title} -> {streamable_id}")
                    return streamable_id
                else:
                    self.logger.error(f"❌ Database update failed for {title}")
                    return None
            else:
                self.logger.warning(f"⚠️  No Streamable ID found for: {title}")
                return None
                
        except Exception as e:
            self.logger.error(f"❌ Processing error for {title}: {e}")
            return None
    
    def process_batch(self, limit: Optional[int] = None) -> Dict:
        """Process a batch of videos"""
        self.logger.info("=" * 80)
        self.logger.info("🚀 Starting Batch Processing")
        self.logger.info("=" * 80)
        
        # Increment session count
        self.progress['session_count'] += 1
        
        # Get videos to process
        start_from_id = self.progress.get('last_processed_id')
        videos = self.get_videos_without_streamable_ids(limit=limit, start_from_id=start_from_id)
        
        if not videos:
            self.logger.info("🎉 No more videos to process!")
            return self.progress
        
        self.logger.info(f"📊 Found {len(videos)} videos to process")
        
        if start_from_id:
            self.logger.info(f"📍 Resuming from ID: {start_from_id}")
        
        # Process each video
        session_successful = 0
        session_failed = 0
        
        for i, video in enumerate(videos, 1):
            self.logger.info(f"\n--- Video {i}/{len(videos)} ---")
            self.logger.info(f"📈 Session Progress: {session_successful + session_failed}/{len(videos)} processed")
            self.logger.info(f"🎯 Total Progress: {self.progress['processed']} videos processed overall")
            
            # Process video
            streamable_id = self.process_single_video(video)
            
            # Update counters
            if streamable_id:
                session_successful += 1
                self.progress['successful'] += 1
            else:
                session_failed += 1
                self.progress['failed'] += 1
            
            self.progress['processed'] += 1
            self.progress['last_processed_id'] = video['id']
            
            # Save progress periodically
            if i % 5 == 0:  # Save every 5 videos
                self._save_progress()
            
            # Rate limiting: 2 second delay between requests
            if i < len(videos):
                self.logger.info("⏳ Rate limiting: waiting 2 seconds...")
                time.sleep(2)
        
        # Final statistics
        self.logger.info("=" * 80)
        self.logger.info("📊 Session Summary")
        self.logger.info("=" * 80)
        self.logger.info(f"✅ Successful extractions: {session_successful}")
        self.logger.info(f"❌ Failed extractions: {session_failed}")
        self.logger.info(f"📈 Session success rate: {session_successful/(session_successful + session_failed)*100:.1f}%")
        
        self.logger.info("=" * 80)
        self.logger.info("📊 Overall Statistics")
        self.logger.info("=" * 80)
        self.logger.info(f"📋 Total videos processed: {self.progress['processed']}")
        self.logger.info(f"✅ Total successful: {self.progress['successful']}")
        self.logger.info(f"❌ Total failed: {self.progress['failed']}")
        self.logger.info(f"🎯 Overall success rate: {self.progress['successful']/self.progress['processed']*100:.1f}%")
        
        # Save final progress
        self._save_progress()
        
        return {
            'session_successful': session_successful,
            'session_failed': session_failed,
            'total_processed': self.progress['processed'],
            'total_successful': self.progress['successful'],
            'total_failed': self.progress['failed']
        }
    
    def get_processing_stats(self) -> Dict:
        """Get current processing statistics"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Total videos
            cursor.execute("SELECT COUNT(*) FROM videos")
            total_videos = cursor.fetchone()[0]
            
            # Videos with streamable_ids
            cursor.execute("SELECT COUNT(*) FROM videos WHERE streamable_id IS NOT NULL AND streamable_id != ''")
            videos_with_ids = cursor.fetchone()[0]
            
            # Videos without streamable_ids
            remaining = total_videos - videos_with_ids
            
            return {
                'total_videos': total_videos,
                'videos_with_streamable_ids': videos_with_ids,
                'videos_remaining': remaining,
                'completion_percentage': (videos_with_ids / total_videos) * 100 if total_videos > 0 else 0,
                'processed_this_session': self.progress['processed'],
                'successful_this_session': self.progress['successful'],
                'failed_this_session': self.progress['failed']
            }
    
    def reset_progress(self):
        """Reset processing progress (use with caution)"""
        self.progress = {
            'processed': 0,
            'successful': 0,
            'failed': 0,
            'last_processed_id': None,
            'start_time': datetime.now().isoformat(),
            'session_count': 0
        }
        self._save_progress()
        self.logger.info("🔄 Progress reset")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Batch Streamable ID Processor')
    parser.add_argument('--limit', type=int, help='Limit number of videos to process')
    parser.add_argument('--stats', action='store_true', help='Show processing statistics')
    parser.add_argument('--reset', action='store_true', help='Reset progress (use with caution)')
    parser.add_argument('--chrome-port', type=int, default=9222, help='Chrome debugging port')
    parser.add_argument('--db', type=str, default='library_videos.db', help='Database file path')
    
    args = parser.parse_args()
    
    processor = BatchProcessor(db_path=args.db, chrome_port=args.chrome_port)
    
    if args.reset:
        processor.reset_progress()
        return
    
    if args.stats:
        stats = processor.get_processing_stats()
        print("\n📊 Processing Statistics")
        print("=" * 40)
        print(f"Total videos in database: {stats['total_videos']}")
        print(f"Videos with Streamable IDs: {stats['videos_with_streamable_ids']}")
        print(f"Videos remaining: {stats['videos_remaining']}")
        print(f"Completion: {stats['completion_percentage']:.1f}%")
        return
    
    # Process videos
    results = processor.process_batch(limit=args.limit)
    
    print(f"\n🎯 Batch processing complete!")
    print(f"✅ Successful: {results['session_successful']}")
    print(f"❌ Failed: {results['session_failed']}")


if __name__ == "__main__":
    main()