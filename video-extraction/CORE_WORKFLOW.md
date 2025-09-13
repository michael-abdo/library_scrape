# Core Video Transcription Workflow

This directory contains the essential scripts for the video transcription workflow. All temporary migration and analysis scripts have been archived.

## Core Scripts

### 1. **transcribe_s3_videos.py**
Main orchestration script that:
- Fetches videos from the database that need transcription
- Downloads videos from S3
- Sends them to transcription services
- Uploads transcripts back to S3
- Updates database with transcript links

### 2. **openai_whisper_transcriber.py**
OpenAI Whisper API integration:
- Primary transcription service (87.5% cost savings)
- Supports timestamp generation
- Handles audio chunking for large files

### 3. **google_gpu_transcriber.py**
Google Cloud Speech-to-Text integration:
- Alternative transcription service
- Used as fallback option
- GPU-accelerated transcription

### 4. **s3_manager.py**
S3 operations manager:
- Upload/download files to/from S3
- Generate presigned URLs
- Stream large files efficiently
- Default bucket: `xenodx-video-archive`

### 5. **upload_transcripts_to_s3.py**
Standalone script to:
- Upload existing local transcripts to S3
- Update database with S3 links
- Handle various transcript formats (txt, vtt, json)

### 6. **transcription_config.py**
Central configuration for:
- API keys and credentials
- Service-specific settings
- Transcription parameters

### 7. **unified_video_processor.py**
Video extraction and processing:
- Extract videos from various sources
- Upload to S3 for transcription
- Handle different video formats

## Workflow Overview

```
1. Video Discovery → unified_video_processor.py
   ↓
2. Video Upload to S3 → s3_manager.py
   ↓
3. Transcription → transcribe_s3_videos.py
   ├── OpenAI Whisper → openai_whisper_transcriber.py
   └── Google Speech → google_gpu_transcriber.py
   ↓
4. Transcript Upload → upload_transcripts_to_s3.py / s3_manager.py
   ↓
5. Database Update → (integrated in scripts)
```

## Running the Workflow

```bash
# Set environment variables
export AWS_PROFILE=zenex
export S3_BUCKET=xenodx-video-archive

# Run transcription for videos without transcripts
python3 transcribe_s3_videos.py

# Upload existing transcripts to S3
python3 upload_transcripts_to_s3.py
```

## Archived Scripts

All temporary, migration, and analysis scripts have been moved to:
`_archive_temp_scripts/20250913/`

This includes one-time use scripts for:
- Database migrations
- S3 bucket migrations
- Cost analysis
- Debugging tools
- Data verification scripts