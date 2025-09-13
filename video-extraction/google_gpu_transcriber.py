#!/usr/bin/env python3
"""
Google GPU Transcriber
Cloud-based transcription using Google Cloud Speech-to-Text on Google's GPU infrastructure
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
from google.cloud import speech

logger = logging.getLogger(__name__)

class GoogleGPUTranscriber:
    """Google Cloud GPU-based Speech-to-Text transcriber"""
    
    def __init__(self, model_size: str = "chirp_2", device: str = "google-gpu", language: str = "en"):
        """
        Initialize Google GPU transcriber
        
        Args:
            model_size: Google Speech model (chirp_2, latest_long, latest_short, video, etc.)
            device: Device identifier (always "google-gpu")
            language: Language code for transcription (en, en-US, auto, etc.)
        """
        self.model_size = model_size
        self.language = self._normalize_language(language)
        self.device = "google-gpu"  # Always using Google's GPU infrastructure
        self.project_id = os.environ.get('GOOGLE_CLOUD_PROJECT', 'claude-code-dev-20250615-1851')
        
        # S3 client for accessing videos
        self.s3_client = boto3.client('s3')
        self.bucket_name = 'xenodx-video-archive'
        
        # Google Speech client and model info
        self.model_info = self._get_model_info()
        self.speech_client = None
        
        logger.info(f"GoogleGPUTranscriber initialized:")
        logger.info(f"  Model: {model_size}")
        logger.info(f"  Device: {self.device}")
        logger.info(f"  Language: {self.language}")
        logger.info(f"  Project: {self.project_id}")
        
    def _normalize_language(self, language: str) -> str:
        """Normalize language code for Google Speech API"""
        # Map common language codes to Google Speech format
        lang_mapping = {
            "en": "en-US",
            "es": "es-ES", 
            "fr": "fr-FR",
            "de": "de-DE",
            "it": "it-IT",
            "pt": "pt-BR",
            "auto": "en-US"  # Default to English for auto-detection
        }
        return lang_mapping.get(language, language)
    
    def _get_model_info(self) -> Dict[str, Any]:
        """Get Google Speech model information and capabilities"""
        models = {
            "chirp_2": {
                "name": "Chirp 2",
                "description": "Latest universal speech model with enhanced multilingual support",
                "accuracy": "highest",
                "speed": "fast", 
                "cost_per_15s": 0.012,
                "supports_video": True,
                "supports_streaming": True
            },
            "latest_long": {
                "name": "Latest Long",
                "description": "Optimized for longer audio files",
                "accuracy": "high",
                "speed": "medium",
                "cost_per_15s": 0.009,
                "supports_video": True,
                "supports_streaming": False
            },
            "latest_short": {
                "name": "Latest Short", 
                "description": "Optimized for shorter audio files",
                "accuracy": "high",
                "speed": "fast",
                "cost_per_15s": 0.009,
                "supports_video": True,
                "supports_streaming": True
            },
            "video": {
                "name": "Video Model",
                "description": "Specialized for video content transcription",
                "accuracy": "high",
                "speed": "fast",
                "cost_per_15s": 0.009,
                "supports_video": True,
                "supports_streaming": False
            }
        }
        return models.get(self.model_size, models["chirp_2"])
    
    def initialize_speech_client(self) -> bool:
        """Initialize Google Cloud Speech client"""
        try:
            logger.info("Initializing Google Cloud Speech client...")
            self.speech_client = speech.SpeechClient()
            logger.info("✅ Google Speech client initialized")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to initialize Speech client: {e}")
            return False
    
    def load_model(self) -> bool:
        """Initialize Google Speech client and model configuration"""
        if not self.initialize_speech_client():
            return False
            
        try:
            logger.info(f"Configuring Google Speech model '{self.model_size}'...")
            
            # Verify model is supported
            if self.model_size not in self.model_info:
                logger.warning(f"⚠️  Model '{self.model_size}' not recognized, using 'chirp_2'")
                self.model_size = "chirp_2"
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
    
    def _get_speech_config(self) -> speech.RecognitionConfig:
        """Get Google Speech recognition configuration"""
        return speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.MP3,  # Support MP3/MP4 video files
            sample_rate_hertz=16000,  # Will be auto-detected if not specified
            language_code=self.language,
            model=self.model_size if self.model_size != "chirp_2" else "chirp",  # Map chirp_2 to chirp
            enable_automatic_punctuation=True,
            enable_word_time_offsets=True,
            enable_word_confidence=True,
            audio_channel_count=1,  # Mono audio
            use_enhanced=True,  # Use enhanced models when available
        )
    
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
        """Transcribe audio file using Google Speech API from URL"""
        if not self.speech_client:
            if not self.load_model():
                raise Exception("Failed to initialize Google Speech client")
        
        try:
            logger.info(f"Transcribing audio from URL with Google Speech '{self.model_size}'...")
            start_time = time.time()
            
            # Create audio object from URL
            audio = speech.RecognitionAudio(uri=audio_url)
            
            # Get recognition configuration
            config = self._get_speech_config()
            
            # For longer audio files, use long_running_recognize
            logger.info("Starting long-running recognition...")
            operation = self.speech_client.long_running_recognize(
                config=config, 
                audio=audio
            )
            
            logger.info("Waiting for transcription to complete...")
            response = operation.result(timeout=1800)  # 30 minute timeout
            
            duration = time.time() - start_time
            
            # Process results
            full_transcript = ""
            word_info = []
            confidence_scores = []
            
            for result in response.results:
                alternative = result.alternatives[0]
                full_transcript += alternative.transcript + " "
                
                if hasattr(alternative, 'confidence'):
                    confidence_scores.append(alternative.confidence)
                
                # Collect word-level information
                if hasattr(alternative, 'words'):
                    for word in alternative.words:
                        word_info.append({
                            'word': word.word,
                            'start_time': word.start_time.total_seconds(),
                            'end_time': word.end_time.total_seconds(),
                            'confidence': getattr(word, 'confidence', 0.0)
                        })
            
            # Calculate average confidence
            avg_confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0.0
            
            transcript_length = len(full_transcript.strip())
            logger.info(f"✅ Transcribed in {duration:.1f}s ({transcript_length} chars)")
            logger.info(f"   Average confidence: {avg_confidence:.2%}")
            
            # Build result in Whisper-compatible format
            result = {
                'text': full_transcript.strip(),
                'segments': [],  # Could be populated from word info if needed
                'language': self.language,
                'processing_time': duration,
                'model_used': self.model_size,
                'device_used': self.device,
                'language_detected': self.language,
                'confidence': avg_confidence,
                'word_timestamps': word_info,
                'service': 'google-speech'
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Google Speech transcription failed: {e}")
            raise
    
    def transcribe(self, s3_key: str) -> Dict[str, Any]:
        """
        Main transcription method - generate presigned URL and transcribe with Google Speech
        
        Args:
            s3_key: S3 key of the audio/video file
            
        Returns:
            Transcription result with text and metadata
        """
        try:
            # Generate presigned URL for Google Speech API access
            presigned_url = self.generate_presigned_url(s3_key, expiration=3600)
            
            # Transcribe using Google Speech API
            result = self.transcribe_from_url(presigned_url)
            
            # Add S3 metadata
            result['s3_key'] = s3_key
            result['s3_bucket'] = self.bucket_name
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to transcribe {s3_key}: {e}")
            raise
    
    def get_system_info(self) -> Dict[str, Any]:
        """Get system information for diagnostics"""
        info = {
            "model_size": self.model_size,
            "device": self.device,
            "language": self.language,
            "model_info": self.model_info,
            "project_id": self.project_id,
            "service": "google-speech"
        }
        
        # Add Google Cloud Speech API info
        try:
            if self.speech_client:
                info["google_speech"] = {
                    "client_initialized": True,
                    "model_configured": True,
                    "model_name": self.model_info.get('name', 'Unknown'),
                    "supports_video": self.model_info.get('supports_video', False),
                    "supports_streaming": self.model_info.get('supports_streaming', False),
                    "cost_per_15s": self.model_info.get('cost_per_15s', 0.0)
                }
            else:
                info["google_speech"] = {
                    "client_initialized": False,
                    "model_configured": False
                }
                
            # Test basic connectivity
            try:
                # Try to initialize client if not done already
                if not self.speech_client:
                    test_client = speech.SpeechClient()
                    info["google_speech"]["connectivity"] = "ok"
                else:
                    info["google_speech"]["connectivity"] = "ok"
            except Exception as e:
                info["google_speech"]["connectivity"] = f"failed: {e}"
                
        except ImportError:
            info["google_speech"] = {
                "error": "google-cloud-speech not installed",
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
        print("\n🔍 System Information:")
        info = transcriber.get_system_info()
        for key, value in info.items():
            if isinstance(value, dict):
                print(f"{key}:")
                for k, v in value.items():
                    print(f"  {k}: {v}")
            else:
                print(f"{key}: {value}")
    
    if args.benchmark:
        benchmark = transcriber.benchmark_model(args.benchmark)
        print(f"\n⚡ Benchmark Results:")
        for key, value in benchmark.items():
            print(f"{key}: {value}")


if __name__ == "__main__":
    main()