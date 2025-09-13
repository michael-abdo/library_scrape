#!/usr/bin/env python3
"""
Comprehensive Analysis: Database Videos vs S3 Videos

This script performs a detailed comparison between:
1. Video records in the database (with their S3 keys)
2. Actual video files stored in S3

It identifies discrepancies, orphaned files, missing files, and data integrity issues.
"""

import sqlite3
import boto3
import json
import logging
from datetime import datetime
from typing import Dict, List, Set, Tuple, Optional
from collections import defaultdict
import re

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DatabaseS3Analyzer:
    """Analyze differences between database records and S3 files"""
    
    def __init__(self, db_path: str = "../../library_scrape/library_videos.db", 
                 bucket_name: str = "xenodx-video-archive", profile: str = "zenex"):
        self.db_path = db_path
        self.bucket_name = bucket_name
        
        # Initialize S3 client
        session = boto3.Session(profile_name=profile)
        self.s3_client = session.client('s3')
        
        # Data structures to hold analysis results
        self.db_videos = {}
        self.s3_videos = {}
        self.analysis_results = {}
    
    def get_database_videos(self) -> Dict[str, Dict]:
        """Extract all video records from database"""
        logger.info("🔍 Analyzing database video records...")
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                # Get all videos with their S3 information
                cursor.execute("""
                    SELECT id, title, s3_key, s3_bucket, streamable_id, 
                           video_url, file_size, s3_upload_date,
                           transcript_s3_key, transcript_s3_url,
                           transcription_status, transcription_service
                    FROM videos
                    ORDER BY id
                """)
                
                videos = {}
                for row in cursor.fetchall():
                    video_dict = dict(row)
                    videos[video_dict['id']] = video_dict
                
                logger.info(f"✅ Found {len(videos)} video records in database")
                return videos
                
        except Exception as e:
            logger.error(f"❌ Database error: {e}")
            return {}
    
    def get_s3_videos(self) -> Dict[str, Dict]:
        """Extract all video files from S3"""
        logger.info("🔍 Analyzing S3 video files...")
        
        try:
            # List all video files in S3
            paginator = self.s3_client.get_paginator('list_objects_v2')
            
            videos = {}
            total_size = 0
            file_count = 0
            
            for page in paginator.paginate(Bucket=self.bucket_name, Prefix='videos/'):
                if 'Contents' not in page:
                    continue
                    
                for obj in page['Contents']:
                    key = obj['Key']
                    size = obj['Size']
                    last_modified = obj['LastModified']
                    
                    # Skip directories
                    if key.endswith('/'):
                        continue
                    
                    # Extract video info from S3 key
                    # Format: videos/{uuid}/{filename}
                    parts = key.split('/')
                    if len(parts) >= 3:
                        uuid = parts[1]
                        filename = '/'.join(parts[2:])  # Handle nested paths
                        
                        videos[key] = {
                            's3_key': key,
                            'uuid': uuid,
                            'filename': filename,
                            'size': size,
                            'last_modified': last_modified,
                            'size_mb': round(size / (1024 * 1024), 2)
                        }
                        
                        total_size += size
                        file_count += 1
            
            logger.info(f"✅ Found {file_count} video files in S3")
            logger.info(f"📊 Total S3 video storage: {round(total_size / (1024**3), 2)} GB")
            return videos
            
        except Exception as e:
            logger.error(f"❌ S3 error: {e}")
            return {}
    
    def analyze_discrepancies(self) -> Dict:
        """Perform comprehensive analysis of discrepancies"""
        logger.info("🧠 Performing discrepancy analysis...")
        
        db_s3_keys = set()
        db_with_s3 = 0
        db_without_s3 = 0
        
        # Analyze database records
        for video_id, video in self.db_videos.items():
            if video.get('s3_key'):
                db_s3_keys.add(video['s3_key'])
                db_with_s3 += 1
            else:
                db_without_s3 += 1
        
        # Get actual S3 keys
        actual_s3_keys = set(self.s3_videos.keys())
        
        # Find discrepancies
        db_keys_not_in_s3 = db_s3_keys - actual_s3_keys  # Database claims these exist but they don't
        s3_keys_not_in_db = actual_s3_keys - db_s3_keys  # S3 has these but DB doesn't know about them
        matching_keys = db_s3_keys & actual_s3_keys      # Perfect matches
        
        # Analyze transcription status
        transcription_analysis = self.analyze_transcription_status()
        
        # Analyze file patterns and potential matches
        pattern_analysis = self.analyze_file_patterns()
        
        results = {
            'summary': {
                'total_db_records': len(self.db_videos),
                'db_records_with_s3_key': db_with_s3,
                'db_records_without_s3_key': db_without_s3,
                'total_s3_files': len(self.s3_videos),
                'perfect_matches': len(matching_keys),
                'db_keys_missing_in_s3': len(db_keys_not_in_s3),
                's3_orphaned_files': len(s3_keys_not_in_db)
            },
            'discrepancies': {
                'db_keys_not_in_s3': list(db_keys_not_in_s3),
                's3_keys_not_in_db': list(s3_keys_not_in_db),
                'matching_keys': list(matching_keys)
            },
            'transcription_analysis': transcription_analysis,
            'pattern_analysis': pattern_analysis
        }
        
        return results
    
    def analyze_transcription_status(self) -> Dict:
        """Analyze transcription status across database records"""
        logger.info("🎯 Analyzing transcription status...")
        
        total_videos = len(self.db_videos)
        with_transcript_s3_key = 0
        with_transcript_s3_url = 0
        with_transcription_service = 0
        transcription_services = defaultdict(int)
        
        videos_ready_for_transcription = []
        
        for video_id, video in self.db_videos.items():
            # Count transcription-related fields
            if video.get('transcript_s3_key'):
                with_transcript_s3_key += 1
            if video.get('transcript_s3_url'):
                with_transcript_s3_url += 1
            if video.get('transcription_service'):
                with_transcription_service += 1
                transcription_services[video['transcription_service']] += 1
            
            # Identify videos ready for transcription (have S3 video but no transcript)
            if (video.get('s3_key') and 
                video['s3_key'] in self.s3_videos and 
                not video.get('transcript_s3_key')):
                videos_ready_for_transcription.append({
                    'id': video_id,
                    'title': video.get('title', 'Unknown'),
                    's3_key': video['s3_key'],
                    'size_mb': self.s3_videos[video['s3_key']]['size_mb']
                })
        
        return {
            'total_videos': total_videos,
            'with_transcript_s3_key': with_transcript_s3_key,
            'with_transcript_s3_url': with_transcript_s3_url,
            'with_transcription_service': with_transcription_service,
            'transcription_services': dict(transcription_services),
            'videos_ready_for_transcription': len(videos_ready_for_transcription),
            'ready_videos_sample': videos_ready_for_transcription[:10]  # First 10 as sample
        }
    
    def analyze_file_patterns(self) -> Dict:
        """Analyze file naming patterns and potential matches"""
        logger.info("🔍 Analyzing file patterns...")
        
        # Extract UUIDs from database S3 keys
        db_uuids = set()
        for video in self.db_videos.values():
            if video.get('s3_key'):
                # Extract UUID from s3_key like "videos/uuid/filename"
                match = re.search(r'videos/([a-f0-9-]{36})/', video['s3_key'])
                if match:
                    db_uuids.add(match.group(1))
        
        # Extract UUIDs from actual S3 keys
        s3_uuids = set()
        for s3_key, s3_info in self.s3_videos.items():
            s3_uuids.add(s3_info['uuid'])
        
        # Find UUID matches and mismatches
        uuid_matches = db_uuids & s3_uuids
        db_uuids_not_in_s3 = db_uuids - s3_uuids
        s3_uuids_not_in_db = s3_uuids - db_uuids
        
        # Analyze filename patterns
        s3_filenames = [info['filename'] for info in self.s3_videos.values()]
        filename_patterns = defaultdict(int)
        
        for filename in s3_filenames:
            # Categorize by file extension
            if '.' in filename:
                ext = filename.split('.')[-1].lower()
                filename_patterns[f'*.{ext}'] += 1
            
            # Check for common patterns
            if 'streamable' in filename.lower():
                filename_patterns['streamable_*'] += 1
            if any(word in filename.lower() for word in ['test', 'sample', 'demo']):
                filename_patterns['test_files'] += 1
        
        return {
            'uuid_analysis': {
                'db_uuids': len(db_uuids),
                's3_uuids': len(s3_uuids),
                'uuid_matches': len(uuid_matches),
                'db_uuids_not_in_s3': len(db_uuids_not_in_s3),
                's3_uuids_not_in_db': len(s3_uuids_not_in_db)
            },
            'filename_patterns': dict(filename_patterns),
            'sample_s3_filenames': s3_filenames[:10]
        }
    
    def generate_report(self) -> str:
        """Generate comprehensive analysis report"""
        logger.info("📋 Generating comprehensive report...")
        
        report = []
        report.append("=" * 80)
        report.append("🔍 DATABASE vs S3 COMPREHENSIVE ANALYSIS REPORT")
        report.append("=" * 80)
        report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"Database: {self.db_path}")
        report.append(f"S3 Bucket: {self.bucket_name}")
        report.append("")
        
        # Summary Statistics
        summary = self.analysis_results['summary']
        report.append("📊 SUMMARY STATISTICS")
        report.append("-" * 40)
        report.append(f"Total database records: {summary['total_db_records']:,}")
        report.append(f"  • With S3 key: {summary['db_records_with_s3_key']:,}")
        report.append(f"  • Without S3 key: {summary['db_records_without_s3_key']:,}")
        report.append(f"Total S3 video files: {summary['total_s3_files']:,}")
        report.append(f"Perfect DB ↔ S3 matches: {summary['perfect_matches']:,}")
        report.append(f"DB keys missing in S3: {summary['db_keys_missing_in_s3']:,}")
        report.append(f"S3 files not in DB: {summary['s3_orphaned_files']:,}")
        report.append("")
        
        # Data Integrity Issues
        report.append("🚨 DATA INTEGRITY ISSUES")
        report.append("-" * 40)
        
        discrepancies = self.analysis_results['discrepancies']
        missing_ratio = (summary['db_keys_missing_in_s3'] / summary['db_records_with_s3_key'] * 100) if summary['db_records_with_s3_key'] > 0 else 0
        orphaned_ratio = (summary['s3_orphaned_files'] / summary['total_s3_files'] * 100) if summary['total_s3_files'] > 0 else 0
        
        report.append(f"Database integrity: {missing_ratio:.1f}% of DB S3 keys are invalid")
        report.append(f"S3 orphan rate: {orphaned_ratio:.1f}% of S3 files not tracked in DB")
        report.append("")
        
        # Transcription Analysis
        trans = self.analysis_results['transcription_analysis']
        report.append("🎯 TRANSCRIPTION STATUS ANALYSIS")
        report.append("-" * 40)
        report.append(f"Total videos: {trans['total_videos']:,}")
        report.append(f"With transcript S3 key: {trans['with_transcript_s3_key']:,}")
        report.append(f"With transcript S3 URL: {trans['with_transcript_s3_url']:,}")
        report.append(f"With transcription service: {trans['with_transcription_service']:,}")
        report.append(f"Ready for transcription: {trans['videos_ready_for_transcription']:,}")
        
        if trans['transcription_services']:
            report.append("\nTranscription services used:")
            for service, count in trans['transcription_services'].items():
                report.append(f"  • {service}: {count:,} videos")
        
        report.append("")
        
        # Pattern Analysis
        patterns = self.analysis_results['pattern_analysis']
        report.append("🔍 FILE PATTERN ANALYSIS")
        report.append("-" * 40)
        
        uuid_analysis = patterns['uuid_analysis']
        report.append(f"UUID Directory Analysis:")
        report.append(f"  • Database UUIDs: {uuid_analysis['db_uuids']:,}")
        report.append(f"  • S3 UUIDs: {uuid_analysis['s3_uuids']:,}")
        report.append(f"  • UUID matches: {uuid_analysis['uuid_matches']:,}")
        report.append(f"  • DB UUIDs not in S3: {uuid_analysis['db_uuids_not_in_s3']:,}")
        report.append(f"  • S3 UUIDs not in DB: {uuid_analysis['s3_uuids_not_in_db']:,}")
        
        report.append(f"\nFile type distribution:")
        for pattern, count in patterns['filename_patterns'].items():
            report.append(f"  • {pattern}: {count:,} files")
        
        report.append("")
        
        # Actionable Recommendations
        report.append("💡 ACTIONABLE RECOMMENDATIONS")
        report.append("-" * 40)
        
        if summary['db_keys_missing_in_s3'] > 100:
            report.append("🔴 CRITICAL: Large number of invalid S3 keys in database")
            report.append("   → Run S3 key correction/migration script")
        
        if trans['videos_ready_for_transcription'] > 0:
            estimated_cost = trans['videos_ready_for_transcription'] * 20  # ~$20 per video estimate
            report.append(f"🟡 OPPORTUNITY: {trans['videos_ready_for_transcription']:,} videos ready for transcription")
            report.append(f"   → Estimated cost: ${estimated_cost:,} (OpenAI Whisper)")
            report.append(f"   → Command: python3 transcribe_s3_videos.py {min(10, trans['videos_ready_for_transcription'])}")
        
        if summary['s3_orphaned_files'] > 50:
            report.append("🟠 CLEANUP: Many orphaned S3 files not tracked in database")
            report.append("   → Consider S3 cleanup or database sync")
        
        report.append("")
        
        # Sample Data
        if trans['ready_videos_sample']:
            report.append("📋 SAMPLE VIDEOS READY FOR TRANSCRIPTION")
            report.append("-" * 40)
            for i, video in enumerate(trans['ready_videos_sample'], 1):
                title = video['title'][:50] + "..." if len(video['title']) > 50 else video['title']
                report.append(f"{i:2d}. {title}")
                report.append(f"     ID: {video['id']}")
                report.append(f"     Size: {video['size_mb']} MB")
                report.append(f"     S3: {video['s3_key']}")
                report.append("")
        
        report.append("=" * 80)
        
        return "\n".join(report)
    
    def save_detailed_results(self, filename: str = None):
        """Save detailed analysis results to JSON file"""
        if not filename:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"db_s3_analysis_{timestamp}.json"
        
        # Add sample data for detailed inspection
        detailed_results = self.analysis_results.copy()
        
        # Add sample discrepancies
        discrepancies = detailed_results['discrepancies']
        if len(discrepancies['db_keys_not_in_s3']) > 0:
            detailed_results['sample_missing_s3_keys'] = discrepancies['db_keys_not_in_s3'][:20]
        
        if len(discrepancies['s3_keys_not_in_db']) > 0:
            detailed_results['sample_orphaned_s3_files'] = discrepancies['s3_keys_not_in_db'][:20]
        
        # Add database sample
        detailed_results['sample_db_records'] = list(self.db_videos.values())[:10]
        
        # Add S3 sample
        detailed_results['sample_s3_files'] = list(self.s3_videos.values())[:10]
        
        with open(filename, 'w') as f:
            json.dump(detailed_results, f, indent=2, default=str)
        
        logger.info(f"💾 Detailed results saved to: {filename}")
        return filename
    
    def run_full_analysis(self):
        """Run complete analysis pipeline"""
        logger.info("🚀 Starting comprehensive database vs S3 analysis...")
        
        # Step 1: Load data
        self.db_videos = self.get_database_videos()
        self.s3_videos = self.get_s3_videos()
        
        # Step 2: Analyze discrepancies
        self.analysis_results = self.analyze_discrepancies()
        
        # Step 3: Generate and display report
        report = self.generate_report()
        print(report)
        
        # Step 4: Save detailed results
        json_file = self.save_detailed_results()
        
        logger.info("✅ Analysis complete!")
        return {
            'report': report,
            'results': self.analysis_results,
            'json_file': json_file
        }


def main():
    """Main function"""
    analyzer = DatabaseS3Analyzer()
    results = analyzer.run_full_analysis()
    
    print(f"\n💡 Next steps:")
    print(f"   • Review detailed results: {results['json_file']}")
    print(f"   • Fix S3 key mismatches if needed")
    print(f"   • Run transcription for ready videos")


if __name__ == "__main__":
    main()