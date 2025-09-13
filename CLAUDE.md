# Claude Code Instructions

This document contains instructions and context for Claude when working with the Objective Personality video processing system.

## System Overview

This system processes videos from the Objective Personality library by:
1. Extracting Streamable video IDs from ObjectivePersonality pages
2. Downloading videos from Streamable's CDN
3. Uploading videos to AWS S3 storage
4. Updating database records with S3 metadata

## Current Status (Updated 2025-09-13)

### Database Statistics
- **Total videos**: 1,903 with Streamable IDs
- **Uploaded to S3**: 773 videos (40.6%)
- **Need processing**: 1,130 videos (59.4%)

### Working Systems
- ✅ **S3 Access**: Using `zenex` AWS profile with `op-videos-storage` bucket
- ✅ **Streamable Download**: Fixed CDN URL parsing to use API responses
- ✅ **Database Updates**: Unified processor updates s3_key after uploads

### Known Issues
- ❌ **Streamable ID Extraction**: Chrome debug and cookie methods failing for new videos
- ❌ **Network DNS**: cdn.streamable.com doesn't exist (fixed: now uses dynamic URLs)

## Key Scripts

### 1. unified_video_processor.py (RECOMMENDED)
**Location**: `video-extraction/unified_video_processor.py`

**Purpose**: Complete end-to-end video processing with database updates

**Usage**:
```bash
# Process videos with known Streamable IDs (bypasses extraction issues)
python3 unified_video_processor.py --limit 200 --streamable

# Process ALL remaining videos with known Streamable IDs
python3 unified_video_processor.py --streamable

# Show database status
python3 unified_video_processor.py --status

# Process single video by Streamable ID
python3 unified_video_processor.py u189o6
```

**Features**:
- ✅ Direct S3 streaming (no local storage)
- ✅ Database updates with S3 metadata
- ✅ Progress tracking and upload verification
- ✅ Handles videos with known Streamable IDs
- ✅ Robust error handling

### 2. streamable_to_s3.py (ALTERNATIVE)
**Location**: `streamable_to_s3.py`

**Purpose**: Direct Streamable to S3 upload (no database updates)

**Usage**:
```bash
# Process N videos with known Streamable IDs
python3 streamable_to_s3.py --200

# Test with 5 videos
python3 streamable_to_s3.py --test
```

**Note**: Does not update database with S3 keys - use unified processor instead.

## AWS Configuration

### Profile: zenex
```bash
aws configure --profile zenex
```

### S3 Bucket: op-videos-storage
- Region: us-east-1
- Path structure: `s3://op-videos-storage/objectivepersonality/videos/{streamable_id}/{filename}.mp4`

### Testing S3 Access
```bash
aws --profile zenex s3 ls s3://op-videos-storage/objectivepersonality/videos/
```

## Database Schema

### Key Fields
- `streamable_id`: Streamable video identifier (e.g., "u189o6")
- `s3_key`: S3 object path (set after successful upload)
- `s3_bucket`: S3 bucket name
- `storage_mode`: Set to 's3' after upload
- `downloaded_at`: Upload timestamp

### Useful Queries
```sql
-- Count videos needing processing
SELECT COUNT(*) FROM videos 
WHERE streamable_id IS NOT NULL 
AND streamable_id != 'MANUAL_CHECK_REQUIRED'
AND (s3_key IS NULL OR s3_key = '');

-- Count videos already in S3
SELECT COUNT(*) FROM videos 
WHERE s3_key IS NOT NULL AND s3_key != '';

-- Find videos for processing
SELECT streamable_id, title FROM videos 
WHERE streamable_id IS NOT NULL 
AND (s3_key IS NULL OR s3_key = '')
LIMIT 10;
```

## Troubleshooting

### Common Issues
1. **AWS Credentials**: Use `zenex` profile, not default
2. **DNS Resolution**: Scripts now use dynamic CDN URLs from API
3. **S3 Bucket**: Use `op-videos-storage`, not `xenodx-videos`
4. **Database Path**: Use `library_videos.db` in current directory

### Error Resolution
```bash
# Test AWS access
aws --profile zenex sts get-caller-identity

# Test S3 access
aws --profile zenex s3 ls s3://op-videos-storage/

# Check database
sqlite3 library_videos.db "SELECT COUNT(*) FROM videos;"
```

## Recent Fixes (2025-09-13)

1. **Fixed S3 Access**: Updated to use `zenex` profile and correct bucket
2. **Fixed Streamable CDN**: Removed hardcoded cdn.streamable.com, now uses API responses
3. **Added --streamable Flag**: Unified processor can now bypass extraction for known IDs
4. **Fixed Database Path**: Scripts now find correct database file

## Processing Large Batches

For processing hundreds of videos:

```bash
# Process in background with logging
nohup python3 unified_video_processor.py --limit 500 --streamable > upload_500.log 2>&1 &

# Monitor progress
tail -f upload_500.log

# Check S3 uploads
aws --profile zenex s3 ls s3://op-videos-storage/objectivepersonality/videos/ | wc -l
```

## Next Steps

1. **Process remaining 1,130 videos** using unified processor with --streamable flag
2. **Fix Streamable ID extraction** for processing new ObjectivePersonality videos
3. **Implement transcription workflow** using existing S3 videos