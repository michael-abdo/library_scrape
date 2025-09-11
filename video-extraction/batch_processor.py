#!/usr/bin/env python3
"""
Batch processor that handles videos one at a time with progress tracking
"""
import sys
import os
import time
import sqlite3
import signal
import json
from datetime import datetime

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from process_with_ids import StreamableProcessor

class BatchVideoProcessor:
    def __init__(self):
        self.db_path = "../library_videos.db"
        self.state_file = "batch_progress.json"
        self.processor = StreamableProcessor()
        self.load_state()
        
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
                'failed_ids': []
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
                    AND streamable_id != 'MANUAL_CHECK_REQUIRED'
                    AND (s3_key IS NULL OR s3_key = '')
                """
                
                params = []
                
                if self.state['last_id']:
                    query += " AND id > ?"
                    params.append(self.state['last_id'])
                
                # Exclude failed IDs
                if self.state['failed_ids']:
                    placeholders = ','.join(['?'] * len(self.state['failed_ids']))
                    query += f" AND id NOT IN ({placeholders})"
                    params.extend(self.state['failed_ids'])
                    
                query += f" ORDER BY id LIMIT {batch_size}"
                
                cursor.execute(query, params)
                    
                results = cursor.fetchall()
                
                return [{
                    'id': r[0], 
                    'title': r[1], 
                    'video_url': r[2],
                    'streamable_id': r[3]
                } for r in results]
                
        except Exception as e:
            print(f"❌ Database error: {e}")
            return []
    
    def process_batch(self, total_limit=100, batch_size=10):
        """Process videos in small batches to avoid timeouts"""
        print(f"\n🚀 Batch Video Processor")
        print(f"   Total target: {total_limit} videos")
        print(f"   Batch size: {batch_size} videos")
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
                        # Process the video
                        success = self.processor.stream_video_to_s3(video, video['streamable_id'])
                        
                        if success:
                            self.state['success'] += 1
                            print(f"✅ Success #{self.state['success']}")
                        else:
                            self.state['failed'] += 1
                            self.state['failed_ids'].append(video['id'])
                            print(f"❌ Failed #{self.state['failed']}")
                        
                        self.state['processed'] += 1
                        self.state['last_id'] = video['id']
                        videos_processed_this_run += 1
                        
                        # Save state after each video
                        self.save_state()
                        
                        # Show running statistics
                        elapsed = time.time() - start_time
                        rate = (videos_processed_this_run * 3600) / elapsed  # videos per hour
                        print(f"\n📊 Stats: {self.state['success']} success, {self.state['failed']} failed")
                        print(f"⚡ Rate: {rate:.1f} videos/hour")
                        
                        if videos_processed_this_run >= total_limit:
                            break
                            
                    except KeyboardInterrupt:
                        raise
                    except Exception as e:
                        print(f"❌ Error processing {video['title']}: {e}")
                        self.state['failed'] += 1
                        self.state['failed_ids'].append(video['id'])
                        self.save_state()
                
                # Brief pause between batches
                if videos_processed_this_run < total_limit:
                    print("\n💤 Pausing 2 seconds between batches...")
                    time.sleep(2)
                    
        except KeyboardInterrupt:
            print("\n\n⚠️  Interrupted by user")
            print("💾 Progress saved - run again to resume")
        
        # Final summary
        elapsed_time = time.time() - start_time
        print(f"\n{'='*60}")
        print(f"📊 SESSION SUMMARY:")
        print(f"   Time elapsed: {elapsed_time/60:.1f} minutes")
        print(f"   Videos processed this run: {videos_processed_this_run}")
        print(f"   ✅ Success: {self.state['success']} total")
        print(f"   ❌ Failed: {self.state['failed']} total")
        print(f"   📁 Total all-time: {self.state['processed']}")
        
        if videos_processed_this_run > 0:
            rate = (videos_processed_this_run * 3600) / elapsed_time
            print(f"\n   ⚡ Session rate: {rate:.1f} videos/hour")
            
            # Estimate for all videos
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT COUNT(*) FROM videos 
                    WHERE streamable_id IS NOT NULL 
                    AND (s3_key IS NULL OR s3_key = '')
                """)
                remaining = cursor.fetchone()[0]
                
            if remaining > 0:
                eta_hours = remaining / rate
                print(f"   📅 Estimated time for all {remaining} remaining: {eta_hours:.1f} hours")

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Batch video processor')
    parser.add_argument('--limit', type=int, default=100, help='Total videos to process')
    parser.add_argument('--batch', type=int, default=10, help='Videos per batch')
    parser.add_argument('--reset', action='store_true', help='Reset progress and start fresh')
    
    args = parser.parse_args()
    
    processor = BatchVideoProcessor()
    
    if args.reset:
        processor.state = {
            'processed': 0,
            'success': 0,
            'failed': 0,
            'last_id': None,
            'failed_ids': []
        }
        processor.save_state()
        print("🔄 Progress reset")
    
    processor.process_batch(args.limit, args.batch)

if __name__ == "__main__":
    main()