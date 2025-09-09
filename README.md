# Library Video Scraper

This scraper extracts all videos from the Objective Personality library (https://www.objectivepersonality.com/library).

## Current Status

- ✅ 39 videos scraped from page 1
- 📊 Database: `/Users/Mike/Xenodex/library_scrape/library_videos.db`
- 🎯 Total expected: ~1,911 videos (39 videos × 49 pages)

## How to Scrape All Videos

### Prerequisites

1. **Chrome with Remote Debugging**:
   ```bash
   # Make sure Chrome is running with debug port
   /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222
   ```

2. **Login to the Library**:
   - Open https://www.objectivepersonality.com/library
   - Make sure you're logged in with proper membership access
   - Keep the tab open

3. **Activate Python Environment**:
   ```bash
   source venv/bin/activate
   ```

### Running the Full Scraper

```bash
# Scrape all 49 pages
python scrape_all_library_videos.py

# Or scrape specific pages
python scrape_all_library_videos.py
# Then enter start page: 2
# And end page: 49
```

The scraper will:
- Navigate through each page automatically
- Extract all video metadata
- Save to the SQLite database
- Show progress for each page
- Wait 3 seconds between pages to be respectful

### Estimated Time

- ~5-8 seconds per page
- Total time for all 49 pages: ~4-7 minutes

### Database Schema

```sql
CREATE TABLE videos (
    id TEXT PRIMARY KEY,
    title TEXT,
    description TEXT,
    duration TEXT,
    upload_date TEXT,
    video_url TEXT,
    thumbnail_url TEXT,
    tags TEXT,
    category TEXT,
    data_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    local_filename TEXT
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