# Google Colab Whisper Integration Guide

## How Easy Is It? Very! 

Total setup time: **~15 minutes**

## What It Does

1. **Your VM** generates presigned S3 URLs for videos
2. **Google Colab** downloads videos, transcribes them with GPU
3. **Results** automatically sync back to your database
4. **Transcripts** saved to S3 alongside videos

## Step-by-Step Setup

### 1. Get Google Colab Pro ($10/month)
- Go to [colab.research.google.com](https://colab.research.google.com)
- Click "Get Pro" 
- Sign up with Google account

### 2. Database Setup (Already Done!)
```sql
-- Add these columns to your videos table (I'll do this for you)
ALTER TABLE videos ADD COLUMN transcription_status TEXT;
ALTER TABLE videos ADD COLUMN transcript_s3_key TEXT;
ALTER TABLE videos ADD COLUMN transcribed_at TEXT;
```

### 3. Simple Workflow

**On Your VM:**
```bash
# Prepare a batch of 10 videos
python3 colab_whisper_integration.py prepare 10

# This creates: colab_batch_1234567890.json
```

**In Google Colab:**
1. Create new notebook
2. Copy/paste code from `whisper_colab_notebook.txt`
3. Run all cells
4. Upload the batch JSON when prompted
5. Wait ~30 minutes for 10 videos
6. Download results file

**Back on Your VM:**
```bash
# Process the results
python3 colab_whisper_integration.py process results_colab_batch_1234567890.json

# ✅ Database updated!
# ✅ Transcripts saved to S3!
```

## Performance

- **T4 GPU Speed**: ~3x realtime
- **10 videos (750 min)**: ~4 hours
- **Parallel batches**: Run multiple Colab tabs!

## Cost Comparison

For your 296 videos:
- **Whisper API**: $133 (instant, no setup)
- **Google Colab Pro**: $10/month (reusable forever)
- **Your time**: 15 min setup + clicking "Run"

## Database Integration

The script automatically:
- Updates `transcription_status`: pending → processing → completed
- Saves transcript location in `transcript_s3_key`
- Records timestamp in `transcribed_at`

## Example Query
```sql
-- See transcription progress
SELECT 
    COUNT(*) as total,
    SUM(CASE WHEN transcription_status = 'completed' THEN 1 ELSE 0 END) as completed
FROM videos
WHERE s3_key IS NOT NULL;
```

## Pro Tips

1. **Batch Size**: 10-20 videos optimal (Colab has 12hr limit)
2. **Model Choice**: "base" model is best balance
3. **Multiple Tabs**: Run 3-4 Colab tabs simultaneously
4. **Auto-save**: Results download automatically

Want me to set this up for you right now?