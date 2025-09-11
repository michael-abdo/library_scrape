#!/usr/bin/env python3
"""
Whisper API Client for programmatic transcription
Supports both OpenAI Whisper API and self-hosted alternatives
"""
import os
import json
import time
import boto3
import logging
import tempfile
import requests
from typing import Optional, Dict, Any
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

class WhisperAPIClient:
    """Client for transcribing audio using Whisper API"""
    
    def __init__(self, api_key: Optional[str] = None, service: str = "openai"):
        """
        Initialize Whisper API client
        
        Args:
            api_key: API key for the service
            service: Service to use ("openai", "replicate", or "huggingface")
        """
        self.service = service
        self.api_key = api_key or os.environ.get(f"{service.upper()}_API_KEY")
        
        if not self.api_key and service != "huggingface":
            raise ValueError(f"No API key provided for {service}")
        
        # S3 client for downloading audio
        self.s3_client = boto3.client('s3')
        self.bucket_name = 'xenodex-video-archive'
        
        # Service-specific endpoints
        self.endpoints = {
            "openai": "https://api.openai.com/v1/audio/transcriptions",
            "replicate": "https://api.replicate.com/v1/predictions",
            "huggingface": "https://api-inference.huggingface.co/models/openai/whisper-large-v3"
        }
        
    def download_from_s3(self, s3_key: str) -> Path:
        """Download file from S3 to temporary location"""
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4')
        temp_path = Path(temp_file.name)
        
        try:
            logger.info(f"Downloading {s3_key} from S3...")
            self.s3_client.download_file(self.bucket_name, s3_key, str(temp_path))
            return temp_path
        except Exception as e:
            logger.error(f"Failed to download from S3: {e}")
            if temp_path.exists():
                temp_path.unlink()
            raise
            
    def transcribe_openai(self, audio_path: Path) -> Dict[str, Any]:
        """Transcribe using OpenAI Whisper API"""
        headers = {
            "Authorization": f"Bearer {self.api_key}"
        }
        
        with open(audio_path, 'rb') as audio_file:
            files = {
                'file': (audio_path.name, audio_file, 'audio/mp4'),
                'model': (None, 'whisper-1'),
                'language': (None, 'en'),
                'response_format': (None, 'json')
            }
            
            response = requests.post(
                self.endpoints["openai"],
                headers=headers,
                files=files,
                timeout=600  # 10 minute timeout for long files
            )
            
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"OpenAI API error: {response.status_code} - {response.text}")
            
    def transcribe_replicate(self, audio_path: Path) -> Dict[str, Any]:
        """Transcribe using Replicate's Whisper model"""
        # First, upload the file or provide URL
        headers = {
            "Authorization": f"Token {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # For Replicate, we need to upload to their service or provide a URL
        # This is a simplified version - in production you'd upload to temp storage
        payload = {
            "version": "30414ee7c4fffc37e260fcab7842b5be470b9b840f2b608f5baa9bbef9a259ed",
            "input": {
                "audio": f"file://{audio_path}",  # This would need to be a public URL
                "model": "large-v3",
                "language": "en",
                "translate": False
            }
        }
        
        response = requests.post(
            self.endpoints["replicate"],
            headers=headers,
            json=payload
        )
        
        if response.status_code == 201:
            prediction = response.json()
            # Poll for completion
            return self._poll_replicate_prediction(prediction['id'])
        else:
            raise Exception(f"Replicate API error: {response.status_code} - {response.text}")
            
    def _poll_replicate_prediction(self, prediction_id: str) -> Dict[str, Any]:
        """Poll Replicate for prediction completion"""
        headers = {
            "Authorization": f"Token {self.api_key}"
        }
        
        while True:
            response = requests.get(
                f"https://api.replicate.com/v1/predictions/{prediction_id}",
                headers=headers
            )
            
            if response.status_code == 200:
                result = response.json()
                if result['status'] == 'succeeded':
                    return {'text': result['output']['transcription']}
                elif result['status'] == 'failed':
                    raise Exception(f"Replicate prediction failed: {result.get('error')}")
                    
                time.sleep(5)  # Poll every 5 seconds
            else:
                raise Exception(f"Replicate API error: {response.status_code}")
                
    def transcribe_huggingface(self, audio_path: Path) -> Dict[str, Any]:
        """Transcribe using HuggingFace Inference API (free tier)"""
        headers = {
            "Authorization": f"Bearer {self.api_key}"
        } if self.api_key else {}
        
        with open(audio_path, 'rb') as audio_file:
            response = requests.post(
                self.endpoints["huggingface"],
                headers=headers,
                data=audio_file.read(),
                timeout=300
            )
            
        if response.status_code == 200:
            result = response.json()
            return {'text': result.get('text', '')}
        else:
            raise Exception(f"HuggingFace API error: {response.status_code} - {response.text}")
            
    def transcribe(self, s3_key: str) -> Dict[str, Any]:
        """
        Transcribe audio file from S3
        
        Args:
            s3_key: S3 key of the audio file
            
        Returns:
            Transcription result with 'text' field
        """
        temp_path = None
        
        try:
            # Download from S3
            temp_path = self.download_from_s3(s3_key)
            
            # Check file size for API limits
            file_size_mb = temp_path.stat().st_size / (1024 * 1024)
            logger.info(f"File size: {file_size_mb:.1f} MB")
            
            # OpenAI has a 25MB limit
            if self.service == "openai" and file_size_mb > 25:
                logger.warning(f"File too large for OpenAI Whisper API ({file_size_mb:.1f} MB > 25 MB)")
                # Could implement chunking here
                raise ValueError("File too large for API")
                
            # Transcribe based on service
            if self.service == "openai":
                result = self.transcribe_openai(temp_path)
            elif self.service == "replicate":
                result = self.transcribe_replicate(temp_path)
            elif self.service == "huggingface":
                result = self.transcribe_huggingface(temp_path)
            else:
                raise ValueError(f"Unknown service: {self.service}")
                
            return result
            
        finally:
            # Clean up temp file
            if temp_path and temp_path.exists():
                temp_path.unlink()
                
    def estimate_cost(self, duration_minutes: float) -> float:
        """Estimate cost for transcription"""
        costs_per_minute = {
            "openai": 0.006,
            "replicate": 0.01,  # Approximate
            "huggingface": 0.0  # Free tier
        }
        
        return costs_per_minute.get(self.service, 0) * duration_minutes
        

class TranscriptionChunker:
    """Handle large files by chunking for API limits"""
    
    @staticmethod
    def chunk_audio(audio_path: Path, max_size_mb: float = 24) -> list[Path]:
        """
        Split audio file into chunks under the size limit
        
        Args:
            audio_path: Path to audio file
            max_size_mb: Maximum size per chunk in MB
            
        Returns:
            List of paths to chunk files
        """
        # This would use ffmpeg to split the audio
        # Implementation depends on ffmpeg being available
        pass