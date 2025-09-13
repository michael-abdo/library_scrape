#!/usr/bin/env python3
"""List all videos in S3 bucket and compare with database entries."""

import boto3
import sqlite3
import os
from typing import List, Dict, Tuple
from datetime import datetime

def list_s3_videos(bucket_name: str = 'xenodx-video-archive', prefix: str = 'videos/') -> List[Dict]:
    """List all video files in S3 bucket."""
    print(f"Listing videos in S3 bucket: {bucket_name} with prefix: {prefix}")
    
    # Use the zenex profile
    session = boto3.Session(profile_name='zenex')
    s3_client = session.client('s3')
    
    videos = []
    
    try:
        # List objects in bucket with pagination
        paginator = s3_client.get_paginator('list_objects_v2')
        page_iterator = paginator.paginate(
            Bucket=bucket_name,
            Prefix=prefix
        )
        
        for page in page_iterator:
            if 'Contents' in page:
                for obj in page['Contents']:
                    key = obj['Key']
                    # Skip if it's just the prefix folder
                    if key == prefix:
                        continue
                    
                    # Extract video filename
                    filename = key.replace(prefix, '')
                    if filename and (filename.endswith('.mp4') or filename.endswith('.webm')):
                        videos.append({
                            'key': key,
                            'filename': filename,
                            'size': obj['Size'],
                            'last_modified': obj['LastModified'],
                            'size_mb': round(obj['Size'] / (1024 * 1024), 2)
                        })
        
        print(f"Found {len(videos)} videos in S3")
        return videos
        
    except Exception as e:
        print(f"Error listing S3 objects: {e}")
        return []

def get_database_videos(db_path: str = 'test_videos.db') -> List[Dict]:
    """Get all videos from database."""
    print(f"Reading videos from database: {db_path}")
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get all videos with their transcription status
    query = """
    SELECT 
        v.id,
        v.title,
        v.video_url,
        v.transcript,
        v.transcription_confidence,
        v.transcription_service,
        v.transcribed_at,
        v.created_at
    FROM videos v
    ORDER BY v.id
    """
    
    cursor.execute(query)
    videos = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    print(f"Found {len(videos)} videos in database")
    return videos

def compare_s3_and_database(s3_videos: List[Dict], db_videos: List[Dict]) -> Dict:
    """Compare S3 contents with database entries."""
    # Create lookup dictionaries
    s3_by_filename = {v['filename']: v for v in s3_videos}
    
    # Extract S3 keys from database URLs
    db_s3_keys = []
    for db_video in db_videos:
        if db_video['video_url']:
            # Extract filename from video URL
            # Could be S3 URL or filename
            if 'amazonaws.com/' in db_video['video_url']:
                key = db_video['video_url'].split('amazonaws.com/')[-1]
                filename = key.replace('videos/', '')
                db_video['s3_filename'] = filename
                db_s3_keys.append(filename)
            elif db_video['video_url'].endswith('.mp4') or db_video['video_url'].endswith('.webm'):
                # Assume it's just a filename
                filename = db_video['video_url'].split('/')[-1]
                db_video['s3_filename'] = filename
                db_s3_keys.append(filename)
    
    # Find matches and mismatches
    s3_filenames = set(s3_by_filename.keys())
    db_filenames = set(db_s3_keys)
    
    # Videos in both S3 and database
    matched = s3_filenames.intersection(db_filenames)
    
    # Videos only in S3
    s3_only = s3_filenames - db_filenames
    
    # Videos only in database
    db_only = db_filenames - s3_filenames
    
    # Find videos that exist in S3 and need transcription
    need_transcription = []
    for db_video in db_videos:
        if 's3_filename' in db_video and db_video['s3_filename'] in matched:
            # Check if needs transcription (no transcript or empty)
            if not db_video['transcript'] or db_video['transcript'].strip() == '':
                need_transcription.append({
                    'db_video': db_video,
                    's3_video': s3_by_filename[db_video['s3_filename']]
                })
    
    return {
        'matched': matched,
        's3_only': s3_only,
        'db_only': db_only,
        'need_transcription': need_transcription,
        's3_videos': s3_videos,
        'db_videos': db_videos
    }

def print_report(comparison: Dict):
    """Print detailed comparison report."""
    print("\n" + "="*80)
    print("S3 vs Database Comparison Report")
    print("="*80)
    
    print(f"\nTotal videos in S3: {len(comparison['s3_videos'])}")
    print(f"Total videos in database: {len(comparison['db_videos'])}")
    
    print(f"\nVideos in both S3 and database: {len(comparison['matched'])}")
    print(f"Videos only in S3: {len(comparison['s3_only'])}")
    print(f"Videos only in database: {len(comparison['db_only'])}")
    
    # List videos that exist in S3 but not in database
    if comparison['s3_only']:
        print("\n--- Videos only in S3 (not in database) ---")
        for filename in sorted(comparison['s3_only'])[:10]:  # Show first 10
            s3_video = next(v for v in comparison['s3_videos'] if v['filename'] == filename)
            print(f"  {filename} ({s3_video['size_mb']} MB)")
        if len(comparison['s3_only']) > 10:
            print(f"  ... and {len(comparison['s3_only']) - 10} more")
    
    # List videos that are in database but not in S3
    if comparison['db_only']:
        print("\n--- Videos in database but NOT in S3 ---")
        for filename in sorted(comparison['db_only'])[:10]:  # Show first 10
            print(f"  {filename}")
        if len(comparison['db_only']) > 10:
            print(f"  ... and {len(comparison['db_only']) - 10} more")
    
    # List videos that need transcription
    print(f"\n--- Videos that exist in S3 and need transcription ---")
    print(f"Total: {len(comparison['need_transcription'])}")
    
    if comparison['need_transcription']:
        # Sort by size for efficient processing
        need_trans_sorted = sorted(comparison['need_transcription'], 
                                 key=lambda x: x['s3_video']['size'])
        
        for i, item in enumerate(need_trans_sorted[:10]):
            db_video = item['db_video']
            s3_video = item['s3_video']
            print(f"\n{i+1}. {db_video['title']}")
            print(f"   Video URL: {db_video['video_url']}")
            print(f"   S3 filename: {s3_video['filename']}")
            print(f"   Size: {s3_video['size_mb']} MB")
            print(f"   Has transcript: {'Yes' if db_video['transcript'] else 'No'}")
            if db_video['transcribed_at']:
                print(f"   Transcribed at: {db_video['transcribed_at']}")
        
        if len(comparison['need_transcription']) > 10:
            print(f"\n... and {len(comparison['need_transcription']) - 10} more videos need transcription")
    
    # Summary of transcription statuses
    print("\n--- Transcription Status Summary ---")
    transcribed_count = 0
    not_transcribed_count = 0
    
    for db_video in comparison['db_videos']:
        if db_video['transcript']:
            transcribed_count += 1
        else:
            not_transcribed_count += 1
    
    print(f"  Transcribed: {transcribed_count}")
    print(f"  Not transcribed: {not_transcribed_count}")

def main():
    """Main function."""
    # List S3 videos
    s3_videos = list_s3_videos()
    
    # Get database videos
    db_videos = get_database_videos()
    
    # Compare
    comparison = compare_s3_and_database(s3_videos, db_videos)
    
    # Print report
    print_report(comparison)
    
    # Return videos that need transcription for further processing
    return comparison['need_transcription']

if __name__ == "__main__":
    videos_to_process = main()
    
    # Save list of videos that need transcription
    if videos_to_process:
        print(f"\nFound {len(videos_to_process)} videos that need transcription")
        print("Run transcribe_s3_videos.py to process them")