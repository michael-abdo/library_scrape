#!/usr/bin/env python3
"""
Transcribe large videos by downloading from S3 and processing in chunks
WITH TIMESTAMP PRESERVATION
"""

import argparse
import json
import logging
import os
import sqlite3
import sys
import time
import tempfile
import subprocess
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
import boto3
from botocore.exceptions import ClientError

from openai_whisper_transcriber import OpenAIWhisperTranscriber

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ChunkedTranscriber:
    """Handle transcription of large videos by chunking with timestamp preservation"""
    
    def __init__(self, db_path: str = 'test_videos.db'):
        """Initialize the transcription processor"""
        self.db_path = db_path
        
        # Initialize S3 client with zenex profile
        session = boto3.Session(profile_name='zenex')
        self.s3_client = session.client('s3')
        self.bucket_name = 'xenodx-video-archive'
        
        # Initialize OpenAI transcriber
        self.transcriber = OpenAIWhisperTranscriber()
        logger.info("Using OpenAI Whisper with chunking for large files")
        
        # Chunk settings
        self.chunk_duration = 600  # 10 minutes per chunk
        self.max_chunk_size = 24 * 1024 * 1024  # 24MB to stay under 25MB limit
    
    def calculate_chunk_offset(self, chunk_index: int) -> float:
        """Calculate the time offset for a given chunk"""
        return chunk_index * self.chunk_duration
    
    def adjust_segment_timestamps(self, segments: List[Dict], offset: float) -> List[Dict]:
        """Adjust segment timestamps by adding the chunk offset"""
        adjusted_segments = []
        for segment in segments:
            adjusted_segment = segment.copy()
            adjusted_segment['start'] = segment.get('start', 0) + offset
            adjusted_segment['end'] = segment.get('end', 0) + offset
            adjusted_segments.append(adjusted_segment)
        return adjusted_segments
    
    def adjust_word_timestamps(self, words: List[Dict], offset: float) -> List[Dict]:
        """Adjust word-level timestamps by adding the chunk offset"""
        adjusted_words = []
        for word in words:
            adjusted_word = word.copy()
            adjusted_word['start_time'] = word.get('start_time', 0) + offset
            adjusted_word['end_time'] = word.get('end_time', 0) + offset
            adjusted_words.append(adjusted_word)
        return adjusted_words
    
    def renumber_segments(self, all_segments: List[List[Dict]]) -> List[Dict]:
        """Merge and renumber all segments with sequential IDs"""
        merged_segments = []
        segment_id = 0
        
        for chunk_segments in all_segments:
            for segment in chunk_segments:
                segment['id'] = segment_id
                merged_segments.append(segment)
                segment_id += 1
        
        return merged_segments
    
    def get_videos_needing_transcription(self, limit: Optional[int] = None) -> List[Dict]:
        """Get videos that have no transcript"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                query = """
                    SELECT id, title, video_url
                    FROM videos 
                    WHERE video_url IS NOT NULL 
                    AND video_url != ''
                    AND (transcript IS NULL OR transcript = '')
                    ORDER BY id
                """
                
                if limit:
                    query += f" LIMIT {limit}"
                
                cursor.execute(query)
                videos = [dict(row) for row in cursor.fetchall()]
                
                return videos
                
        except Exception as e:
            logger.error(f"Database error: {e}")
            return []
    
    def download_video_from_s3(self, s3_url: str, local_path: str) -> bool:
        """Download video from S3 to local path"""
        try:
            # Extract key from S3 URL
            if 'amazonaws.com/' in s3_url:
                key = s3_url.split('amazonaws.com/')[-1]
            else:
                logger.error(f"Invalid S3 URL format: {s3_url}")
                return False
            
            logger.info(f"Downloading from S3: {key}")
            self.s3_client.download_file(self.bucket_name, key, local_path)
            
            # Verify file size
            file_size = os.path.getsize(local_path)
            logger.info(f"Downloaded {file_size / (1024*1024):.1f} MB")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to download from S3: {e}")
            return False
    
    def extract_audio_chunks(self, video_path: str, output_dir: str) -> List[Tuple[str, int]]:
        """Extract audio from video and split into chunks
        Returns list of (chunk_file_path, chunk_index) tuples"""
        chunk_files = []
        
        try:
            # First extract full audio
            audio_path = os.path.join(output_dir, "audio.mp3")
            logger.info("Extracting audio from video...")
            
            cmd = [
                'ffmpeg', '-i', video_path,
                '-vn',  # No video
                '-acodec', 'mp3',
                '-ab', '128k',  # Bitrate
                '-ar', '16000',  # Sample rate
                audio_path,
                '-y'  # Overwrite
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                logger.error(f"FFmpeg error: {result.stderr}")
                return []
            
            # Get audio duration
            probe_cmd = [
                'ffprobe', '-v', 'error',
                '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                audio_path
            ]
            
            duration_result = subprocess.run(probe_cmd, capture_output=True, text=True)
            total_duration = float(duration_result.stdout.strip())
            logger.info(f"Total audio duration: {total_duration:.1f} seconds")
            
            # Calculate number of chunks
            num_chunks = int(total_duration / self.chunk_duration) + 1
            logger.info(f"Splitting into {num_chunks} chunks of {self.chunk_duration}s each")
            
            # Split audio into chunks
            for i in range(num_chunks):
                start_time = i * self.chunk_duration
                chunk_file = os.path.join(output_dir, f"chunk_{i+1:03d}.mp3")
                
                split_cmd = [
                    'ffmpeg', '-i', audio_path,
                    '-ss', str(start_time),
                    '-t', str(self.chunk_duration),
                    '-acodec', 'copy',
                    chunk_file,
                    '-y'
                ]
                
                result = subprocess.run(split_cmd, capture_output=True, text=True)
                if result.returncode == 0:
                    # Check chunk size
                    chunk_size = os.path.getsize(chunk_file)
                    if chunk_size > 0 and chunk_size < self.max_chunk_size:
                        chunk_files.append((chunk_file, i))  # Store with chunk index
                        logger.info(f"Created chunk {i+1}/{num_chunks}: {chunk_size/(1024*1024):.1f} MB")
                    else:
                        logger.warning(f"Chunk {i+1} too large or empty: {chunk_size} bytes")
            
            # Remove full audio file to save space
            os.remove(audio_path)
            
            return chunk_files
            
        except Exception as e:
            logger.error(f"Error splitting audio: {e}")
            return []
    
    def transcribe_chunks(self, chunk_files: List[Tuple[str, int]]) -> Optional[Dict]:
        """Transcribe all chunks and combine results with timestamp preservation"""
        all_transcripts = []
        all_segments = []
        all_words = []
        total_confidence = 0
        
        for chunk_file, chunk_index in chunk_files:
            logger.info(f"Transcribing chunk {chunk_index + 1}/{len(chunk_files)}")
            
            try:
                # Calculate time offset for this chunk
                chunk_offset = self.calculate_chunk_offset(chunk_index)
                
                # Read chunk file and transcribe using OpenAI with verbose JSON
                with open(chunk_file, 'rb') as audio_file:
                    # Use OpenAI client directly with verbose_json for segments
                    transcript_response = self.transcriber.client.audio.transcriptions.create(
                        model="whisper-1",
                        file=audio_file,
                        response_format="verbose_json",  # Get segments with timestamps
                        language=self.transcriber.language if self.transcriber.language != "auto" else None
                    )
                    
                    if transcript_response and transcript_response.text:
                        # Add transcript text
                        all_transcripts.append(transcript_response.text)
                        total_confidence += 0.9  # OpenAI doesn't provide confidence scores
                        
                        # Process segments if available
                        if hasattr(transcript_response, 'segments') and transcript_response.segments:
                            # Adjust timestamps for this chunk's segments
                            chunk_segments = []
                            for segment in transcript_response.segments:
                                adjusted_segment = {
                                    'start': segment.start + chunk_offset,
                                    'end': segment.end + chunk_offset,
                                    'text': segment.text
                                }
                                chunk_segments.append(adjusted_segment)
                            
                            all_segments.append(chunk_segments)
                            
                            # Process word-level timestamps if available
                            if hasattr(transcript_response.segments[0], 'words'):
                                for segment in transcript_response.segments:
                                    if hasattr(segment, 'words') and segment.words:
                                        for word in segment.words:
                                            adjusted_word = {
                                                'word': word.get('word', ''),
                                                'start_time': word.get('start', 0) + chunk_offset,
                                                'end_time': word.get('end', 0) + chunk_offset,
                                                'confidence': word.get('confidence', 1.0)
                                            }
                                            all_words.append(adjusted_word)
                        
                        logger.info(f"Successfully transcribed chunk {chunk_index + 1} with {len(chunk_segments) if 'chunk_segments' in locals() else 0} segments")
                    else:
                        logger.error(f"Empty transcript for chunk {chunk_index + 1}")
                    
            except Exception as e:
                logger.error(f"Error transcribing chunk {chunk_index + 1}: {e}")
            
            # Small delay between chunks
            time.sleep(1)
        
        if all_transcripts:
            # Combine all transcripts
            combined_transcript = ' '.join(all_transcripts)
            avg_confidence = total_confidence / len(all_transcripts) if all_transcripts else 0
            
            # Merge and renumber segments
            merged_segments = self.renumber_segments(all_segments) if all_segments else []
            
            return {
                'success': True,
                'text': combined_transcript,
                'transcript': combined_transcript,  # For compatibility
                'segments': merged_segments,
                'word_timestamps': all_words,
                'confidence': avg_confidence,
                'service': 'openai-chunked',
                'chunks_processed': len(all_transcripts),
                'total_chunks': len(chunk_files),
                'has_timestamps': len(merged_segments) > 0
            }
        
        return None
    
    def transcribe_video(self, video: Dict) -> Optional[Dict]:
        """Transcribe a single video using chunking"""
        video_id = video['id']
        title = video['title']
        s3_url = video['video_url']
        
        logger.info(f"Processing video {video_id}: {title}")
        
        # Create temporary directory for processing
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                # Download video
                video_path = os.path.join(temp_dir, f"video_{video_id}.mp4")
                if not self.download_video_from_s3(s3_url, video_path):
                    return None
                
                # Extract and chunk audio
                chunk_files = self.extract_audio_chunks(video_path, temp_dir)
                if not chunk_files:
                    logger.error("Failed to create audio chunks")
                    return None
                
                # Delete video to save space
                os.remove(video_path)
                
                # Transcribe chunks
                result = self.transcribe_chunks(chunk_files)
                
                if result:
                    logger.info(f"Successfully transcribed video {video_id} in {result['chunks_processed']} chunks")
                    if result.get('has_timestamps'):
                        logger.info(f"  - Preserved {len(result.get('segments', []))} segments with timestamps")
                        logger.info(f"  - Preserved {len(result.get('word_timestamps', []))} word timestamps")
                    return result
                else:
                    logger.error(f"Failed to transcribe chunks for video {video_id}")
                    return None
                    
            except Exception as e:
                logger.error(f"Error processing video {video_id}: {e}")
                return None
    
    def update_database(self, video_id: int, transcript_result: Dict) -> bool:
        """Update database with transcription results"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Extract transcript text
                transcript_text = transcript_result.get('text', '')
                confidence = transcript_result.get('confidence', 0.0)
                service = transcript_result.get('service', 'openai-chunked')
                
                # Check if we have segments to save
                segments = transcript_result.get('segments', [])
                segments_json = json.dumps(segments) if segments else None
                
                # Check if segments column exists
                cursor.execute("PRAGMA table_info(videos)")
                columns = [row[1] for row in cursor.fetchall()]
                has_segments_column = 'segments' in columns
                
                if has_segments_column:
                    # Update with segments
                    cursor.execute("""
                        UPDATE videos 
                        SET transcript = ?,
                            transcription_confidence = ?,
                            transcription_service = ?,
                            transcribed_at = ?,
                            segments = ?
                        WHERE id = ?
                    """, (
                        transcript_text,
                        confidence,
                        service,
                        datetime.now().isoformat(),
                        segments_json,
                        video_id
                    ))
                else:
                    # Update without segments column
                    cursor.execute("""
                        UPDATE videos 
                        SET transcript = ?,
                            transcription_confidence = ?,
                            transcription_service = ?,
                            transcribed_at = ?
                        WHERE id = ?
                    """, (
                        transcript_text,
                        confidence,
                        service,
                        datetime.now().isoformat(),
                        video_id
                    ))
                
                conn.commit()
                logger.info(f"Updated database for video {video_id}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to update database for video {video_id}: {e}")
            return False
    
    def save_transcript_to_s3(self, video_id: int, transcript_result: Dict) -> Optional[str]:
        """Save transcript with timestamps to S3"""
        try:
            # Generate S3 key
            s3_key = f"transcripts/{video_id}/transcript_with_timestamps.json"
            
            # Prepare transcript data with all metadata
            transcript_data = {
                'video_id': video_id,
                'transcript': transcript_result.get('text', ''),
                'segments': transcript_result.get('segments', []),
                'word_timestamps': transcript_result.get('word_timestamps', []),
                'metadata': {
                    'service': transcript_result.get('service', 'openai-chunked'),
                    'confidence': transcript_result.get('confidence', 0),
                    'chunks_processed': transcript_result.get('chunks_processed', 0),
                    'total_chunks': transcript_result.get('total_chunks', 0),
                    'has_timestamps': transcript_result.get('has_timestamps', False),
                    'language': 'en',
                    'created_at': datetime.now().isoformat()
                }
            }
            
            # Convert to JSON
            transcript_json = json.dumps(transcript_data, indent=2)
            
            # Upload to S3
            from io import BytesIO
            transcript_bytes = BytesIO(transcript_json.encode('utf-8'))
            
            self.s3_client.upload_fileobj(
                transcript_bytes,
                self.bucket_name,
                s3_key,
                ExtraArgs={
                    'ContentType': 'application/json',
                    'Metadata': {
                        'video_id': str(video_id),
                        'has_timestamps': 'true'
                    }
                }
            )
            
            logger.info(f"Uploaded transcript with timestamps to S3: {s3_key}")
            return s3_key
            
        except Exception as e:
            logger.error(f"Failed to save transcript to S3: {e}")
            return None
    
    def process_videos(self, limit: Optional[int] = None):
        """Process videos for transcription"""
        # Get videos needing transcription
        videos = self.get_videos_needing_transcription(limit)
        
        if not videos:
            logger.info("No videos found that need transcription")
            return
        
        logger.info(f"Found {len(videos)} videos to process")
        
        # Process each video
        successful = 0
        failed = 0
        
        for i, video in enumerate(videos, 1):
            print(f"\n{'='*60}")
            print(f"Processing video {i}/{len(videos)}")
            print(f"{'='*60}")
            
            # Transcribe the video
            result = self.transcribe_video(video)
            
            if result and result.get('success'):
                # Save to S3 if requested
                s3_key = self.save_transcript_to_s3(video['id'], result)
                if s3_key:
                    result['s3_key'] = s3_key
                
                # Update database
                if self.update_database(video['id'], result):
                    successful += 1
                    logger.info(f"Successfully processed video {video['id']}")
                else:
                    failed += 1
                    logger.error(f"Failed to update database for video {video['id']}")
            else:
                failed += 1
                logger.error(f"Failed to transcribe video {video['id']}")
            
            # Small delay between videos
            if i < len(videos):
                time.sleep(2)
        
        # Summary
        print(f"\n{'='*60}")
        print(f"Transcription Summary:")
        print(f"  Total processed: {len(videos)}")
        print(f"  Successful: {successful}")
        print(f"  Failed: {failed}")
        print(f"{'='*60}")


def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='Transcribe large videos using chunking with timestamp preservation')
    parser.add_argument('--limit', type=int, default=5, help='Limit number of videos to process (default: 5)')
    parser.add_argument('--db', type=str, default='test_videos.db', help='Database path (default: test_videos.db)')
    
    args = parser.parse_args()
    
    # Check if ffmpeg is available
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
    except:
        logger.error("FFmpeg not found. Please install ffmpeg: sudo apt-get install ffmpeg")
        sys.exit(1)
    
    # Initialize processor
    processor = ChunkedTranscriber(db_path=args.db)
    
    # Process videos
    processor.process_videos(limit=args.limit)


if __name__ == "__main__":
    main()