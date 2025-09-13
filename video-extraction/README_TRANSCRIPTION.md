# Video Transcription Pipeline

## Overview

The `transcribe_s3_videos.py` script is designed to find videos in the database that already have S3 keys but haven't been transcribed yet. It uses OpenAI Whisper (or Google Speech-to-Text as fallback) to transcribe these videos and saves the transcripts to S3.

## Features

- **Automatic Discovery**: Finds videos with `s3_key` but no transcript
- **OpenAI Whisper Integration**: Uses OpenAI's Whisper API for transcription (87.5% cost savings vs Google)
- **Fallback Support**: Automatically falls back to Google Speech-to-Text if OpenAI fails
- **S3 Storage**: Saves transcripts as JSON files to S3 with metadata
- **Database Updates**: Updates the database with transcript S3 links and metadata
- **Batch Processing**: Process multiple videos with configurable limits
- **Status Monitoring**: Check transcription progress and statistics

## Usage

### Check Status
```bash
python3 transcribe_s3_videos.py --status
```

Shows:
- Total videos in database
- Videos with S3 keys
- Videos already transcribed
- Videos needing transcription
- Next videos to process

### Process Videos
```bash
# Process all videos needing transcription
python3 transcribe_s3_videos.py

# Process only 10 videos
python3 transcribe_s3_videos.py --limit 10

# Process specific video by ID
python3 transcribe_s3_videos.py --video-id "video123"

# Use specific service
python3 transcribe_s3_videos.py --service openai --limit 5
```

## Database Schema

The script works with these database columns:
- `s3_key` - The S3 key where the video is stored
- `transcript_s3_key` - The S3 key where the transcript JSON is stored
- `transcript_s3_url` - Full URL to the transcript in S3
- `transcription_status` - Status of transcription (pending/completed/failed)
- `transcribed_at` - Timestamp of when transcription completed
- `transcription_service` - Service used (openai/google)

## Transcript Storage

Transcripts are saved to S3 in JSON format:
- **Location**: `s3://bucket/transcripts/{video_id}/transcript.json`
- **Format**: JSON with transcript text, metadata, timestamps, segments

Example transcript structure:
```json
{
  "video_id": "video123",
  "transcript": "Full transcript text...",
  "metadata": {
    "service": "openai-whisper",
    "confidence": 0.95,
    "language_detected": "en",
    "processing_time": 45.2
  },
  "created_at": "2024-01-20T10:30:00Z",
  "word_timestamps": [...],
  "segments": [...]
}
```

## Configuration

The script uses environment variables from `.env`:
- `OPENAI_API_KEY` - For OpenAI Whisper
- `S3_BUCKET` - Target S3 bucket (default: op-videos-storage)
- `AWS_PROFILE` - AWS profile to use (optional)

## Cost Considerations

- **OpenAI Whisper**: $0.006 per minute
- **Google Speech-to-Text**: $0.048 per minute
- **Savings**: OpenAI is 87.5% cheaper

## Error Handling

The script includes:
- Automatic retry with fallback service
- Detailed error logging
- Safe database updates (only on success)
- Presigned URL generation with 2-hour expiration

## Integration with Existing Pipeline

This script complements the existing `unified_video_processor.py`:
1. `unified_video_processor.py` - Downloads and uploads videos to S3
2. `transcribe_s3_videos.py` - Transcribes videos already in S3
3. Both update the same database with their respective results

## Monitoring Progress

Use SQL queries to monitor detailed progress:
```sql
-- Videos ready for transcription
SELECT COUNT(*) FROM videos 
WHERE s3_key IS NOT NULL 
AND transcript_s3_key IS NULL;

-- Transcription success rate by service
SELECT transcription_service, COUNT(*) as count
FROM videos 
WHERE transcription_status = 'completed'
GROUP BY transcription_service;

-- Recent transcriptions
SELECT title, transcribed_at, transcription_service
FROM videos 
WHERE transcribed_at IS NOT NULL
ORDER BY transcribed_at DESC
LIMIT 10;
```