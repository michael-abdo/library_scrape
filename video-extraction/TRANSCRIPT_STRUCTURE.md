# Transcript Storage Structure Documentation
Last Updated: 2025-09-13

## Overview

All transcripts have been migrated to a unified storage structure within the `xenodx-video-archive` S3 bucket. This consolidation simplifies access and management of all media assets.

## S3 Bucket Structure

```
xenodx-video-archive/
├── videos/               # Video files (existing)
└── transcripts/          # All transcript files (migrated)
    ├── txt/              # Plain text transcripts (258 files)
    │   ├── classes/      # Class-related transcripts (4 files)
    │   ├── other/        # Other category transcripts (7 files)
    │   ├── qa/           # Q&A transcripts (2 files)
    │   └── *.txt         # Main transcript files (235 files)
    ├── vtt/              # WebVTT subtitle files (241 files)
    │   └── *.vtt         # WebVTT format files with timestamps
    ├── json/             # JSON transcripts (9 files)
    │   ├── aws/          # AWS Transcribe format (1 file)
    │   └── *.json        # JSON format transcripts with metadata
    └── archive/          # Archived/legacy transcripts (10 files)
        └── *.txt         # Old format transcripts without timestamps
```

## File Formats

### TXT Files
- **Location**: `transcripts/txt/`
- **Format**: Plain text with VTT-style timestamps
- **Example**: `220.1_Ventura.txt`
- **Content**: Human-readable transcripts with time codes

### VTT Files
- **Location**: `transcripts/vtt/`
- **Format**: WebVTT (Web Video Text Tracks)
- **Example**: `auto_generated_captions (1).vtt`
- **Content**: Subtitle files with precise timestamps for video synchronization

### JSON Files
- **Location**: `transcripts/json/`
- **Format**: JSON with detailed metadata
- **Example**: `transcript_with_timestamps.json`
- **Content**: Structured data including segments, word-level timestamps, confidence scores

## Access Methods

### Direct S3 Access
```bash
# List all transcripts
aws s3 ls s3://xenodx-video-archive/transcripts/ --recursive --profile zenex

# Download specific transcript
aws s3 cp s3://xenodx-video-archive/transcripts/txt/220.1_Ventura.txt . --profile zenex
```

### Presigned URLs
Use the `presign_s3_url.py` script to generate temporary access URLs:
```bash
python3 presign_s3_url.py "s3://xenodx-video-archive/transcripts/txt/example.txt"
```

### Python SDK
```python
from s3_manager import S3Manager

# Initialize with new bucket
s3 = S3Manager(bucket_name='xenodx-video-archive')

# Get presigned URL
url = s3.get_presigned_url('transcripts/txt/example.txt')
```

## Configuration Updates

### Environment Variables
```bash
# Set default bucket
export S3_BUCKET=xenodx-video-archive

# Set AWS profile
export AWS_PROFILE=zenex
```

### Database
- The `videos` table uses `transcript_s3_key` and `transcript_s3_url` fields
- URLs already point to `xenodx-video-archive` bucket
- No database migration required

### Python Scripts
- `s3_manager.py`: Updated default bucket to `xenodx-video-archive`
- Migration script: Available for future use in `migrate_transcripts_to_unified_bucket.py`

## Migration Details

- **Migration Date**: 2025-09-13
- **Files Migrated**: 501
- **Total Size**: 11.0 MB
- **Source**: `s3://op-videos-storage/transcripts/`
- **Target**: `s3://xenodx-video-archive/transcripts/`
- **Migration Time**: 62 seconds
- **Cost**: ~$0.0027

## Backup and Recovery

- **Original Files**: Preserved in `op-videos-storage` bucket
- **Database Backup**: `test_videos_backup_20250913_172600.db`
- **Migration Report**: `transcript_migration_report_20250913_172532.json`
- **File List Backup**: `source_transcript_files_backup.txt`

## Benefits

1. **Unified Storage**: Videos and transcripts in same bucket
2. **Organized Structure**: Clear directory hierarchy by file type
3. **Cost Efficiency**: Single bucket reduces management overhead
4. **Simplified Access**: All media assets in one location
5. **Consistent Naming**: Standardized file organization