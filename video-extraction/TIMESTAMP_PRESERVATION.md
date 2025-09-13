# Timestamp Preservation in Chunked Transcription

## Overview

The enhanced chunked transcription system now preserves timestamps from OpenAI Whisper API when processing large video files that exceed the 25MB limit. This feature maintains accurate timing information across chunk boundaries.

## Key Features

1. **Segment-Level Timestamps**: Preserves start/end times for each transcript segment (sentences or paragraphs)
2. **Word-Level Timestamps**: Captures individual word timings when available
3. **Automatic Offset Adjustment**: Correctly adjusts timestamps based on chunk position in the original audio
4. **Sequential ID Management**: Renumbers segment IDs to maintain proper ordering

## How It Works

### 1. Chunking Process
- Videos are split into 10-minute (600 second) chunks
- Each chunk is processed independently by OpenAI Whisper
- Chunk index is tracked to calculate time offsets

### 2. Timestamp Adjustment
For each chunk `n`, timestamps are adjusted by adding the chunk offset:
```
adjusted_timestamp = original_timestamp + (chunk_index * chunk_duration)
```

Example:
- Chunk 0 (0-600s): No adjustment needed
- Chunk 1 (600-1200s): Add 600s to all timestamps
- Chunk 2 (1200-1800s): Add 1200s to all timestamps

### 3. Data Structure

The transcription result includes:

```json
{
  "transcript": "Full transcript text...",
  "segments": [
    {
      "id": 0,
      "start": 0.0,
      "end": 5.2,
      "text": "First segment text"
    },
    {
      "id": 1,
      "start": 5.2,
      "end": 10.8,
      "text": "Second segment text"
    }
  ],
  "word_timestamps": [
    {
      "word": "First",
      "start_time": 0.0,
      "end_time": 0.5,
      "confidence": 0.95
    }
  ],
  "metadata": {
    "has_timestamps": true,
    "chunks_processed": 3,
    "chunk_duration": 600
  }
}
```

## Usage

### Basic Usage
```bash
python3 transcribe_with_chunking_timestamps.py --limit 5
```

### Processing Specific Database
```bash
python3 transcribe_with_chunking_timestamps.py --db library_videos.db --limit 10
```

### Database Schema Update
Before using timestamp preservation, update your database schema:
```bash
python3 update_database_schema.py
```

This adds three new columns:
- `segments`: JSON array of segment timestamps
- `word_timestamps`: JSON array of word-level timestamps
- `has_timestamps`: Boolean flag indicating timestamp availability

## Benefits

1. **Accurate Timing**: Maintain precise timing information for subtitles and captions
2. **Searchability**: Enable time-based search within transcripts
3. **Synchronization**: Keep audio/video sync for playback applications
4. **Analytics**: Analyze speaking patterns and pacing

## Implementation Details

### Key Functions

1. **`calculate_chunk_offset(chunk_index)`**: Calculates time offset for a chunk
2. **`adjust_segment_timestamps(segments, offset)`**: Adjusts segment times
3. **`adjust_word_timestamps(words, offset)`**: Adjusts word-level times
4. **`renumber_segments(all_segments)`**: Merges and renumbers segments

### File Storage

Transcripts with timestamps are saved to S3 as:
```
s3://bucket/transcripts/{video_id}/transcript_with_timestamps.json
```

## Testing

Run the timestamp calculation tests:
```bash
python3 test_timestamp_calculations.py
```

This verifies:
- Correct offset calculations
- Proper timestamp adjustments
- Sequential segment numbering
- Timestamp continuity

## Limitations

1. **Chunk Boundaries**: Small gaps may exist at chunk boundaries due to audio splitting
2. **Word Timestamps**: Not all audio may have word-level precision
3. **Processing Time**: Timestamp processing adds minimal overhead

## Future Enhancements

1. Variable chunk sizes based on natural speech breaks
2. Overlap processing to improve boundary accuracy
3. Speaker diarization with timestamps
4. Real-time streaming support