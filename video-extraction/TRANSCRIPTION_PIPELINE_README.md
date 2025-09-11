# Programmatic Transcription Pipeline

## Overview

This is a fully automated transcription pipeline that integrates with the video processing workflow. It supports multiple transcription services and runs continuously in the background.

## Features

- ✅ **Fully Programmatic** - No manual intervention required
- 🔄 **Continuous Processing** - Automatically transcribes new videos
- 🎯 **Multiple Services** - OpenAI Whisper, Replicate, HuggingFace
- 💰 **Cost Optimization** - Choose the most cost-effective service
- 🔁 **Retry Logic** - Automatic retries for failed transcriptions
- 📊 **Progress Tracking** - Monitor transcription status in real-time
- 🔌 **Pipeline Integration** - Works seamlessly with existing video processor

## Quick Start

### 1. Setup Environment

```bash
# Copy example environment file
cp .env.example .env

# Edit .env and add your API keys
nano .env
```

### 2. Install Dependencies

```bash
pip install python-dotenv requests
```

### 3. Run Transcription Worker

```bash
# Start the background worker
python3 run_transcription_worker.py start

# Check status
python3 run_transcription_worker.py status

# Stop worker
python3 run_transcription_worker.py stop
```

### 4. Process Videos with Transcription

```bash
# Process new videos AND transcribe them
python3 batch_processor_with_transcription.py --limit 100 --transcribe

# Use a specific service
python3 batch_processor_with_transcription.py --transcribe --transcription-service openai
```

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│                 │     │                  │     │                 │
│ Video Processor │────▶│ S3 Upload        │────▶│ Transcription   │
│                 │     │                  │     │ Pipeline        │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                                                           │
                                                           ▼
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│                 │     │                  │     │                 │
│ SQLite DB       │◀────│ S3 Transcripts   │◀────│ Whisper API     │
│                 │     │                  │     │                 │
└─────────────────┘     └──────────────────┘     └─────────────────┘
```

## Components

### 1. `whisper_api_client.py`
- Handles API communication with transcription services
- Downloads videos from S3 temporarily
- Uploads transcripts back to S3

### 2. `transcription_pipeline.py`
- Orchestrates the transcription process
- Manages database updates
- Handles retries and error recovery

### 3. `batch_processor_with_transcription.py`
- Enhanced video processor with integrated transcription
- Processes videos and transcribes in one workflow

### 4. `run_transcription_worker.py`
- Background worker for continuous transcription
- Manages worker lifecycle (start/stop/status)

### 5. `transcription_config.py`
- Centralized configuration management
- Environment variable handling

## Service Comparison

| Service     | Cost/min | Speed | File Limit | Features              |
|------------|----------|-------|------------|-----------------------|
| OpenAI     | $0.006   | Fast  | 25MB       | High accuracy         |
| Replicate  | ~$0.01   | Fast  | No limit   | GPU options          |
| HuggingFace| Free     | Slow  | 100MB      | Free tier available  |

## Usage Examples

### Run Standalone Transcription

```bash
# Transcribe pending videos (one batch)
python3 transcription_pipeline.py --batch-size 10

# Run continuously
python3 transcription_pipeline.py --continuous

# Use different service
python3 transcription_pipeline.py --service huggingface --continuous
```

### Integrated with Video Processing

```bash
# Process and transcribe 100 videos
python3 batch_processor_with_transcription.py \
    --limit 100 \
    --transcribe \
    --transcription-service openai
```

### Background Worker

```bash
# Start worker
./run_transcription_worker.py start

# Check logs
tail -f transcription_worker.log

# Monitor progress
./run_transcription_worker.py status
```

## Configuration

### Environment Variables

```bash
# Required for OpenAI
OPENAI_API_KEY=sk-...

# Optional services
REPLICATE_API_TOKEN=r8_...
HUGGINGFACE_API_KEY=hf_...

# Settings
TRANSCRIPTION_SERVICE=openai
TRANSCRIPTION_BATCH_SIZE=10
ENABLE_AUTO_TRANSCRIPTION=true
```

### Cost Estimation

```bash
# Check costs before running
python3 -c "
from transcription_config import TranscriptionConfig
costs = TranscriptionConfig.estimate_cost(100, avg_duration_minutes=75)
for service, cost in costs.items():
    print(f'{service}: ${cost[\"total_cost\"]:.2f} total')
"
```

## Monitoring

### Check Progress

```sql
-- Run in SQLite
SELECT 
    COUNT(*) as total,
    SUM(CASE WHEN transcription_status = 'completed' THEN 1 ELSE 0 END) as completed
FROM videos
WHERE s3_key IS NOT NULL;
```

### View Recent Transcriptions

```sql
SELECT 
    title,
    transcription_status,
    transcribed_at
FROM videos
WHERE transcription_status = 'completed'
ORDER BY transcribed_at DESC
LIMIT 10;
```

## Troubleshooting

### Common Issues

1. **API Key Errors**
   ```bash
   export OPENAI_API_KEY='your-key-here'
   ```

2. **File Too Large**
   - Files over 25MB will be skipped for OpenAI
   - Use Replicate or chunk the files

3. **Rate Limiting**
   - Automatic delays are built in
   - Adjust `DELAY_BETWEEN_REQUESTS` if needed

4. **Worker Not Starting**
   ```bash
   # Check if port is in use
   ps aux | grep transcription_worker
   ```

## Best Practices

1. **Start Small**: Test with a few videos first
2. **Monitor Costs**: Check estimated costs before large batches
3. **Use Background Worker**: For continuous processing
4. **Choose Right Service**: OpenAI for quality, HuggingFace for free

## Next Steps

1. Set up your API keys in `.env`
2. Start the transcription worker
3. Monitor progress with `status` command
4. Scale up as needed

## Support

- Check logs: `transcription_worker.log`
- Database: `../library_videos.db`
- Transcripts stored in: `s3://xenodex-video-archive/transcripts/`