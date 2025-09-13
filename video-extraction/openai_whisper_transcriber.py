#!/usr/bin/env python3
"""
OpenAI Whisper Transcriber
Cloud-based transcription using OpenAI Whisper API
"""
import os
import sys
import logging
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any, List
import json
import time
import boto3
import requests
import openai
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger(__name__)

class OpenAIWhisperTranscriber:
    """OpenAI Whisper API-based transcriber"""
    
    def __init__(self, model: str = "whisper-1", device: str = "openai-api", language: str = "en"):
        """
        Initialize OpenAI Whisper transcriber
        
        Args:
            model: OpenAI Whisper model (whisper-1)
            device: Device identifier (always "openai-api")
            language: Language code for transcription (en, es, fr, de, etc.)
        """
        self.model = model
        self.language = self._normalize_language(language)
        self.device = "openai-api"  # Using OpenAI's API infrastructure
        self.api_key = os.environ.get('OPENAI_API_KEY')
        
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required")
        
        # Initialize OpenAI client
        self.client = openai.OpenAI(api_key=self.api_key)
        
        # S3 client for accessing videos with profile support
        aws_profile = os.environ.get('AWS_PROFILE')
        if aws_profile:
            session = boto3.Session(profile_name=aws_profile)
            self.s3_client = session.client('s3')
        else:
            self.s3_client = boto3.client('s3')
        self.bucket_name = os.environ.get('S3_BUCKET', 'xenodx-video-archive')
        
        # OpenAI model info
        self.model_info = self._get_model_info()
        
        logger.info(f"OpenAIWhisperTranscriber initialized:")
        logger.info(f"  Model: {model}")
        logger.info(f"  Device: {self.device}")
        logger.info(f"  Language: {self.language}")
        logger.info(f"  API: OpenAI Whisper")
        
    def _normalize_language(self, language: str) -> str:
        """Normalize language code for OpenAI Whisper API"""
        # OpenAI Whisper supports ISO 639-1 language codes
        lang_mapping = {
            "auto": "en",  # Default to English for auto-detection
            "en-US": "en",
            "es-ES": "es",
            "fr-FR": "fr",
            "de-DE": "de",
            "it-IT": "it",
            "pt-BR": "pt"
        }
        return lang_mapping.get(language, language)
    
    def _get_model_info(self) -> Dict[str, Any]:
        """Get OpenAI Whisper model information and capabilities"""
        models = {
            "whisper-1": {
                "name": "Whisper-1",
                "description": "OpenAI's latest Whisper model with excellent accuracy and multilingual support",
                "accuracy": "very high",
                "speed": "fast", 
                "cost_per_minute": 0.006,
                "cost_per_15s": 0.0015,  # For comparison with other services
                "supports_video": True,
                "supports_streaming": False,
                "max_file_size_mb": 25,
                "supported_formats": ["m4a", "mp3", "webm", "mp4", "mpga", "wav", "mpeg"]
            }
        }
        return models.get(self.model, models["whisper-1"])
    
    def initialize_client(self) -> bool:
        """Initialize OpenAI client"""
        try:
            if not self.api_key:
                raise ValueError("OpenAI API key is required")
            
            logger.info("Initializing OpenAI Whisper client...")
            # Client is already initialized in __init__
            logger.info("✅ OpenAI client initialized")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to initialize OpenAI client: {e}")
            return False
    
    def load_model(self) -> bool:
        """Validate OpenAI Whisper model configuration"""
        if not self.initialize_client():
            return False
            
        try:
            logger.info(f"Configuring OpenAI Whisper model '{self.model}'...")
            
            # Verify model is supported (currently only whisper-1)
            if self.model != "whisper-1":
                logger.warning(f"⚠️  Model '{self.model}' not recognized, using 'whisper-1'")
                self.model = "whisper-1"
                self.model_info = self._get_model_info()
            
            logger.info(f"✅ Model configured: {self.model_info['name']}")
            logger.info(f"   Description: {self.model_info['description']}")
            logger.info(f"   Accuracy: {self.model_info['accuracy']}")
            logger.info(f"   Speed: {self.model_info['speed']}")
            logger.info(f"   Cost: ${self.model_info['cost_per_15s']}/15s")
            logger.info(f"   Video support: {self.model_info['supports_video']}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to configure model: {e}")
            return False
    
    
    def generate_presigned_url(self, s3_key: str, expiration: int = 3600) -> str:
        """Generate presigned URL for S3 object access"""
        try:
            presigned_url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket_name, 'Key': s3_key},
                ExpiresIn=expiration
            )
            logger.info(f"Generated presigned URL for {s3_key}")
            return presigned_url
        except Exception as e:
            logger.error(f"Failed to generate presigned URL: {e}")
            raise
    
    def transcribe_from_url(self, audio_url: str) -> Dict[str, Any]:
        """Transcribe audio file using OpenAI Whisper API from URL"""
        if not self.load_model():
            raise Exception("Failed to initialize OpenAI client")
        
        temp_file = None
        try:
            logger.info(f"Transcribing audio from URL with OpenAI Whisper '{self.model}'...")
            start_time = time.time()
            
            # Step 1: Download audio file from S3 presigned URL
            logger.info("Downloading audio file from S3...")
            response = requests.get(audio_url, stream=True)
            response.raise_for_status()
            
            # Check file size (OpenAI has 25MB limit)
            content_length = response.headers.get('content-length')
            if content_length and int(content_length) > 25 * 1024 * 1024:
                raise ValueError(f"File size ({int(content_length)/1024/1024:.1f}MB) exceeds OpenAI's 25MB limit")
            
            # Step 2: Save to temporary file
            temp_file = tempfile.NamedTemporaryFile(suffix='.mp4', delete=False)
            for chunk in response.iter_content(chunk_size=8192):
                temp_file.write(chunk)
            temp_file.close()
            
            logger.info(f"Audio file downloaded to temporary location ({os.path.getsize(temp_file.name)/1024/1024:.1f}MB)")
            
            # Step 3: Transcribe with OpenAI Whisper API
            logger.info("Starting OpenAI Whisper transcription...")
            with open(temp_file.name, 'rb') as audio_file:
                transcript_response = self.client.audio.transcriptions.create(
                    model=self.model,
                    file=audio_file,
                    response_format="verbose_json",
                    language=self.language if self.language != "auto" else None
                )
            
            duration = time.time() - start_time
            
            # Step 4: Process results and format for compatibility
            full_transcript = transcript_response.text
            language_detected = getattr(transcript_response, 'language', self.language)
            
            # Extract segments if available
            segments = []
            word_info = []
            if hasattr(transcript_response, 'segments') and transcript_response.segments:
                for segment in transcript_response.segments:
                    segments.append({
                        'start': segment.start,
                        'end': segment.end,
                        'text': segment.text
                    })
                    
                    # Extract word-level information if available
                    if hasattr(segment, 'words') and segment.words:
                        for word in segment.words:
                            word_info.append({
                                'word': word.word,
                                'start_time': word.start,
                                'end_time': word.end,
                                'confidence': getattr(word, 'confidence', 1.0)  # Whisper doesn't provide word confidence
                            })
            
            transcript_length = len(full_transcript.strip())
            logger.info(f"✅ Transcribed in {duration:.1f}s ({transcript_length} chars)")
            logger.info(f"   Detected language: {language_detected}")
            
            # Calculate cost estimate
            file_size_mb = os.path.getsize(temp_file.name) / 1024 / 1024
            # Rough estimate: 1MB ≈ 1 minute of audio
            estimated_minutes = file_size_mb
            cost_estimate = estimated_minutes * 0.006
            
            # Build result in compatible format
            result = {
                'success': True,
                'text': full_transcript.strip(),
                'transcript': full_transcript.strip(),  # For compatibility with existing code
                'segments': segments,
                'language': self.language,
                'processing_time': duration,
                'model_used': self.model,
                'device_used': self.device,
                'language_detected': language_detected,
                'confidence': 1.0,  # OpenAI doesn't provide overall confidence
                'word_timestamps': word_info,
                'service': 'openai-whisper',
                'cost_estimate': cost_estimate,
                'file_size_mb': file_size_mb
            }
            
            return result
            
        except Exception as e:
            logger.error(f"OpenAI Whisper transcription failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'service': 'openai-whisper'
            }
        
        finally:
            # Cleanup temporary file
            if temp_file and os.path.exists(temp_file.name):
                try:
                    os.unlink(temp_file.name)
                except:
                    pass  # Ignore cleanup errors
    
    def transcribe(self, s3_key: str) -> Dict[str, Any]:
        """
        Main transcription method - generate presigned URL and transcribe with OpenAI Whisper
        
        Args:
            s3_key: S3 key of the audio/video file
            
        Returns:
            Transcription result with text and metadata
        """
        try:
            # Generate presigned URL for OpenAI Whisper API access
            presigned_url = self.generate_presigned_url(s3_key, expiration=3600)
            
            # Transcribe using OpenAI Whisper API
            result = self.transcribe_from_url(presigned_url)
            
            # Add S3 metadata
            result['s3_key'] = s3_key
            result['s3_bucket'] = self.bucket_name
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to transcribe {s3_key}: {e}")
            return {
                'success': False,
                'error': str(e),
                'service': 'openai-whisper',
                's3_key': s3_key
            }
    
    def get_system_info(self) -> Dict[str, Any]:
        """Get system information for diagnostics"""
        info = {
            "model": self.model,
            "device": self.device,
            "language": self.language,
            "model_info": self.model_info,
            "api_key_configured": bool(self.api_key),
            "service": "openai-whisper"
        }
        
        # Add OpenAI Whisper API info
        try:
            if self.client:
                info["openai_whisper"] = {
                    "client_initialized": True,
                    "model_configured": True,
                    "model_name": self.model_info.get('name', 'Unknown'),
                    "supports_video": self.model_info.get('supports_video', False),
                    "cost_per_minute": self.model_info.get('cost_per_minute', 0.0),
                    "max_file_size_mb": self.model_info.get('max_file_size_mb', 25)
                }
            else:
                info["openai_whisper"] = {
                    "client_initialized": False,
                    "model_configured": False
                }
                
            # Test basic connectivity (simple API availability check)
            try:
                if self.client and self.api_key:
                    info["openai_whisper"]["connectivity"] = "configured"
                else:
                    info["openai_whisper"]["connectivity"] = "not configured"
            except Exception as e:
                info["openai_whisper"]["connectivity"] = f"failed: {e}"
                
        except ImportError:
            info["openai_whisper"] = {
                "error": "openai not installed",
                "client_initialized": False
            }
        
        return info
    
    def benchmark_model(self, test_duration: int = 10) -> Dict[str, Any]:
        """Benchmark Google Speech API transcription speed"""
        logger.info(f"Benchmarking Google Speech model '{self.model_size}'...")
        logger.info(f"Note: This will use actual Google Speech API calls and incur costs")
        
        try:
            # For benchmarking, we need a real audio file since Google Speech API
            # requires actual audio content. We'll create a simple test audio.
            import numpy as np
            sample_rate = 16000
            
            # Create test audio with some variation (not just silence)
            # Simple sine wave pattern so Google Speech has something to process
            t = np.linspace(0, test_duration, sample_rate * test_duration)
            test_audio = (np.sin(2 * np.pi * 440 * t) * 0.1).astype(np.float32)  # 440Hz tone
            
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.wav')
            temp_path = Path(temp_file.name)
            temp_file.close()
            
            # Save as WAV file
            import scipy.io.wavfile
            scipy.io.wavfile.write(str(temp_path), sample_rate, (test_audio * 32767).astype(np.int16))
            
            logger.warning(f"Creating {test_duration}s test audio file for benchmark")
            logger.warning(f"This will cost approximately ${test_duration/15 * self.model_info['cost_per_15s']:.4f}")
            
            # Upload to S3 temporarily for testing
            test_s3_key = f"benchmark_test_{int(time.time())}.wav"
            logger.info(f"Uploading test file to S3: {test_s3_key}")
            
            self.s3_client.upload_file(str(temp_path), self.bucket_name, test_s3_key)
            
            try:
                # Benchmark transcription
                start_time = time.time()
                result = self.transcribe(test_s3_key)
                processing_time = time.time() - start_time
                
                # Calculate metrics
                # For cloud APIs, "realtime factor" is less meaningful since it includes network time
                benchmark = {
                    "test_duration_seconds": test_duration,
                    "processing_time_seconds": processing_time,
                    "transcript_length": len(result.get('text', '')),
                    "confidence": result.get('confidence', 0.0),
                    "cost_estimate": test_duration/15 * self.model_info['cost_per_15s'],
                    "model_used": result.get('model_used', self.model_size),
                    "service": "google-speech"
                }
                
                logger.info(f"Benchmark results:")
                logger.info(f"  Processing time: {processing_time:.1f}s")
                logger.info(f"  Transcript length: {benchmark['transcript_length']} chars")
                logger.info(f"  Confidence: {benchmark['confidence']:.2%}")
                logger.info(f"  Estimated cost: ${benchmark['cost_estimate']:.4f}")
                
                return benchmark
                
            finally:
                # Clean up S3 test file
                try:
                    self.s3_client.delete_object(Bucket=self.bucket_name, Key=test_s3_key)
                    logger.info(f"Cleaned up test file from S3")
                except:
                    logger.warning(f"Failed to clean up test file: {test_s3_key}")
                
                # Clean up local temp file
                temp_path.unlink()
            
        except Exception as e:
            logger.error(f"Benchmark failed: {e}")
            return {"error": str(e)}


def main():
    """Test the Google GPU transcriber"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Google GPU Transcriber')
    parser.add_argument('--model', default='chirp_2', 
                       choices=['chirp_2', 'latest_long', 'latest_short', 'video'],
                       help='Google Speech model')
    parser.add_argument('--language', default='en', 
                       help='Language code (en, es, fr, etc.)')
    parser.add_argument('--test', action='store_true',
                       help='Run system test')
    parser.add_argument('--benchmark', type=int, metavar='SECONDS',
                       help='Benchmark with N seconds of test audio')
    
    args = parser.parse_args()
    
    # Set up logging
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    
    # Create transcriber
    transcriber = GoogleGPUTranscriber(
        model_size=args.model,
        language=args.language
    )
    
    if args.test:
        print("\n🧪 OpenAI Whisper Transcriber Test")
        print("=" * 40)
        
        # Show system info
        info = transcriber.get_system_info()
        print(f"Model: {info['model']}")
        print(f"Language: {info['language']}")
        print(f"Service: {info['service']}")
        print(f"API Key Configured: {info['api_key_configured']}")
        
        if info['api_key_configured']:
            print("\n✅ OpenAI Whisper transcriber ready for use!")
            print("\n💡 To transcribe a video:")
            print("   result = transcriber.transcribe_from_url('your_s3_presigned_url')")
        else:
            print("\n❌ Please set OPENAI_API_KEY environment variable")
    else:
        print("Use --test to run basic system test")


if __name__ == "__main__":
    main()