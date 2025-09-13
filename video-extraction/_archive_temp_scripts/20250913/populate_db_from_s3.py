#!/usr/bin/env python3
"""Populate database with videos found in S3."""

import boto3
import sqlite3
import os
from datetime import datetime
from typing import List, Dict

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
                        # Extract title from filename
                        # Format: UUID/Title.mp4
                        parts = filename.split('/')
                        if len(parts) >= 2:
                            title = parts[1].replace('.mp4', '').replace('.webm', '')
                        else:
                            title = filename.replace('.mp4', '').replace('.webm', '')
                        
                        videos.append({
                            'key': key,
                            'filename': filename,
                            'title': title,
                            'size': obj['Size'],
                            'last_modified': obj['LastModified'],
                            'size_mb': round(obj['Size'] / (1024 * 1024), 2),
                            's3_url': f"https://{bucket_name}.s3.amazonaws.com/{key}"
                        })
        
        print(f"Found {len(videos)} videos in S3")
        return videos
        
    except Exception as e:
        print(f"Error listing S3 objects: {e}")
        return []

def populate_database(videos: List[Dict], db_path: str = 'test_videos.db'):
    """Populate database with S3 videos."""
    print(f"\nPopulating database: {db_path}")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Insert videos
    inserted_count = 0
    for video in videos:
        try:
            cursor.execute("""
                INSERT INTO videos (title, video_url, created_at)
                VALUES (?, ?, ?)
            """, (
                video['title'],
                video['s3_url'],
                datetime.now().isoformat()
            ))
            inserted_count += 1
            print(f"  Added: {video['title']} ({video['size_mb']} MB)")
        except sqlite3.IntegrityError as e:
            print(f"  Skipped (already exists): {video['title']}")
        except Exception as e:
            print(f"  Error inserting {video['title']}: {e}")
    
    conn.commit()
    conn.close()
    
    print(f"\nInserted {inserted_count} new videos into database")

def main():
    """Main function."""
    # List S3 videos
    s3_videos = list_s3_videos()
    
    if not s3_videos:
        print("No videos found in S3")
        return
    
    # Sort by size for better display
    s3_videos.sort(key=lambda x: x['size'])
    
    print("\nVideos found in S3:")
    for i, video in enumerate(s3_videos, 1):
        print(f"{i}. {video['title']} - {video['size_mb']} MB")
    
    # Populate database
    populate_database(s3_videos)
    
    print("\nDatabase populated. You can now run transcription processing.")

if __name__ == "__main__":
    main()