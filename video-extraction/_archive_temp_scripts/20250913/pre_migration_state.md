# Pre-Migration State Documentation
Generated: 2025-09-13 17:16:00 UTC

## Current Transcript Locations

### Source Bucket: op-videos-storage
- **Total Files**: 501
- **Total Size**: 11.0 MB
- **S3 Path**: s3://op-videos-storage/transcripts/

### Directory Structure:
```
transcripts/
├── archive/no_timestamps/  (10 files, ~2.4KB)
├── aws/                    (2 files, ~727KB)
├── classes/                (4 files, ~0.9KB)
├── other/                  (7 files, ~2.2KB)
├── qa/                     (2 files, ~0.3KB)
├── txt/                    (235 files, ~5.1MB)
└── vtt/                    (241 files, ~5.4MB)
```

### Target Bucket: xenodx-video-archive
- **Current transcripts**: 8 JSON files
- **S3 Path**: s3://xenodx-video-archive/transcripts/

## File Formats Found:
- `.txt` - Plain text transcripts (258 files)
- `.vtt` - WebVTT subtitle files (241 files)
- `.json` - JSON transcripts (2 files)

## Backup Information:
- **Source file list backup**: source_transcript_files_backup.txt
- **Migration report**: transcript_migration_report_20250913_171404.json

## Rollback Plan:
If migration needs to be reversed:
1. Delete migrated files from xenodx-video-archive using the migration report
2. Original files remain untouched in op-videos-storage
3. Revert any database updates using backup
4. Revert any script changes using git

## Notes:
- No naming conflicts detected in target bucket
- Estimated migration cost: $0.0027
- Estimated migration time: 4.2 minutes