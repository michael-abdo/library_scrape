#!/usr/bin/env python3
"""
Unified Video Processor - Complete S3 Workflow for ObjectivePersonality Videos

This script processes videos from the database WHERE s3_key IS NULL and uploads them to S3.
It combines authentication, Streamable ID extraction, S3 streaming, and database updates
into a single, robust workflow.

Usage:
    python3 unified_video_processor.py --limit 5       # Process 5 unprocessed videos
    python3 unified_video_processor.py --status        # Show current status
    python3 unified_video_processor.py <streamable_id> # Process specific video by ID
    python3 unified_video_processor.py <op_url>        # Process specific video by URL

Features:
- Multi-method Streamable ID extraction (cookies, Chrome debug)
- Direct S3 streaming (no local storage)
- Progress tracking and upload verification
- Robust error handling and recovery
- Database updates with S3 metadata
- Batch processing with limit controls
"""

import requests
import sys
import os
import sqlite3
import uuid
import time
import json
import re
import argparse
from datetime import datetime
from pathlib import Path
from s3_manager import S3Manager
from google_gpu_transcriber import GoogleGPUTranscriber

class UnifiedVideoProcessor:
    def __init__(self):
        """Initialize the unified video processor"""
        self.s3_manager = S3Manager()
        self.transcriber = GoogleGPUTranscriber()
        self.db_path = self._find_database()
        self.cookies = self._load_cookies()
        self.session = self._create_session()
        
        # S3 connection is verified in S3Manager constructor
            
    def _find_database(self):
        """Find the database file in possible locations"""
        possible_paths = [
            "../library_videos.db", 
            "../../library_videos.db",
            "/Users/Mike/Xenodx/library_scrape/library_videos.db",
            "library_videos.db"
        ]
        
        for db_path in possible_paths:
            if os.path.exists(db_path):
                return db_path
                
        raise Exception("Could not find library_videos.db database")
    
    def _load_cookies(self):
        """Load authentication cookies from multiple possible locations"""
        possible_paths = [
            "../cookies.json",
            "../../cookies.json",
            "../celebrity_archive_scrape/cookies.json",
            "../../celebrity_archive_scrape/cookies.json",
            "/Users/Mike/Xenodex/celebrity_archive_scrape/cookies.json",
            "cookies.json"
        ]
        
        for cookie_path in possible_paths:
            path = Path(cookie_path)
            if path.exists():
                print(f"📁 Found cookies at: {path}")
                with open(path, 'r') as f:
                    return json.load(f)
        
        print("⚠️  Warning: No cookies.json found. Chrome debug extraction will be used as fallback.")
        return []
    
    def _create_session(self):
        """Create authenticated requests session"""
        session = requests.Session()
        
        # Add authentication cookies
        for cookie in self.cookies:
            session.cookies.set(
                cookie['name'], 
                cookie['value'],
                domain=cookie.get('domain', '.objectivepersonality.com'),
                path=cookie.get('path', '/')
            )
        
        # Set realistic headers
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
        
        return session
    
    def get_unprocessed_videos(self, limit=None):
        """Get videos from database where s3_key IS NULL"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Build query with optional limit
                query = "SELECT id, title, video_url FROM videos WHERE (s3_key IS NULL OR s3_key = '') AND video_url IS NOT NULL"
                params = []
                
                if limit:
                    query += " LIMIT ?"
                    params.append(limit)
                
                cursor.execute(query, params)
                results = cursor.fetchall()
                
                return [{'id': r[0], 'title': r[1], 'video_url': r[2]} for r in results]
                
        except Exception as e:
            print(f"❌ Database error: {e}")
            return []
    
    def extract_streamable_id_via_cookies(self, op_url):
        """Extract Streamable ID using cookie-based authentication"""
        try:
            print(f"🌐 Fetching page with cookies: {op_url}")
            response = self.session.get(op_url, timeout=30)
            response.raise_for_status()
            
            print(f"📄 Page loaded: {len(response.content):,} bytes")
            
            # Multiple patterns to find Streamable video IDs
            patterns = [
                r'cdn-cf-east\.streamable\.com/image/([a-z0-9]+)-screenshot',
                r'cdn-cf-east\.streamable\.com/video/mp4/([a-z0-9]+)\.mp4',
                r'streamable\.com/o/([a-z0-9]+)',
                r'api\.streamable\.com/videos/([a-z0-9]+)',
                r'streamable\.com/([a-z0-9]{6,})(?![/-])',
                r'"streamable_id":\s*"([a-z0-9]+)"',
                r'data-video-id="([a-z0-9]+)"'
            ]
            
            all_matches = []
            for pattern in patterns:
                matches = re.findall(pattern, response.text, re.IGNORECASE)
                all_matches.extend(matches)
            
            # Remove duplicates while preserving order
            unique_matches = list(dict.fromkeys(all_matches))
            
            if unique_matches:
                print(f"🎯 Found Streamable ID via cookies: {unique_matches[0]}")
                return unique_matches[0]
            else:
                print("⚠️  No Streamable IDs found via cookies")
                return None
                
        except Exception as e:
            print(f"⚠️  Cookie extraction failed: {e}")
            return None
    
    def extract_streamable_id_via_chrome_debug(self, op_url, port=9222):
        """Extract Streamable ID via Chrome debug port as fallback"""
        try:
            print(f"🔍 Trying Chrome debug port {port}...")
            
            # Check if Chrome debug is available
            response = requests.get(f'http://localhost:{port}/json/list', timeout=2)
            tabs = response.json()
            
            print(f"✅ Connected to Chrome ({len(tabs)} tabs)")
            
            # Navigate to URL
            payload = {"expression": f"window.location.href = '{op_url}'; true;"}
            requests.post(
                f"http://localhost:{port}/json/runtime/evaluate",
                headers={"Content-Type": "application/json"},
                data=json.dumps(payload),
                timeout=10
            )
            
            # Wait for load
            time.sleep(5)
            
            # Get page content
            payload = {"expression": "document.documentElement.outerHTML"}
            response = requests.post(
                f"http://localhost:{port}/json/runtime/evaluate",
                headers={"Content-Type": "application/json"},
                data=json.dumps(payload),
                timeout=10
            )
            
            result = response.json()
            if 'result' in result and 'value' in result['result']:
                html_content = result['result']['value']
                
                # Extract Streamable IDs
                patterns = [
                    r'cdn-cf-east\.streamable\.com/image/([a-z0-9]+)-screenshot',
                    r'streamable\.com/o/([a-z0-9]+)',
                    r'streamable\.com/([a-z0-9]{6,})(?![/-])',
                ]
                
                for pattern in patterns:
                    matches = re.findall(pattern, html_content, re.IGNORECASE)
                    if matches:
                        print(f"🎯 Found Streamable ID via Chrome: {matches[0]}")
                        return matches[0]
            
        except Exception as e:
            print(f"⚠️  Chrome debug extraction failed: {e}")
        
        return None
    
    def extract_streamable_id(self, op_url):
        """Extract Streamable ID using multiple methods"""
        # Method 1: Cookie-based extraction (primary)
        if self.cookies:
            streamable_id = self.extract_streamable_id_via_cookies(op_url)
            if streamable_id:
                return streamable_id
        
        # Method 2: Chrome debug extraction (fallback)
        streamable_id = self.extract_streamable_id_via_chrome_debug(op_url)
        if streamable_id:
            return streamable_id
        
        print("❌ Failed to extract Streamable ID with all methods")
        return None
    
    def get_streamable_metadata(self, video_id):
        """Get video metadata from Streamable API"""
        print(f"🔗 Getting metadata for Streamable ID: {video_id}")
        
        api_url = f"https://api.streamable.com/videos/{video_id}"
        
        try:
            response = requests.get(api_url, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            title = data.get('title', 'Unknown')
            print(f"✅ Got metadata: {title}")
            
            return data
            
        except Exception as e:
            print(f"❌ Error getting Streamable metadata: {e}")
            return None
    
    def stream_video_to_s3(self, video_record, streamable_id):
        """Stream video directly to S3 with verification"""
        print(f"\n🚀 Starting S3 workflow for: {video_record['title']}")
        
        # Get metadata
        metadata = self.get_streamable_metadata(streamable_id)
        if not metadata:
            return False
        
        # Extract video info
        mp4_info = metadata.get('files', {}).get('mp4', {})
        if not mp4_info:
            print("❌ No MP4 format available")
            return False
            
        video_url = mp4_info.get('url')
        video_size = mp4_info.get('size', 0)
        duration = mp4_info.get('duration', 0)
        
        if not video_url:
            print("❌ No download URL found")
            return False
        
        title = video_record['title'] or metadata.get('title', f"streamable_{streamable_id}")
        
        print(f"🎬 Video Details:")
        print(f"   Title: {title}")
        print(f"   Duration: {duration/60:.1f} minutes")
        print(f"   Size: {video_size / (1024*1024):.1f} MB")
        print(f"   Resolution: {mp4_info.get('width')}x{mp4_info.get('height')}")
        
        # Generate S3 key
        video_uuid = str(uuid.uuid4())
        safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).strip()
        s3_key = f"videos/{video_uuid}/{safe_title}.mp4"
        
        print(f"☁️  S3 Location: s3://{self.s3_manager.bucket_name}/{s3_key}")
        
        # Stream to S3
        try:
            response = requests.get(video_url, stream=True, timeout=30)
            response.raise_for_status()
            
            # Prepare metadata
            metadata_dict = {
                'title': title,
                'duration': str(duration),
                'width': str(mp4_info.get('width', '')),
                'height': str(mp4_info.get('height', '')),
                'streamable_id': streamable_id,
                'op_url': video_record['video_url']
            }
            
            # Upload to S3
            success = self.s3_manager.stream_video_to_s3(
                response,
                s3_key,
                video_size,
                metadata_dict
            )
            
            if not success:
                print("❌ S3 upload failed")
                return False
                
            # Verify upload
            if not self.s3_manager.check_s3_exists(s3_key):
                print("❌ S3 verification failed")
                return False
            
            # Update database with S3 info
            self.update_database_record(video_record, s3_key, streamable_id)
            
            # Start transcription process
            transcription_success = self.transcribe_video(s3_key, video_record)
            
            if transcription_success:
                print(f"✅ Successfully processed and transcribed: {title}")
            else:
                print(f"⚠️  S3 upload successful but transcription failed: {title}")
                
            return True
                
        except Exception as e:
            print(f"❌ Upload error: {e}")
            return False
    
    def transcribe_video(self, s3_key, video_record):
        """Transcribe video using Google GPU transcription"""
        try:
            print(f"🎙️  Starting Google GPU transcription for: {video_record.get('title', 'Unknown')}")
            
            # Generate presigned URL for the video
            presigned_url = self.s3_manager.get_presigned_url(s3_key, expiration=7200)  # 2 hours
            if not presigned_url:
                print("❌ Failed to generate presigned URL for transcription")
                return False
            
            print(f"🔗 Using presigned URL for transcription")
            
            # Perform transcription
            result = self.transcriber.transcribe_video_from_url(presigned_url)
            
            if result and result.get('success'):
                transcript = result.get('transcript', '')
                confidence = result.get('confidence', 0)
                
                # Update database with transcription
                self.update_transcription_record(video_record, transcript, confidence)
                print(f"✅ Transcription completed (confidence: {confidence:.2f})")
                return True
            else:
                error = result.get('error', 'Unknown error') if result else 'No result returned'
                print(f"❌ Transcription failed: {error}")
                return False
                
        except Exception as e:
            print(f"❌ Transcription error: {e}")
            return False
    
    def update_transcription_record(self, video_record, transcript, confidence):
        """Update database with transcription results"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    UPDATE videos 
                    SET transcript = ?,
                        transcription_confidence = ?,
                        transcribed_at = datetime('now')
                    WHERE id = ?
                """, (transcript, confidence, video_record['id']))
                
                conn.commit()
                
                if cursor.rowcount > 0:
                    print(f"   ✅ Updated transcription record: {video_record['id']}")
                else:
                    print(f"   ⚠️  No transcription rows updated")
                    
        except Exception as e:
            print(f"   ❌ Transcription database update error: {e}")
    
    def update_database_record(self, video_record, s3_key, streamable_id):
        """Update database with S3 information"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    UPDATE videos 
                    SET s3_key = ?,
                        s3_bucket = ?,
                        storage_mode = 's3',
                        downloaded_at = datetime('now'),
                        streamable_id = ?
                    WHERE id = ?
                """, (s3_key, self.s3_manager.bucket_name, streamable_id, video_record['id']))
                
                conn.commit()
                
                if cursor.rowcount > 0:
                    print(f"   ✅ Updated database record: {video_record['id']}")
                else:
                    print(f"   ⚠️  No database rows updated")
                    
        except Exception as e:
            print(f"   ❌ Database update error: {e}")
    
    def process_single_video(self, video_record):
        """Process a single video through the complete workflow"""
        try:
            print(f"\n" + "="*60)
            print(f"Processing: {video_record['title']}")
            print(f"URL: {video_record['video_url']}")
            print(f"="*60)
            
            # Extract Streamable ID
            streamable_id = self.extract_streamable_id(video_record['video_url'])
            if not streamable_id:
                print(f"❌ Failed to extract Streamable ID")
                return False
            
            # Stream to S3
            return self.stream_video_to_s3(video_record, streamable_id)
            
        except Exception as e:
            print(f"❌ Error processing video: {e}")
            return False
    
    def process_batch(self, limit=None):
        """Process multiple unprocessed videos"""
        print(f"📋 Unified Video Processor - Batch Mode")
        if limit:
            print(f"   Limit: {limit} videos")
        
        # Get unprocessed videos
        videos = self.get_unprocessed_videos(limit)
        if not videos:
            print("✅ No unprocessed videos found!")
            return
        
        print(f"🎯 Found {len(videos)} videos to process")
        
        # Process each video
        success_count = 0
        failed_count = 0
        
        for i, video in enumerate(videos, 1):
            print(f"\n" + "="*60)
            print(f"Processing {i}/{len(videos)}: {video['title']}")
            print(f"="*60)
            
            if self.process_single_video(video):
                success_count += 1
            else:
                failed_count += 1
            
            # Brief pause between videos
            if i < len(videos):
                time.sleep(1)
        
        # Summary
        print(f"\n📊 BATCH SUMMARY:")
        print(f"✅ Successful: {success_count}")
        print(f"❌ Failed: {failed_count}")
        print(f"📁 Total processed: {len(videos)}")
    
    def show_status(self):
        """Show current database status"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("SELECT COUNT(*) FROM videos")
                total = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(*) FROM videos WHERE s3_key IS NOT NULL AND s3_key != ''")
                s3_count = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(*) FROM videos WHERE local_filename IS NOT NULL AND local_filename != ''")
                local_count = cursor.fetchone()[0]
                
                remaining = total - s3_count - local_count
                
                print(f"📊 Database Status:")
                print(f"   Total videos: {total}")
                print(f"   In S3: {s3_count}")
                print(f"   Local files: {local_count}")
                print(f"   Unprocessed: {remaining}")
                
                if remaining > 0:
                    # Show next few to process
                    cursor.execute("""
                        SELECT title, video_url FROM videos 
                        WHERE (s3_key IS NULL OR s3_key = '') AND video_url IS NOT NULL 
                        LIMIT 5
                    """)
                    next_videos = cursor.fetchall()
                    
                    print(f"\n🎯 Next videos to process:")
                    for i, (title, url) in enumerate(next_videos, 1):
                        print(f"   {i}. {title[:50]}...")
                
        except Exception as e:
            print(f"❌ Status error: {e}")

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Unified Video Processor for ObjectivePersonality Videos')
    parser.add_argument('--limit', type=int, help='Limit number of videos to process')
    parser.add_argument('--status', action='store_true', help='Show database status')
    parser.add_argument('input', nargs='?', help='Streamable ID or ObjectivePersonality URL')
    
    args = parser.parse_args()
    
    try:
        processor = UnifiedVideoProcessor()
        
        if args.status:
            processor.show_status()
        elif args.input:
            # Handle single video by ID or URL
            if args.input.startswith('https://'):
                # Process single URL
                video_record = {'id': None, 'title': 'Single Video', 'video_url': args.input}
                processor.process_single_video(video_record)
            else:
                # Process by Streamable ID
                video_record = {'id': None, 'title': f'Streamable {args.input}', 'video_url': None}
                processor.stream_video_to_s3(video_record, args.input)
        else:
            # Batch processing
            processor.process_batch(args.limit)
            
    except KeyboardInterrupt:
        print("\n⚠️  Interrupted by user")
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()