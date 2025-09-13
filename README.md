# Objective Personality Video Processing System

This system extracts, downloads, and processes videos from the Objective Personality library, uploading them to AWS S3 with database tracking.

## Current Status (Updated 2025-09-13)

- ✅ **1,903 videos** with Streamable IDs in database
- ✅ **773 videos** (40.6%) uploaded to S3  
- 🎯 **1,130 videos** (59.4%) remaining to process
- 📊 Database: `library_videos.db`
- ☁️ **S3 Storage**: `s3://op-videos-storage/objectivepersonality/videos/`

## Quick Start - Process Videos to S3

### Prerequisites

1. **AWS Credentials** (zenex profile configured):
   ```bash
   aws configure --profile zenex
   aws --profile zenex s3 ls s3://op-videos-storage/
   ```

### Processing Videos

**Recommended: Use Unified Processor**
```bash
# Process 200 videos with known Streamable IDs
python3 video-extraction/unified_video_processor.py --limit 200 --streamable

# Process ALL remaining videos (1,130)
python3 video-extraction/unified_video_processor.py --streamable

# Show database status
python3 video-extraction/unified_video_processor.py --status
```

**Alternative: Direct S3 Upload** (no database updates)
```bash
# Process N videos directly
python3 streamable_to_s3.py --200

# Test with 5 videos  
python3 streamable_to_s3.py --test
```

### Monitoring Progress

```bash
# Check database status
sqlite3 library_videos.db "SELECT COUNT(*) FROM videos WHERE s3_key IS NOT NULL;"

# Check S3 uploads
aws --profile zenex s3 ls s3://op-videos-storage/objectivepersonality/videos/ --recursive | wc -l
```

## Video Scraping (Initial Setup)

### Prerequisites for New Videos

1. **Chrome with Remote Debugging**:
   ```bash
   # Make sure Chrome is running with debug port
   /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222
   ```

2. **Login to the Library**:
   - Open https://www.objectivepersonality.com/library
   - Make sure you're logged in with proper membership access
   - Keep the tab open

### Running the Full Scraper

```bash
# Scrape all 49 pages
python scrape_all_library_videos.py
```

The scraper will:
- Navigate through each page automatically
- Extract all video metadata and Streamable IDs
- Save to the SQLite database
- Show progress for each page

## System Architecture

### Processing Pipeline
1. **Video Scraping**: Extract video metadata and Streamable IDs from OP library
2. **Streamable Download**: Get videos from Streamable's CDN using API
3. **S3 Upload**: Stream directly to AWS S3 storage (no local storage)
4. **Database Update**: Track S3 keys and metadata in SQLite

### Key Scripts
- `video-extraction/unified_video_processor.py` - **Complete workflow with database updates**
- `streamable_to_s3.py` - Direct Streamable to S3 upload  
- `scrape_all_library_videos.py` - Initial video metadata extraction

### Database Schema

```sql
CREATE TABLE videos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT,
    video_url TEXT,                 -- ObjectivePersonality URL
    s3_key TEXT,                    -- S3 object path (set after upload)
    s3_bucket TEXT,                 -- S3 bucket name
    storage_mode TEXT,              -- 's3' after successful upload
    streamable_id TEXT,             -- Streamable video ID (e.g., 'u189o6')
    local_filename TEXT,
    transcript TEXT,
    downloaded_at DATETIME,         -- Upload timestamp
    created_at DATETIME DEFAULT (datetime('now')),
    updated_at DATETIME DEFAULT (datetime('now'))
);
```

### Checking Progress

```bash
# Check total videos in database
sqlite3 library_videos.db "SELECT COUNT(*) FROM videos;"

# Check which pages have been scraped
sqlite3 library_videos.db "SELECT DISTINCT substr(id, 5, instr(substr(id, 5), '_') - 1) as page FROM videos ORDER BY CAST(page AS INTEGER);"

# Export all videos to CSV
sqlite3 -header -csv library_videos.db "SELECT * FROM videos;" > library_videos.csv
```

## Technical Details

### Why No Collection ID?

After extensive investigation, we discovered:
- Library videos use **custom Velo/Corvid implementation**
- Videos are **server-side rendered** into HTML
- No standard Wix cloud-data API calls are made
- The repeater is populated at build/render time, not dynamically

This is why we use HTML scraping instead of the API approach used for celebrity archive.

### Files Created

- `library_videos.db` - SQLite database with all videos
- `scrape_all_library_videos.py` - Main scraper for all pages
- `chrome_websocket.py` - Chrome DevTools integration
- `velo_bundle.js` - Downloaded Velo bundle (for investigation)
- Various investigation scripts