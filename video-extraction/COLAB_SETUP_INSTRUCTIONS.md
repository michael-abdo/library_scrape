# Quick Setup Instructions for Google Colab Whisper

## 📝 Step-by-Step Instructions

### 1. Sign up for Google Colab Pro
- Go to https://colab.research.google.com
- Click "Get Colab Pro" ($10/month)
- Select Pro plan for GPU access

### 2. Create New Notebook
- Click "New Notebook" 
- Select Runtime → Change runtime type → T4 GPU

### 3. Copy the Notebook Code
- Copy ALL the code from `whisper_colab_notebook.txt`
- Paste into the notebook
- You can split into cells at the "# Cell" comments

### 4. Run Your First Batch
On your local machine:
```bash
cd /home/Mike/projects/Xenodex/ops_scraping/library_scrape/video-extraction
python3 colab_whisper_integration.py prepare 5
```
This creates: `colab_batch_1757609228.json`

### 5. In Colab:
- Run all cells (Runtime → Run all)
- When prompted, upload your batch JSON file
- Wait for processing (5 videos = ~30 minutes)
- Results auto-download when done

### 6. Process Results (Local Machine)
```bash
python3 colab_whisper_integration.py process results_colab_batch_1757609228.json
```

## ✅ What Happens:
- Database updated with transcription status
- Transcripts saved to S3
- Progress tracked automatically

## 🚀 Pro Tips:
- Run multiple Colab tabs for parallel processing
- Batch size of 10-20 videos is optimal
- T4 GPU processes ~3x realtime
- Results persist even if Colab disconnects

## 📊 Current Status:
- Videos in S3: 322
- Need transcription: 322
- Batch prepared: 5 videos
- Ready to process!

## 🔧 Troubleshooting:
- If upload fails: Check file size < 100MB
- If GPU unavailable: Wait or try different region
- If transcription fails: Video might be corrupted