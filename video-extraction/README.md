# ObjectivePersonality Video Downloader

A complete solution for downloading videos from ObjectivePersonality's protected video library.

## 🎯 What This Does

Downloads the "Lead Ne Self Fulfilling Fears" video (and potentially other videos) from ObjectivePersonality by:

1. **Authentication**: Uses existing cookies from celebrity scraper
2. **Video ID Extraction**: Finds Streamable video IDs from the OP page  
3. **Metadata Retrieval**: Gets signed download URLs from Streamable API
4. **Download**: Downloads the full HD video with progress tracking

## 📁 Files

- **`op_video_downloader.py`** - Original local downloader script
- **`op_video_downloader_s3.py`** - Enhanced version with S3 streaming support
- **`s3_manager.py`** - S3 operations manager for direct streaming
- **`config_manager.py`** - Configuration management for S3 and download settings
- **`EXTRACTION_PROCESS.md`** - Detailed documentation of discovery process  
- **`387 Lead Ne Self Fulfilling Fears.mp4`** - Downloaded video (2.74 GB)

## 🚀 Usage

**Batch Mode (download multiple videos):**
```bash
python3 op_video_downloader.py                    # Download all undownloaded videos
python3 op_video_downloader.py 3                  # Download up to 3 videos
python3 op_video_downloader.py --limit 5          # Download up to 5 videos
```

**Single Video Mode:**
```bash
python3 op_video_downloader.py <url>              # Download specific video
```

**Examples:**
```bash
# Batch modes
python3 op_video_downloader.py                    # Download all undownloaded videos
python3 op_video_downloader.py 2                  # Download up to 2 videos
python3 op_video_downloader.py --limit 10         # Download up to 10 videos

# Single video mode
python3 op_video_downloader.py "https://www.objectivepersonality.com/videos/lead-se-self-fulfilling-fears"
python3 op_video_downloader.py "https://www.objectivepersonality.com/videos/shan-typing%3A-selena-gomez"

# Status check
python3 op_video_downloader.py --status           # Show download statistics
```

### 🌟 S3 Streaming Mode (NEW)

**Direct streaming to AWS S3 without local storage:**
```bash
# S3 batch modes
python3 op_video_downloader_s3.py --s3                    # Download all to S3
python3 op_video_downloader_s3.py --s3 --limit 5          # Download 5 videos to S3

# S3 single video mode
python3 op_video_downloader_s3.py --s3 "https://www.objectivepersonality.com/videos/video-name"

# Status check (shows both local and S3 downloads)
python3 op_video_downloader_s3.py --status
```

**S3 Setup Requirements:**
1. AWS credentials configured (`aws configure` or environment variables)
2. S3 bucket created (default: `op-videos-storage`)
3. boto3 installed (`pip install boto3`)

**🔄 Database Integration:**
- **Dual storage tracking** - Separate tracking for local files and S3 objects
- **Tracks downloads** - Updates `library_videos.db` with storage location and status
- **Skips existing** - Won't re-download videos that already exist (local or S3)  
- **Batch processing** - Can download all undownloaded videos from the database
- **Progress tracking** - Shows download progress and batch statistics
- **S3 metadata** - Stores video metadata and S3 keys for cloud access

## 📋 Requirements

**Core Requirements:**
- Python 3.6+
- `requests`, `beautifulsoup4` libraries  
- Authentication cookies in `cookies.json` (from celebrity scraper)
- `library_videos.db` SQLite database with video URLs
- Write access to current directory for downloads

**Additional for S3 Mode:**
- `boto3` library (`pip install boto3`)
- AWS credentials configured
- S3 bucket with write permissions
- `pyyaml` for configuration (`pip install pyyaml`)

## ✅ Success Results

- **Video**: "387) Lead Ne Self Fulfilling Fears"
- **Size**: 2.74 GB  
- **Quality**: 1920x1080 @ 30fps
- **Duration**: 82.7 minutes
- **Download Speed**: ~23 MB/s

## ❌ Transcripts

**No transcripts available** - exhaustive search confirmed Streamable doesn't provide transcript/caption files for this video.

## 🔧 Technical Details

**Video Hosting**: Streamable.com (not Cloudflare Stream as initially thought)  
**Authentication**: Cookie-based with Wix authorization headers  
**Download URLs**: Time-limited AWS CloudFront signed URLs  
**Video ID**: `026oep` for "Lead Ne Self Fulfilling Fears"

## 🎉 Status: Complete & Working

This is a cleaned-up, production-ready version that successfully downloads the target video.