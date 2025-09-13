#!/usr/bin/env python3
"""Update database schema to support timestamp segments"""

import sqlite3
import sys
import os

def update_schema(db_path: str):
    """Add segments column to videos table if it doesn't exist"""
    
    if not os.path.exists(db_path):
        print(f"Database not found: {db_path}")
        return False
    
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            # Check current schema
            cursor.execute("PRAGMA table_info(videos)")
            columns = [row[1] for row in cursor.fetchall()]
            
            print(f"Current columns in videos table:")
            for col in columns:
                print(f"  - {col}")
            
            # Check if segments column exists
            if 'segments' not in columns:
                print("\nAdding 'segments' column to store timestamp data...")
                cursor.execute("""
                    ALTER TABLE videos 
                    ADD COLUMN segments TEXT
                """)
                conn.commit()
                print("✅ Successfully added 'segments' column")
            else:
                print("\n✅ 'segments' column already exists")
            
            # Check if word_timestamps column exists
            if 'word_timestamps' not in columns:
                print("\nAdding 'word_timestamps' column...")
                cursor.execute("""
                    ALTER TABLE videos 
                    ADD COLUMN word_timestamps TEXT
                """)
                conn.commit()
                print("✅ Successfully added 'word_timestamps' column")
            else:
                print("✅ 'word_timestamps' column already exists")
            
            # Check if has_timestamps column exists
            if 'has_timestamps' not in columns:
                print("\nAdding 'has_timestamps' column...")
                cursor.execute("""
                    ALTER TABLE videos 
                    ADD COLUMN has_timestamps BOOLEAN DEFAULT 0
                """)
                conn.commit()
                print("✅ Successfully added 'has_timestamps' column")
            else:
                print("✅ 'has_timestamps' column already exists")
            
            # Verify changes
            print("\nFinal schema:")
            cursor.execute("PRAGMA table_info(videos)")
            for row in cursor.fetchall():
                col_name = row[1]
                col_type = row[2]
                print(f"  - {col_name} ({col_type})")
            
            return True
            
    except Exception as e:
        print(f"Error updating schema: {e}")
        return False

def main():
    """Main function"""
    # Check multiple database locations
    db_paths = [
        'test_videos.db',
        '../../library_scrape/library_videos.db',
        '../library_scrape/library_videos.db',
        'library_videos.db'
    ]
    
    updated_count = 0
    
    for db_path in db_paths:
        if os.path.exists(db_path):
            print(f"\nUpdating database: {db_path}")
            print("="*60)
            if update_schema(db_path):
                updated_count += 1
            print()
    
    if updated_count == 0:
        print("No databases found to update!")
        sys.exit(1)
    else:
        print(f"\n✅ Successfully updated {updated_count} database(s)")

if __name__ == "__main__":
    main()