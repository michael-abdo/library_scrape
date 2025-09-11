"""
Google GPU Transcription Configuration
"""
import os
from typing import Dict, Any

class TranscriptionConfig:
    """Configuration for Google Cloud Speech-to-Text GPU transcription"""
    
    # Google Cloud Configuration
    GOOGLE_CLOUD_PROJECT = os.getenv('GOOGLE_CLOUD_PROJECT', 'claude-code-dev-20250615-1851')
    GOOGLE_APPLICATION_CREDENTIALS = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
    
    # Google Speech Models and Settings
    DEFAULT_MODEL = os.getenv('GOOGLE_SPEECH_MODEL', 'chirp_2')  # chirp_2, latest_long, latest_short, video
    LANGUAGE = os.getenv('GOOGLE_SPEECH_LANGUAGE', 'en-US')  # en-US, es-ES, fr-FR, etc.
    
    # Processing Settings
    BATCH_SIZE = int(os.getenv('TRANSCRIPTION_BATCH_SIZE', '10'))  # Google GPU can handle more
    ENABLE_AUTO_TRANSCRIPTION = os.getenv('ENABLE_AUTO_TRANSCRIPTION', 'true').lower() == 'true'
    
    # Processing Queue Settings
    MAX_CONCURRENT_JOBS = int(os.getenv('MAX_CONCURRENT_JOBS', '3'))  # Google GPU can handle more
    PROCESSING_TIMEOUT = int(os.getenv('PROCESSING_TIMEOUT', '1800'))  # 30 minutes per video
    
    # Retry Settings
    MAX_RETRIES = int(os.getenv('TRANSCRIPTION_MAX_RETRIES', '3'))
    RETRY_DELAY = int(os.getenv('TRANSCRIPTION_RETRY_DELAY', '30'))  # seconds
    
    
    # Model Information
    MODEL_INFO = {
        'chirp_2': {
            'name': 'Chirp 2',
            'description': 'Latest universal speech model with enhanced multilingual support',
            'accuracy': 'highest',
            'speed': 'fast',
            'cost_per_15s': 0.012,
            'supports_video': True,
            'supports_streaming': True,
            'use_case': 'best overall accuracy and language support'
        },
        'latest_long': {
            'name': 'Latest Long',
            'description': 'Optimized for longer audio files',
            'accuracy': 'high', 
            'speed': 'medium',
            'cost_per_15s': 0.009,
            'supports_video': True,
            'supports_streaming': False,
            'use_case': 'long-form content transcription'
        },
        'latest_short': {
            'name': 'Latest Short',
            'description': 'Optimized for shorter audio files',
            'accuracy': 'high',
            'speed': 'fast',
            'cost_per_15s': 0.009,
            'supports_video': True,
            'supports_streaming': True,
            'use_case': 'short clips and real-time processing'
        },
        'video': {
            'name': 'Video Model',
            'description': 'Specialized for video content transcription',
            'accuracy': 'high',
            'speed': 'fast',
            'cost_per_15s': 0.009,
            'supports_video': True,
            'supports_streaming': False,
            'use_case': 'video-specific audio enhancement'
        }
    }
    
    @classmethod
    def get_model_info(cls, model: str = None) -> Dict[str, Any]:
        """Get information about a Google Speech model"""
        model = model or cls.DEFAULT_MODEL
        return cls.MODEL_INFO.get(model, cls.MODEL_INFO['chirp_2'])
    
    
    
    @classmethod
    def validate_config(cls) -> Dict[str, Any]:
        """Validate Google GPU transcription configuration"""
        issues = []
        warnings = []
        
        # Check model exists
        if cls.DEFAULT_MODEL not in cls.MODEL_INFO:
            issues.append(f"Unknown Google Speech model: {cls.DEFAULT_MODEL}")
        
        # Check Google Cloud project
        if not cls.GOOGLE_CLOUD_PROJECT:
            issues.append("GOOGLE_CLOUD_PROJECT not configured")
        
        # Check batch size
        if cls.BATCH_SIZE < 1 or cls.BATCH_SIZE > 50:
            warnings.append(f"Batch size {cls.BATCH_SIZE} may be inefficient for Google GPU")
        
        return {
            'valid': len(issues) == 0,
            'issues': issues,
            'warnings': warnings,
            'config': {
                'model': cls.DEFAULT_MODEL,
                'language': cls.LANGUAGE,
                'batch_size': cls.BATCH_SIZE,
                'project_id': cls.GOOGLE_CLOUD_PROJECT
            }
        }
    
    @classmethod
    def estimate_processing_cost(cls, num_videos: int, avg_duration_minutes: float = 75) -> Dict[str, Any]:
        """Estimate processing cost for Google GPU transcription"""
        model_info = cls.get_model_info()
        cost_per_15s = model_info['cost_per_15s']
        
        # Calculate total duration in 15-second increments
        total_duration_seconds = num_videos * avg_duration_minutes * 60
        billing_increments = total_duration_seconds / 15
        total_cost = billing_increments * cost_per_15s
        
        return {
            'num_videos': num_videos,
            'avg_video_duration': avg_duration_minutes,
            'model_used': cls.DEFAULT_MODEL,
            'cost_per_15s': cost_per_15s,
            'total_duration_hours': total_duration_seconds / 3600,
            'total_cost_usd': total_cost,
            'cost_per_video': total_cost / num_videos if num_videos > 0 else 0
        }
    
    @classmethod
    def get_installation_requirements(cls) -> Dict[str, Any]:
        """Get installation requirements for Google GPU transcription"""
        return {
            'python_packages': [
                'google-cloud-speech',
                'google-auth',
                'boto3',
                'requests'
            ],
            'environment_variables': {
                'GOOGLE_CLOUD_PROJECT': 'Your Google Cloud project ID',
                'GOOGLE_APPLICATION_CREDENTIALS': 'Path to service account key file',
                'AWS_ACCESS_KEY_ID': 'For S3 access to videos',
                'AWS_SECRET_ACCESS_KEY': 'For S3 access to videos'
            },
            'google_cloud_setup': {
                'enable_speech_api': 'Enable Cloud Speech-to-Text API in your project',
                'service_account': 'Create service account with Speech API permissions',
                'billing': 'Ensure billing is enabled for API usage'
            }
        }


def main():
    """Test configuration and show diagnostics"""
    print("☁️  Google GPU Transcription Configuration")
    print("=" * 50)
    
    validation = TranscriptionConfig.validate_config()
    
    print(f"Valid Configuration: {'✅' if validation['valid'] else '❌'}")
    
    if validation['issues']:
        print("\n❌ Issues:")
        for issue in validation['issues']:
            print(f"   - {issue}")
    
    if validation['warnings']:
        print("\n⚠️  Warnings:")
        for warning in validation['warnings']:
            print(f"   - {warning}")
    
    print(f"\n📊 Current Configuration:")
    config = validation['config']
    for key, value in config.items():
        print(f"   {key}: {value}")
    
    print(f"\n🎯 Model Information ({config['model']}):")
    model_info = TranscriptionConfig.get_model_info()
    for key, value in model_info.items():
        print(f"   {key}: {value}")
    
    print(f"\n💰 Cost Estimates (336 videos):")
    estimates = TranscriptionConfig.estimate_processing_cost(336, 75)
    for key, value in estimates.items():
        if key not in ['num_videos', 'avg_video_duration']:
            print(f"   {key}: {value}")
    
    print(f"\n📦 Installation Requirements:")
    requirements = TranscriptionConfig.get_installation_requirements()
    print(f"   Python packages: {', '.join(requirements['python_packages'])}")
    print(f"   Environment: {requirements['environment_variables']}")
    print(f"   Google Cloud: {requirements['google_cloud_setup']}")


if __name__ == "__main__":
    main()