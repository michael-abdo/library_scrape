# Google GPU Video Transcription System

A production-ready system for extracting, uploading, and transcribing ObjectivePersonality videos using Google Cloud Speech-to-Text GPU acceleration.

## Architecture Overview

```
Video URL → Streamable ID Extraction → S3 Upload → Google GPU Transcription → Database Storage
```

## Core Components

### 1. `unified_video_processor.py` - Main Processing Pipeline
- **Purpose**: Complete workflow from video URL to transcribed content
- **Features**: 
  - Multi-method Streamable ID extraction (cookies + Chrome debug)
  - Direct S3 streaming (no local storage)
  - Integrated Google GPU transcription
  - Progress tracking and error recovery
  - Database updates with metadata

### 2. `google_gpu_transcriber.py` - Google Cloud Speech-to-Text Integration
- **Purpose**: High-accuracy video transcription using Google's GPU-accelerated models
- **Features**:
  - Support for multiple Google Speech models (chirp_2, latest_long, latest_short, video)
  - S3 presigned URL processing
  - Confidence scoring and error handling
  - Cost-effective transcription ($0.012/15s vs $0.44/min for OpenAI)

### 3. `transcription_config.py` - Google GPU Configuration
- **Purpose**: Centralized configuration for Google Cloud Speech-to-Text
- **Features**:
  - Model selection and optimization
  - Cost estimation utilities
  - Environment variable management
  - Validation and diagnostics

### 4. `s3_manager.py` - AWS S3 Storage Manager
- **Purpose**: Efficient video storage and access for transcription
- **Features**:
  - Direct streaming uploads (no local storage)
  - Presigned URL generation for secure access
  - Glacier Instant Retrieval for cost optimization
  - Progress tracking and metadata handling

## Quick Start

### Prerequisites

1. **Google Cloud Setup**:
   ```bash
   # Enable Cloud Speech-to-Text API
   gcloud services enable speech.googleapis.com
   
   # Create service account and download key
   gcloud iam service-accounts create transcription-service
   gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
     --member="serviceAccount:transcription-service@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
     --role="roles/speech.client"
   ```

2. **Environment Variables**:
   ```bash
   export GOOGLE_CLOUD_PROJECT="your-project-id"
   export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account-key.json"
   export AWS_ACCESS_KEY_ID="your-aws-key"
   export AWS_SECRET_ACCESS_KEY="your-aws-secret"
   export S3_BUCKET="your-s3-bucket"
   ```

3. **Install Dependencies**:
   ```bash
   pip install google-cloud-speech google-auth boto3 requests
   ```

### Basic Usage

#### Process Videos in Batch
```bash
# Process next 5 unprocessed videos
python3 unified_video_processor.py --limit 5

# Process all unprocessed videos
python3 unified_video_processor.py

# Check processing status
python3 unified_video_processor.py --status
```

#### Process Single Video
```bash
# By ObjectivePersonality URL
python3 unified_video_processor.py "https://www.objectivepersonality.com/video/..."

# By Streamable ID
python3 unified_video_processor.py "abc123"
```

#### Configuration Testing
```bash
# Test Google GPU transcription configuration
python3 transcription_config.py
```

## Configuration Options

### Google Speech Models

| Model | Accuracy | Speed | Cost/15s | Best For |
|-------|----------|-------|----------|----------|
| `chirp_2` | Highest | Fast | $0.012 | General use, multilingual |
| `latest_long` | High | Medium | $0.009 | Long-form content |
| `latest_short` | High | Fast | $0.009 | Short clips, real-time |
| `video` | High | Fast | $0.009 | Video-specific audio |

### Environment Configuration
```bash
# Google Cloud
GOOGLE_CLOUD_PROJECT="your-project-id"
GOOGLE_APPLICATION_CREDENTIALS="/path/to/key.json"
GOOGLE_SPEECH_MODEL="chirp_2"  # Default model
GOOGLE_SPEECH_LANGUAGE="en-US"

# Processing
TRANSCRIPTION_BATCH_SIZE="10"  # Videos per batch
MAX_CONCURRENT_JOBS="3"        # Parallel transcription jobs
PROCESSING_TIMEOUT="1800"      # 30 minutes per video

# AWS S3
S3_BUCKET="your-videos-bucket"
AWS_ACCESS_KEY_ID="your-key"
AWS_SECRET_ACCESS_KEY="your-secret"
```

## Cost Analysis

### For 336 Videos (75 min average):
- **Google GPU Transcription**: $1,209.60 ($3.60/video)
- **Total Processing Time**: ~420 hours of audio
- **Storage**: S3 Glacier Instant Retrieval (~$0.004/GB/month)

### Comparison:
- **OpenAI Whisper API**: $2,646.00 (120% more expensive)
- **Local GPU**: Free but requires expensive GPU hardware
- **Google GPU**: Best balance of cost, accuracy, and reliability

## Database Schema

The system updates these fields in your videos table:

```sql
-- S3 Storage
s3_key              TEXT    -- S3 object key
s3_bucket          TEXT    -- S3 bucket name  
storage_mode       TEXT    -- 's3'
downloaded_at      TEXT    -- Timestamp

-- Streamable Integration
streamable_id      TEXT    -- Streamable video ID

-- Transcription Results
transcript         TEXT    -- Full transcript text
transcription_confidence REAL -- Confidence score (0-1)
transcribed_at     TEXT    -- Transcription timestamp
```

## Workflow Details

### 1. Video Processing Pipeline
```python
# Automatic workflow for each video:
1. Extract Streamable ID from ObjectivePersonality URL
2. Get video metadata from Streamable API
3. Stream video directly to S3 (no local storage)
4. Generate presigned URL for Google Speech access
5. Transcribe using Google GPU (chirp_2 model)
6. Update database with transcript and confidence score
```

### 2. Error Handling & Recovery
- **Streamable ID extraction**: Fallback from cookies to Chrome debug
- **S3 upload**: Verification and retry logic
- **Transcription**: Confidence scoring and error reporting
- **Database updates**: Transaction safety and rollback

### 3. Progress Tracking
- Per-session statistics and logging
- Resumable batch processing from last processed video
- Detailed error reporting and failed video tracking

## Monitoring & Logging

### Log Files Location
```
extraction_logs/
├── unified_extraction_session_YYYYMMDD_HHMMSS.log
└── unified_progress.json
```

### Progress JSON Format
```json
{
  "processed": 123,
  "successful": 120,
  "failed": 3,
  "by_platform": {
    "streamable": 115,
    "youtube": 5,
    "none": 3
  },
  "last_processed_id": "video_123",
  "session_count": 5
}
```

## Troubleshooting

### Common Issues

1. **Google Cloud Authentication Error**:
   ```bash
   export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account-key.json"
   gcloud auth application-default login
   ```

2. **S3 Access Denied**:
   ```bash
   aws configure list
   # Verify AWS credentials and bucket permissions
   ```

3. **Chrome Debug Connection Failed**:
   ```bash
   # Start Chrome with debugging enabled
   chrome --remote-debugging-port=9222 --user-data-dir=/tmp/chrome-debug
   ```

4. **Database Schema Missing**:
   ```sql
   ALTER TABLE videos ADD COLUMN transcript TEXT;
   ALTER TABLE videos ADD COLUMN transcription_confidence REAL;
   ALTER TABLE videos ADD COLUMN transcribed_at TEXT;
   ```

### Performance Optimization

1. **Batch Size**: Increase `TRANSCRIPTION_BATCH_SIZE` for faster processing
2. **Concurrent Jobs**: Adjust `MAX_CONCURRENT_JOBS` based on quota limits
3. **Model Selection**: Use `latest_short` for faster processing of short videos
4. **S3 Region**: Ensure S3 bucket is in same region as processing

## Production Deployment

### Recommended Setup
```bash
# 1. Create dedicated service account
gcloud iam service-accounts create video-transcription

# 2. Set appropriate quotas
gcloud services quotas update --service=speech.googleapis.com \
  --consumer=projects/YOUR_PROJECT_ID \
  --usage-bucket=requests-per-minute-per-user \
  --value=1000

# 3. Set up monitoring
gcloud logging sinks create transcription-logs \
  cloud-storage://your-logs-bucket/transcription/

# 4. Configure environment for production
export NODE_ENV=production
export TRANSCRIPTION_BATCH_SIZE=20
export MAX_CONCURRENT_JOBS=5
```

### Security Considerations
- Use IAM service accounts with minimal required permissions
- Enable VPC Service Controls for additional security
- Rotate service account keys regularly
- Monitor API usage and set billing alerts

## Support

For issues or questions:
1. Check logs in `extraction_logs/` directory
2. Verify configuration with `python3 transcription_config.py`
3. Test individual components before running full pipeline
4. Monitor Google Cloud quotas and billing

---

**Status**: Production Ready ✅  
**Last Updated**: December 2024  
**Cost**: ~$3.60 per 75-minute video