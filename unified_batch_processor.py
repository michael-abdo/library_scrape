#!/usr/bin/env python3
"""
Unified Batch Video Processor
Processes all videos using the unified extraction method to handle multiple platforms
"""

import sqlite3
import time
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
from unified_video_extractor import UnifiedVideoExtractor

class UnifiedBatchProcessor:
    def __init__(self, db_path: str = "library_videos.db", chrome_port: int = 9222):
        """Initialize unified batch processor"""
        self.db_path = Path(db_path)
        self.chrome_port = chrome_port
        self.extractor = UnifiedVideoExtractor(chrome_port=chrome_port)
        
        # Setup logging
        self.logs_dir = Path("extraction_logs")
        self.logs_dir.mkdir(exist_ok=True)
        
        # Create session log file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = self.logs_dir / f"unified_extraction_session_{timestamp}.log"
        
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
        self.progress_file = self.logs_dir / "unified_progress.json"
        self.progress = self._load_progress()
        
        self.logger.info(f"🚀 Unified Batch Processor initialized")
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
            'by_platform': {
                'streamable': 0,
                'youtube': 0,
                'vimeo': 0,
                'wistia': 0,
                'other': 0,
                'direct': 0,
                'none': 0
            },
            'last_processed_id': None,
            'start_time': datetime.now().isoformat(),
            'session_count': 0
        }
    
    def _save_progress(self):
        """Save processing progress to file"""
        with open(self.progress_file, 'w') as f:
            json.dump(self.progress, f, indent=2)
    
    def get_videos_to_process(self, limit: Optional[int] = None, start_from_id: Optional[str] = None) -> List[Dict]:
        """Get videos that need video information extracted"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Query for videos without any video platform info
            base_query = """
                SELECT id, title, video_url 
                FROM videos 
                WHERE video_url IS NOT NULL
                AND video_url != ''
                AND (
                    (streamable_id IS NULL OR streamable_id = '')
                    AND (youtube_id IS NULL OR youtube_id = '')
                    AND (vimeo_id IS NULL OR vimeo_id = '')
                    AND (wistia_id IS NULL OR wistia_id = '')
                    AND (other_video_url IS NULL OR other_video_url = '')
                    AND (video_platform IS NULL OR video_platform = '')
                )
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
    
    def update_database_with_video_info(self, video_id: str, video_info: Dict) -> bool:
        """Update database with extracted video information"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Build update query based on found information
                update_parts = []
                params = []
                
                if video_info.get('streamable_id'):
                    update_parts.append("streamable_id = ?")
                    params.append(video_info['streamable_id'])
                
                if video_info.get('youtube_id'):
                    update_parts.append("youtube_id = ?")
                    params.append(video_info['youtube_id'])
                
                if video_info.get('vimeo_id'):
                    update_parts.append("vimeo_id = ?")
                    params.append(video_info['vimeo_id'])
                
                if video_info.get('wistia_id'):
                    update_parts.append("wistia_id = ?")
                    params.append(video_info['wistia_id'])
                
                if video_info.get('other_video_url'):
                    update_parts.append("other_video_url = ?")
                    params.append(video_info['other_video_url'])
                
                if video_info.get('platform'):
                    update_parts.append("video_platform = ?")
                    params.append(video_info['platform'])
                
                if update_parts:
                    query = f"UPDATE videos SET {', '.join(update_parts)} WHERE id = ?"
                    params.append(video_id)
                    cursor.execute(query, params)
                    conn.commit()
                    
                    self.logger.info(f"💾 Database updated: {video_id} -> Platform: {video_info.get('platform', 'none')}")
                    return True
                
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Database update failed for {video_id}: {e}")
            return False
    
    def process_single_video(self, video: Dict) -> Dict:
        """Process a single video and return extraction results"""
        video_id = video['id']
        video_url = video['video_url']
        title = video.get('title', 'Unknown')[:50] + "..." if len(video.get('title', '')) > 50 else video.get('title', 'Unknown')
        
        self.logger.info(f"🎬 Processing: {title} (ID: {video_id})")
        self.logger.info(f"🔗 URL: {video_url}")
        
        try:
            # Extract video information
            video_info = self.extractor.extract_video_info(video_url)
            
            if video_info.get('error'):
                self.logger.error(f"❌ Extraction error for {title}: {video_info['error']}")
                return video_info
            
            # Update database if any video information found
            if video_info.get('platform'):
                if self.update_database_with_video_info(video_id, video_info):
                    self.logger.info(f"✅ SUCCESS: {title} -> {video_info['platform']}")
                    # Update platform counter
                    platform = video_info['platform']
                    if platform in self.progress['by_platform']:
                        self.progress['by_platform'][platform] += 1
                else:
                    self.logger.error(f"❌ Database update failed for {title}")
                    video_info['error'] = 'Database update failed'
            else:
                self.logger.warning(f"⚠️  No video content found for: {title}")
                self.progress['by_platform']['none'] += 1
            
            return video_info
                
        except Exception as e:
            self.logger.error(f"❌ Processing error for {title}: {e}")
            return {'error': str(e)}
    
    def process_batch(self, limit: Optional[int] = None) -> Dict:
        """Process a batch of videos"""
        self.logger.info("=" * 80)
        self.logger.info("🚀 Starting Unified Batch Processing")
        self.logger.info("=" * 80)
        
        # Increment session count
        self.progress['session_count'] += 1
        
        # Get videos to process
        start_from_id = self.progress.get('last_processed_id')
        videos = self.get_videos_to_process(limit=limit, start_from_id=start_from_id)
        
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
            result = self.process_single_video(video)
            
            # Update counters
            if result.get('platform'):
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
        
        self.logger.info("\n📊 Platform Distribution (This Session):")
        for platform, count in sorted(self.progress['by_platform'].items()):
            if count > 0:
                self.logger.info(f"   {platform}: {count}")
        
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
            'total_failed': self.progress['failed'],
            'by_platform': self.progress['by_platform']
        }
    
    def get_processing_stats(self) -> Dict:
        """Get current processing statistics"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Total videos
            cursor.execute("SELECT COUNT(*) FROM videos")
            total_videos = cursor.fetchone()[0]
            
            # Videos with any video platform
            cursor.execute("""
                SELECT COUNT(*) FROM videos 
                WHERE streamable_id IS NOT NULL 
                   OR youtube_id IS NOT NULL 
                   OR vimeo_id IS NOT NULL 
                   OR wistia_id IS NOT NULL 
                   OR other_video_url IS NOT NULL
            """)
            videos_with_content = cursor.fetchone()[0]
            
            # Platform breakdown
            platform_counts = {}
            
            cursor.execute("SELECT COUNT(*) FROM videos WHERE streamable_id IS NOT NULL AND streamable_id != ''")
            platform_counts['streamable'] = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM videos WHERE youtube_id IS NOT NULL AND youtube_id != ''")
            platform_counts['youtube'] = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM videos WHERE vimeo_id IS NOT NULL AND vimeo_id != ''")
            platform_counts['vimeo'] = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM videos WHERE wistia_id IS NOT NULL AND wistia_id != ''")
            platform_counts['wistia'] = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM videos WHERE other_video_url IS NOT NULL AND other_video_url != ''")
            platform_counts['other'] = cursor.fetchone()[0]
            
            # Videos without any content
            remaining = total_videos - videos_with_content
            
            return {
                'total_videos': total_videos,
                'videos_with_content': videos_with_content,
                'videos_remaining': remaining,
                'completion_percentage': (videos_with_content / total_videos) * 100 if total_videos > 0 else 0,
                'platform_counts': platform_counts,
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
            'by_platform': {
                'streamable': 0,
                'youtube': 0,
                'vimeo': 0,
                'wistia': 0,
                'other': 0,
                'direct': 0,
                'none': 0
            },
            'last_processed_id': None,
            'start_time': datetime.now().isoformat(),
            'session_count': 0
        }
        self._save_progress()
        self.logger.info("🔄 Progress reset")
    
    def generate_report(self) -> str:
        """Generate a comprehensive report of extraction results"""
        stats = self.get_processing_stats()
        
        report = f"""
📊 UNIFIED VIDEO EXTRACTION REPORT
================================================================================
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

📈 OVERALL STATISTICS:
- Total videos in database: {stats['total_videos']}
- Videos with content found: {stats['videos_with_content']} ({stats['completion_percentage']:.1f}%)
- Videos remaining: {stats['videos_remaining']}

🎬 PLATFORM BREAKDOWN:
"""
        
        for platform, count in sorted(stats['platform_counts'].items()):
            percentage = (count / stats['total_videos'] * 100) if stats['total_videos'] > 0 else 0
            report += f"- {platform.capitalize()}: {count} ({percentage:.1f}%)\n"
        
        report += f"""
📊 SESSION STATISTICS:
- Total processed: {self.progress['processed']}
- Successful: {self.progress['successful']}
- Failed: {self.progress['failed']}
- Success rate: {(self.progress['successful']/self.progress['processed']*100) if self.progress['processed'] > 0 else 0:.1f}%

🎯 EXTRACTION EFFECTIVENESS:
- Platform detection rate: {(stats['videos_with_content']/stats['total_videos']*100) if stats['total_videos'] > 0 else 0:.1f}%
- Session success rate: {(self.progress['successful']/self.progress['processed']*100) if self.progress['processed'] > 0 else 0:.1f}%

================================================================================
"""
        return report


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Unified Batch Video Processor')
    parser.add_argument('--limit', type=int, help='Limit number of videos to process')
    parser.add_argument('--stats', action='store_true', help='Show processing statistics')
    parser.add_argument('--reset', action='store_true', help='Reset progress (use with caution)')
    parser.add_argument('--report', action='store_true', help='Generate extraction report')
    parser.add_argument('--chrome-port', type=int, default=9222, help='Chrome debugging port')
    parser.add_argument('--db', type=str, default='library_videos.db', help='Database file path')
    
    args = parser.parse_args()
    
    processor = UnifiedBatchProcessor(db_path=args.db, chrome_port=args.chrome_port)
    
    if args.reset:
        processor.reset_progress()
        return
    
    if args.stats:
        stats = processor.get_processing_stats()
        print("\n📊 Processing Statistics")
        print("=" * 40)
        print(f"Total videos: {stats['total_videos']}")
        print(f"Videos with content: {stats['videos_with_content']}")
        print(f"Videos remaining: {stats['videos_remaining']}")
        print(f"Completion: {stats['completion_percentage']:.1f}%")
        print("\nPlatform breakdown:")
        for platform, count in sorted(stats['platform_counts'].items()):
            print(f"  {platform}: {count}")
        return
    
    if args.report:
        print(processor.generate_report())
        return
    
    # Process videos
    results = processor.process_batch(limit=args.limit)
    
    print(f"\n🎯 Batch processing complete!")
    print(f"✅ Successful: {results['session_successful']}")
    print(f"❌ Failed: {results['session_failed']}")


if __name__ == "__main__":
    main()