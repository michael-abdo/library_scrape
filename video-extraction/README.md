# Video Transcription System with OpenAI Whisper & Google Speech

A production-ready system for extracting, uploading, and transcribing ObjectivePersonality videos using **OpenAI Whisper API** (primary) and **Google Cloud Speech-to-Text** (fallback) with automatic service selection and cost optimization.

## Architecture Overview

```
Video URL → Streamable ID Extraction → S3 Upload → OpenAI Whisper/Google Speech → Database Storage
                                                     ↑ (Service Selection + Fallback)
```

## 🚀 Key Features

- **87.5% Cost Savings**: OpenAI Whisper API ($151.20 vs $907.20+ for Google)
- **Dual Service Support**: OpenAI Whisper (primary) + Google Speech (fallback)
- **Automatic Fallback**: Switches to backup service if primary fails
- **Service Selection**: Environment variable controlled service preference
- **Cost Analysis**: Real-time cost comparison and optimization recommendations
- **Streamable ID Support**: Process videos with known IDs (skip extraction)

## Core Components

### 1. `unified_video_processor.py` - Main Processing Pipeline
- **Purpose**: Complete workflow from video URL to transcribed content
- **Features**: 
  - Multi-method Streamable ID extraction (cookies + Chrome debug)
  - Support for known Streamable IDs with `--streamable` flag
  - Direct S3 streaming (no local storage)
  - **Dual-service transcription** with automatic fallback
  - Service selection based on cost optimization
  - Progress tracking and error recovery
  - Database updates with service tracking

### 2. `openai_whisper_transcriber.py` - OpenAI Whisper API Integration (Primary)
- **Purpose**: Cost-effective, high-accuracy transcription using OpenAI Whisper API
- **Features**:
  - **87.5% cheaper** than Google Speech ($0.006/minute)
  - S3 download → OpenAI upload workflow (25MB file limit)
  - Excellent accuracy with multilingual support
  - Fast processing and reliable API
  - Compatible result format for seamless integration

### 3. `google_gpu_transcriber.py` - Google Cloud Speech-to-Text Integration (Fallback)
- **Purpose**: High-accuracy video transcription using Google's GPU-accelerated models
- **Features**:
  - Support for multiple Google Speech models (chirp_2, latest_long, latest_short, video)
  - S3 presigned URL processing (no file size limits)
  - Confidence scoring and error handling
  - Premium transcription quality ($0.036-0.048/minute)

### 4. `transcription_config.py` - Unified Service Configuration
- **Purpose**: Centralized configuration for both OpenAI Whisper and Google Speech
- **Features**:
  - **Service selection**: 'openai' (default) or 'google'
  - Cost estimation and comparison utilities
  - Model information and recommendations
  - Environment variable management
  - Validation and diagnostics for both services

### 5. `s3_manager.py` - AWS S3 Storage Manager
- **Purpose**: Efficient video storage and access for transcription
- **Features**:
  - Direct streaming uploads (no local storage)
  - Presigned URL generation for secure access
  - Glacier Instant Retrieval for cost optimization
  - Progress tracking and metadata handling
  - Default bucket: `xenodx-video-archive`

## Quick Start

### Prerequisites

#### Option 1: OpenAI Whisper Setup (Recommended - 87.5% cheaper)

1. **OpenAI API Key**:
   ```bash
   # Get API key from https://platform.openai.com/api-keys
   export OPENAI_API_KEY="sk-your-openai-api-key"
   ```

2. **Basic Environment Variables**:
   ```bash
   export TRANSCRIPTION_SERVICE="openai"  # Use OpenAI Whisper (default)
   export AWS_PROFILE="zenex"             # AWS profile
   export S3_BUCKET="xenodx-video-archive" # S3 bucket
   ```

3. **Install Dependencies**:
   ```bash
   pip install openai boto3 requests
   ```

#### Option 2: Google Cloud Setup (Fallback/Premium)

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

2. **Google Environment Variables**:
   ```bash
   export TRANSCRIPTION_SERVICE="google"  # Force Google Speech
   export GOOGLE_CLOUD_PROJECT="your-project-id"
   export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account-key.json"
   export AWS_PROFILE="zenex"
   export S3_BUCKET="xenodx-video-archive"
   ```

3. **Install Google Dependencies**:
   ```bash
   pip install google-cloud-speech google-auth openai boto3 requests
   ```

### Basic Usage

#### Process Videos in Batch
```bash
# Process next 5 unprocessed videos
python3 unified_video_processor.py --limit 5

# Process videos with known Streamable IDs (skip extraction)
python3 unified_video_processor.py --limit 200 --streamable

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

#### Transcription Operations
```bash
# Transcribe videos from S3 (with fallback)
python3 transcribe_s3_videos.py --limit 10

# Force specific service
export TRANSCRIPTION_SERVICE="google"
python3 transcribe_s3_videos.py --limit 5

# Upload existing transcripts to S3
python3 upload_transcripts_to_s3.py
```

#### Configuration Testing
```bash
# Test transcription service configuration (OpenAI + Google)
python3 transcription_config.py

# Run cost comparison analysis
python3 cost_comparison.py
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
# Service Selection
TRANSCRIPTION_SERVICE="openai"  # 'openai' or 'google'

# Google Cloud (if using Google)
GOOGLE_CLOUD_PROJECT="your-project-id"
GOOGLE_APPLICATION_CREDENTIALS="/path/to/key.json"
GOOGLE_SPEECH_MODEL="chirp_2"  # Default model
GOOGLE_SPEECH_LANGUAGE="en-US"

# Processing
TRANSCRIPTION_BATCH_SIZE="10"  # Videos per batch
MAX_CONCURRENT_JOBS="3"        # Parallel transcription jobs
PROCESSING_TIMEOUT="1800"      # 30 minutes per video

# AWS S3
S3_BUCKET="xenodx-video-archive"
AWS_PROFILE="zenex"
```

## 💰 Cost Analysis & Savings

### For 336 Videos (75 min average = 25,200 minutes total):

| Service | Total Cost | Per Video | Savings vs OpenAI |
|---------|------------|-----------|-------------------|
| **🥇 OpenAI Whisper** | **$151.20** | **$0.45** | **- (baseline)** |
| 🥈 AWS Transcribe | $604.80 | $1.80 | 300% more expensive |
| 🥉 Google latest_long | $907.20 | $2.70 | 500% more expensive |
| 💸 Google chirp_2 | $1,209.60 | $3.60 | 700% more expensive |

### 🚀 OpenAI Whisper Advantages:
- **87.5% cheaper** than Google Speech-to-Text
- **$756-$1,058 savings** for 336 videos compared to Google
- **Excellent accuracy** with multilingual support  
- **Fast processing** and reliable API
- **Easy setup** - just need OpenAI API key

### 💡 Cost Breakdown:
- **OpenAI Whisper**: $0.006/minute × 25,200 minutes = $151.20
- **Google latest_long**: $0.036/minute equivalent = $907.20  
- **Google chirp_2**: $0.048/minute equivalent = $1,209.60
- **Storage**: S3 Glacier Instant Retrieval (~$0.004/GB/month)

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
transcription_service TEXT    -- Service used: 'openai' or 'google' 
transcribed_at     TEXT    -- Transcription timestamp
```

### Database Migration
```bash
# Add transcription_service column to existing database
python3 database_migration.py
```

## Workflow Details

### 1. Video Processing Pipeline
```python
# Automatic workflow for each video:
1. Extract Streamable ID from ObjectivePersonality URL (or use known ID)
2. Get video metadata from Streamable API
3. Stream video directly to S3 (no local storage)
4. Generate presigned URL for transcription access
5. Transcribe using OpenAI Whisper (with Google fallback)
6. Update database with transcript and confidence score
```

### 2. Error Handling & Recovery
- **Streamable ID extraction**: Fallback from cookies to Chrome debug
- **S3 upload**: Verification and retry logic
- **Transcription**: Automatic service fallback on failure
- **Database updates**: Transaction safety and rollback support

### 3. Performance Optimization
- **Batch processing**: Process multiple videos concurrently
- **Streaming uploads**: No local disk usage
- **Presigned URLs**: Direct S3 access for transcription
- **Service selection**: Cost-optimized default with quality fallback

## Troubleshooting

### Common Issues

1. **AWS Credentials**:
   ```bash
   # Verify AWS profile
   aws --profile zenex sts get-caller-identity
   ```

2. **OpenAI API Key**:
   ```bash
   # Test OpenAI connection
   python3 -c "import openai; print(openai.api_key[:10] + '...')"
   ```

3. **Google Cloud Auth**:
   ```bash
   # Verify Google credentials
   gcloud auth application-default print-access-token
   ```

4. **Database Path**:
   ```bash
   # Check database location
   sqlite3 library_videos.db "SELECT COUNT(*) FROM videos;"
   ```

## Production Deployment

For large-scale processing:

```bash
# Process in background with logging
nohup python3 unified_video_processor.py --limit 500 > transcription.log 2>&1 &

# Monitor progress
tail -f transcription.log

# Check completion status
python3 unified_video_processor.py --status
```

## Support

For issues or questions:
- Check logs in the working directory
- Verify environment variables are set correctly
- Ensure AWS credentials have S3 read/write permissions
- Confirm API keys are valid and have sufficient quota