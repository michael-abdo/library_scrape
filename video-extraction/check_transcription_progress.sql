-- Check overall transcription progress
SELECT 
    'Transcription Progress' as metric,
    COUNT(*) as total_videos,
    SUM(CASE WHEN s3_key IS NOT NULL THEN 1 ELSE 0 END) as videos_in_s3,
    SUM(CASE WHEN transcription_status = 'completed' THEN 1 ELSE 0 END) as transcribed,
    SUM(CASE WHEN transcription_status = 'processing' THEN 1 ELSE 0 END) as processing,
    SUM(CASE WHEN transcription_status = 'failed' THEN 1 ELSE 0 END) as failed,
    SUM(CASE WHEN s3_key IS NOT NULL AND (transcription_status IS NULL OR transcription_status = 'pending') THEN 1 ELSE 0 END) as pending
FROM videos;

-- Show recent transcriptions
SELECT 
    id,
    title,
    transcription_status,
    transcript_s3_key,
    transcribed_at
FROM videos
WHERE transcription_status = 'completed'
ORDER BY transcribed_at DESC
LIMIT 10;

-- Show videos currently being processed
SELECT 
    id,
    title,
    transcription_status
FROM videos
WHERE transcription_status = 'processing';

-- Calculate completion percentage
SELECT 
    ROUND(
        CAST(SUM(CASE WHEN transcription_status = 'completed' THEN 1 ELSE 0 END) AS FLOAT) / 
        CAST(SUM(CASE WHEN s3_key IS NOT NULL THEN 1 ELSE 0 END) AS FLOAT) * 100, 
        2
    ) || '%' as completion_percentage
FROM videos
WHERE s3_key IS NOT NULL;