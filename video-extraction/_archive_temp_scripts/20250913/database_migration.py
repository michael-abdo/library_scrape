#!/usr/bin/env python3
"""
Database Migration Script - Add transcription_service column
Adds transcription_service column to videos table to track which service was used
"""
import sqlite3
import os
from pathlib import Path

def find_database():
    """Find the database file in possible locations"""
    possible_paths = [
        # Main library database (1,903 videos)
        "../library_scrape/library_videos.db",
        "../../library_scrape/library_videos.db", 
        "../../../library_scrape/library_videos.db",
        "/home/Mike/projects/Xenodex/ops_scraping/library_scrape/library_videos.db",
        # Fallback paths
        "../library_videos.db", 
        "../../library_videos.db",
        "/Users/Mike/Xenodx/library_scrape/library_videos.db",
        "library_videos.db",
        "../video_database.db",
        "video_database.db"
    ]
    
    for db_path in possible_paths:
        if os.path.exists(db_path):
            return db_path
            
    return None

def check_column_exists(cursor, table_name, column_name):
    """Check if a column exists in the table"""
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [row[1] for row in cursor.fetchall()]
    return column_name in columns

def check_table_exists(cursor, table_name):
    """Check if a table exists in the database"""
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
    return cursor.fetchone() is not None

def migrate_database():
    """Add transcription_service column to videos table"""
    
    # Find database
    db_path = find_database()
    if not db_path:
        print("❌ No database found. Please create the videos table first.")
        return False
    
    print(f"📁 Found database: {db_path}")
    
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            # Check if videos table exists
            if not check_table_exists(cursor, 'videos'):
                print("⚠️  Videos table does not exist. Creating it...")
                
                # Create videos table with all necessary columns
                cursor.execute("""
                    CREATE TABLE videos (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        title TEXT,
                        video_url TEXT,
                        s3_key TEXT,
                        s3_bucket TEXT,
                        storage_mode TEXT,
                        streamable_id TEXT,
                        local_filename TEXT,
                        transcript TEXT,
                        transcription_confidence REAL,
                        transcription_service TEXT,
                        downloaded_at DATETIME,
                        transcribed_at DATETIME,
                        created_at DATETIME DEFAULT (datetime('now')),
                        updated_at DATETIME DEFAULT (datetime('now'))
                    )
                """)
                
                print("✅ Created videos table with transcription_service column")
                
            else:
                # Check if transcription_service column exists
                if check_column_exists(cursor, 'videos', 'transcription_service'):
                    print("✅ transcription_service column already exists")
                    return True
                
                print("📝 Adding transcription_service column to existing videos table...")
                
                # Add the transcription_service column
                cursor.execute("""
                    ALTER TABLE videos ADD COLUMN transcription_service TEXT
                """)
                
                print("✅ Added transcription_service column")
            
            # Show current table structure
            cursor.execute("PRAGMA table_info(videos)")
            columns = cursor.fetchall()
            
            print("\n📊 Current videos table schema:")
            for column in columns:
                print(f"   {column[1]} ({column[2]})")
            
            # Show statistics
            cursor.execute("SELECT COUNT(*) FROM videos")
            total_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM videos WHERE transcription_service IS NOT NULL")
            with_service = cursor.fetchone()[0]
            
            print(f"\n📈 Database statistics:")
            print(f"   Total videos: {total_count}")
            print(f"   With service info: {with_service}")
            print(f"   Ready for OpenAI/Google service tracking: ✅")
            
            conn.commit()
            return True
            
    except Exception as e:
        print(f"❌ Migration error: {e}")
        return False

def main():
    """Run database migration"""
    print("🔄 Database Migration: Adding transcription_service column")
    print("=" * 60)
    
    success = migrate_database()
    
    if success:
        print("\n✅ Migration completed successfully!")
        print("\n💡 You can now track which transcription service was used:")
        print("   - 'openai': OpenAI Whisper API ($0.006/minute)")
        print("   - 'google': Google Speech-to-Text ($0.036-0.048/minute)")
        print("   - NULL: Legacy transcriptions (pre-service tracking)")
    else:
        print("\n❌ Migration failed!")
        return 1
    
    return 0

if __name__ == "__main__":
    import sys
    sys.exit(main())