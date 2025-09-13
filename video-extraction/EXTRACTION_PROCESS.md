# ObjectivePersonality Video Extraction Process

## Overview
This document details the complete process used to successfully extract and download the "Lead Ne Self Fulfilling Fears" video from ObjectivePersonality's protected video library.

## Initial Challenge
The user requested extraction of a video from: `https://www.objectivepersonality.com/videos/lead-se-self-fulfilling-fears`

This page required authentication and the video hosting platform was initially unknown.

## Step 1: Authentication Analysis

### Source Material
Analyzed the authentication mechanism from `/Users/Mike/Xenodex/celebrity_archive_scrape/get_all_celebrities.py`

### Key Authentication Components
1. **Cookie-based Session Authentication**:
   - `svSession` - Wix session cookie
   - `smSession` - Secondary session 
   - `XSRF-TOKEN` - CSRF protection
   - `bSession` - Additional session data
   - `hs` cookies - Various tracking/session data

2. **Authorization Headers**:
   ```python
   headers = {
       'authorization': f'Bearer {wix_auth_token}',  # JWT token
       'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
       'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
       'Accept-Language': 'en-US,en;q=0.9',
   }
   ```

### Cookie Source
Used existing cookies from: `/Users/Mike/Xenodex/celebrity_archive_scrape/cookies.json`

## Step 2: Page Access and Initial Analysis

### Created: `simple_video_scraper.py`
```python
#!/usr/bin/env python3
import requests
import json
from pathlib import Path
from bs4 import BeautifulSoup

class VideoPageScraper:
    def __init__(self):
        self.cookies = self.load_cookies()
        
    def load_cookies(self):
        cookie_path = Path("/Users/Mike/Xenodex/celebrity_archive_scrape/cookies.json")
        with open(cookie_path, 'r') as f:
            return json.load(f)
    
    def scrape_page(self, url):
        session = requests.Session()
        
        # Add cookies
        for cookie in self.cookies:
            session.cookies.set(cookie['name'], cookie['value'])
            
        # Set headers
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://www.objectivepersonality.com/'
        })
        
        response = session.get(url)
        return response
```

### Results
- ✅ Successfully accessed the protected page
- 📄 Page size: 1,267,951 bytes
- 🔍 Found Wix data structures but no direct video elements

## Step 3: Initial Video Platform Investigation

### First Assumption: Cloudflare Stream
Found iframe elements with Cloudflare Stream IDs in the HTML:
- `72f9a2baadc044aa987408b831c5f444`
- `7c9b4b3ee81d49c3bebab0bc29dba4d2` 
- `3287270d83ef4efabfdd1f52d0dc6ec2`

### Created: `cloudflare_stream_extractor.py`
Tested various Cloudflare Stream URL patterns:
```python
urls_to_test = {
    'stream_manifest': f"https://customer-igynxd2rwhmuoxw8.cloudflarestream.com/{video_id}/manifest/video.m3u8",
    'dash_manifest': f"https://customer-igynxd2rwhmuoxw8.cloudflarestream.com/{video_id}/dash/video.mpd",
    'mp4_download': f"https://customer-igynxd2rwhmuoxw8.cloudflarestream.com/{video_id}/downloads/default.mp4",
    'iframe_embed': f"https://iframe.cloudflarestream.com/{video_id}",
    'thumbnails': f"https://customer-igynxd2rwhmuoxw8.cloudflarestream.com/{video_id}/thumbnails/thumbnail.jpg",
    'subtitles_vtt': f"https://customer-igynxd2rwhmuoxw8.cloudflarestream.com/{video_id}/captions/en/subtitles.vtt",
}
```

### Results
- ❌ All direct video URLs returned 404 "video not found"
- ✅ Iframe embeds worked but showed "video not found" message
- 🤔 Realized these were likely image/thumbnail IDs, not video IDs

## Step 4: Discovery of Actual Video Platform

### Breakthrough: Streamable.com
Further HTML analysis revealed thumbnail URLs pointing to Streamable:
```html
https://cdn-cf-east.streamable.com/image/026oep-screenshot469864.jpg
```

### Key Discovery
The actual video IDs were embedded in these thumbnail URLs:
- `57f8kw` - David Harbour
- `j2591a` - David Harbour Next  
- `5cg6aa` - Christopher Reeve
- `026oep` - **Lead Ne Self Fulfilling Fears** (OUR TARGET!)
- `047i2a` - Observer / Decider Tidal Waves
- `mpabxh` - Rob McElhenney: Observer vs Decider

## Step 5: Streamable Video Extraction

### Created: `streamable_video_extractor.py`

#### Key Streamable URLs Tested
```python
urls_to_test = {
    'streamable_page': f"https://streamable.com/{video_id}",
    'streamable_embed': f"https://streamable.com/e/{video_id}",
    'streamable_json': f"https://api.streamable.com/videos/{video_id}",  # ✅ JACKPOT!
    'streamable_mp4_direct': f"https://cdn-cf-east.streamable.com/video/mp4/{video_id}.mp4", 
    'streamable_webm_direct': f"https://cdn-cf-east.streamable.com/video/webm/{video_id}.webm",
    'thumbnail_image': f"https://cdn-cf-east.streamable.com/image/{video_id}.jpg"
}
```

#### Critical Success: Streamable JSON API
The URL `https://api.streamable.com/videos/026oep` returned complete video metadata:

```json
{
  "status": 2,
  "percent": 100,
  "title": "387) Lead Ne Self Fulfilling Fears",
  "files": {
    "mp4": {
      "status": 2,
      "url": "https://cdn-cf-east.streamable.com/video/mp4/026oep.mp4?Expires=1757555279207&Key-Pair-Id=APKAIEYUVEN4EVB2OKEQ&Signature=...",
      "framerate": 30,
      "height": 1080,
      "width": 1920,
      "bitrate": 4638877,
      "size": 2877405231,
      "duration": 4962.210333
    },
    "mp4-mobile": {
      "url": "https://cdn-cf-east.streamable.com/video/mp4-mobile/026oep.mp4?Expires=1757555279211&Key-Pair-Id=APKAIEYUVEN4EVB2OKEQ&Signature=..."
    }
  }
}
```

### Key Insights
1. **Signed URLs**: Streamable uses time-limited signed URLs with AWS CloudFront
2. **Multiple Formats**: Both high-quality (1080p) and mobile (360p) versions available
3. **Complete Metadata**: Duration (82.7 minutes), file size (2.74 GB), resolution, etc.

## Step 6: Video Download Implementation

### Created: `download_video.py`

#### Core Download Logic
```python
def download_video():
    # Load the JSON metadata
    with open("streamable_026oep_streamable_json.json", 'r') as f:
        data = json.load(f)
    
    # Extract signed URL
    video_url = data.get('files', {}).get('mp4', {}).get('url')
    
    # Download with progress tracking
    response = requests.get(video_url, stream=True)
    
    with open(filename, 'wb') as f:
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)
                # Progress updates every 10MB
```

#### Final Results
- ✅ **File**: `387 Lead Ne Self Fulfilling Fears.mp4`
- 📦 **Size**: 2,877,405,231 bytes (2.74 GB)
- ⏱️ **Download Time**: 2.0 minutes
- 🚀 **Average Speed**: 23.2 MB/s
- 🎥 **Quality**: 1920x1080 @ 30fps
- ⏰ **Duration**: 4962 seconds (82.7 minutes)

## Step 7: Transcript Search

### Transcript URLs Tested
```python
transcript_urls = [
    f"https://streamable.com/{video_id}/captions.vtt",
    f"https://streamable.com/{video_id}/subtitles.srt", 
    f"https://cdn-cf-east.streamable.com/captions/{video_id}.vtt",
    f"https://cdn-cf-east.streamable.com/subtitles/{video_id}.srt"
]
```

### Results
- ❌ No transcript files found at standard Streamable locations
- 🔍 May require additional API exploration or different URL patterns

## Success Factors

### 1. Authentication Reuse
- Leveraging existing authenticated cookies from celebrity scraper
- Understanding Wix-based authentication system

### 2. Platform Discovery
- Not assuming initial video platform (Cloudflare Stream was wrong)
- Following thumbnail URL clues to discover Streamable

### 3. API Exploration
- Testing multiple URL patterns systematically
- Finding the Streamable JSON API endpoint

### 4. Signed URL Handling
- Understanding AWS CloudFront signed URL structure
- Using time-limited URLs before expiration

## File Structure Created

```
/Users/Mike/Xenodex/library_scrape/
├── simple_video_scraper.py              # Initial page scraper
├── cloudflare_stream_extractor.py       # Failed Cloudflare attempt
├── streamable_video_extractor.py        # Successful Streamable extractor
├── download_video.py                    # Final downloader
├── streamable_026oep_streamable_json.json # Video metadata
├── 387 Lead Ne Self Fulfilling Fears.mp4  # Downloaded video (2.74 GB)
├── cloudflare_stream_results.json       # Failed attempts log
└── EXTRACTION_PROCESS.md                # This documentation
```

## Key Lessons Learned

1. **Don't Assume Video Platform**: Initial iframe analysis led to wrong platform
2. **Look for Thumbnail Clues**: Thumbnail URLs contained the real video IDs
3. **Test API Endpoints**: The JSON API was the key to getting signed URLs
4. **Authentication Persistence**: Existing cookies worked across different scraping targets
5. **Signed URLs Have Expiration**: Act quickly on time-limited download URLs

## Future Applications

This methodology can be applied to:
- Other ObjectivePersonality videos using different Streamable IDs
- Any Wix-based video platforms with similar authentication
- Streamable-hosted content on other sites

## Transcript Investigation Required

The transcript search needs further investigation. Potential approaches:
- Web search for Streamable transcript API patterns
- Check if ObjectivePersonality stores transcripts separately
- Investigate video player JavaScript for transcript endpoints