"""
Transcription Service Configuration
Supports OpenAI Whisper API and Google Cloud Speech-to-Text
"""
import os
from typing import Dict, Any
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class TranscriptionConfig:
    """Configuration for OpenAI Whisper API and Google Cloud Speech-to-Text transcription"""
    
    # Service Selection (OpenAI is default due to 87.5% cost savings)
    DEFAULT_SERVICE = os.getenv('TRANSCRIPTION_SERVICE', 'openai')  # 'openai' or 'google'
    
    # OpenAI Whisper Configuration
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    OPENAI_MODEL = os.getenv('OPENAI_WHISPER_MODEL', 'whisper-1')
    
    # Google Cloud Configuration (fallback)
    GOOGLE_CLOUD_PROJECT = os.getenv('GOOGLE_CLOUD_PROJECT', 'claude-code-dev-20250615-1851')
    GOOGLE_APPLICATION_CREDENTIALS = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
    GOOGLE_MODEL = os.getenv('GOOGLE_SPEECH_MODEL', 'latest_long')  # Changed default for cost
    
    # Common Language Setting
    LANGUAGE = os.getenv('TRANSCRIPTION_LANGUAGE', 'en')  # en, es, fr, etc.
    
    # Processing Settings
    BATCH_SIZE = int(os.getenv('TRANSCRIPTION_BATCH_SIZE', '10'))  # Google GPU can handle more
    ENABLE_AUTO_TRANSCRIPTION = os.getenv('ENABLE_AUTO_TRANSCRIPTION', 'true').lower() == 'true'
    
    # Processing Queue Settings
    MAX_CONCURRENT_JOBS = int(os.getenv('MAX_CONCURRENT_JOBS', '3'))  # Google GPU can handle more
    PROCESSING_TIMEOUT = int(os.getenv('PROCESSING_TIMEOUT', '1800'))  # 30 minutes per video
    
    # Retry Settings
    MAX_RETRIES = int(os.getenv('TRANSCRIPTION_MAX_RETRIES', '3'))
    RETRY_DELAY = int(os.getenv('TRANSCRIPTION_RETRY_DELAY', '30'))  # seconds
    
    
    # Model Information for Both Services
    MODEL_INFO = {
        # OpenAI Whisper Models
        'whisper-1': {
            'service': 'openai',
            'name': 'Whisper-1',
            'description': 'OpenAI\'s production Whisper model - 87.5% cheaper than Google!',
            'accuracy': 'very high',
            'speed': 'fast',
            'cost_per_minute': 0.006,
            'cost_per_15s': 0.0015,
            'supports_video': True,
            'supports_streaming': False,
            'max_file_size_mb': 25,
            'use_case': 'Most cost-effective option for all content types'
        },
        
        # Google Cloud Speech Models
        'chirp_2': {
            'service': 'google',
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
    def get_model_info(cls, model: str = None, service: str = None) -> Dict[str, Any]:
        """Get information about a transcription model"""
        if not service:
            service = cls.DEFAULT_SERVICE
        
        if not model:
            model = cls.OPENAI_MODEL if service == 'openai' else cls.GOOGLE_MODEL
        
        return cls.MODEL_INFO.get(model, cls.MODEL_INFO['whisper-1'])  # Default to cheapest
    
    @classmethod
    def get_recommended_model(cls, service: str = None) -> str:
        """Get recommended model based on cost and performance"""
        if not service:
            service = cls.DEFAULT_SERVICE
        
        if service == 'openai':
            return 'whisper-1'  # Only option, but 87.5% cheaper
        else:  # google
            return 'latest_long'  # Best balance for 75-min videos
    
    
    
    @classmethod
    def validate_config(cls, service: str = None) -> Dict[str, Any]:
        """Validate transcription service configuration"""
        service = service or cls.DEFAULT_SERVICE
        issues = []
        warnings = []
        
        # Validate service selection
        if service not in ['openai', 'google']:
            issues.append(f"Invalid service '{service}'. Must be 'openai' or 'google'")
            service = 'openai'  # Default to cheapest
        
        # Service-specific validation
        if service == 'openai':
            # OpenAI Whisper validation
            if not cls.OPENAI_API_KEY:
                issues.append("OPENAI_API_KEY not configured")
            
            if cls.OPENAI_MODEL not in cls.MODEL_INFO:
                issues.append(f"Unknown OpenAI model: {cls.OPENAI_MODEL}")
            
            # Check for OpenAI-specific limits
            model_info = cls.get_model_info(cls.OPENAI_MODEL, 'openai')
            if model_info.get('max_file_size_mb', 25) < 25:
                warnings.append("OpenAI has a 25MB file size limit per request")
                
        else:  # google
            # Google Cloud validation
            if not cls.GOOGLE_CLOUD_PROJECT:
                issues.append("GOOGLE_CLOUD_PROJECT not configured")
            
            if cls.GOOGLE_MODEL not in cls.MODEL_INFO:
                issues.append(f"Unknown Google Speech model: {cls.GOOGLE_MODEL}")
            
            # Cost warning for expensive Google models
            if cls.GOOGLE_MODEL == 'chirp_2':
                warnings.append("chirp_2 is 8x more expensive than OpenAI Whisper ($0.048 vs $0.006/min)")
        
        # Common validation
        if cls.BATCH_SIZE < 1 or cls.BATCH_SIZE > 50:
            warnings.append(f"Batch size {cls.BATCH_SIZE} may be inefficient")
        
        # Language validation
        if not cls.LANGUAGE:
            warnings.append("Language not specified, using default")
        
        # Build config summary
        config = {
            'service': service,
            'language': cls.LANGUAGE,
            'batch_size': cls.BATCH_SIZE
        }
        
        if service == 'openai':
            config.update({
                'model': cls.OPENAI_MODEL,
                'api_key_configured': bool(cls.OPENAI_API_KEY)
            })
        else:
            config.update({
                'model': cls.GOOGLE_MODEL,
                'project_id': cls.GOOGLE_CLOUD_PROJECT
            })
        
        return {
            'valid': len(issues) == 0,
            'issues': issues,
            'warnings': warnings,
            'config': config,
            'service': service
        }
    
    @classmethod
    def estimate_processing_cost(cls, num_videos: int, avg_duration_minutes: float = 75, service: str = None, model: str = None) -> Dict[str, Any]:
        """Estimate processing cost for transcription service"""
        service = service or cls.DEFAULT_SERVICE
        model_info = cls.get_model_info(model, service)
        
        # Calculate cost based on service pricing model
        total_duration_minutes = num_videos * avg_duration_minutes
        total_duration_seconds = total_duration_minutes * 60
        
        if service == 'openai':
            # OpenAI charges per minute
            total_cost = total_duration_minutes * model_info['cost_per_minute']
            cost_per_unit = model_info['cost_per_minute']
            unit = 'minute'
        else:
            # Google charges per 15-second increment
            billing_increments = total_duration_seconds / 15
            total_cost = billing_increments * model_info['cost_per_15s']
            cost_per_unit = model_info['cost_per_15s']
            unit = '15s'
        
        return {
            'service': service,
            'model_used': model or (cls.OPENAI_MODEL if service == 'openai' else cls.GOOGLE_MODEL),
            'num_videos': num_videos,
            'avg_video_duration': avg_duration_minutes,
            'total_duration_hours': total_duration_seconds / 3600,
            'cost_per_unit': cost_per_unit,
            'billing_unit': unit,
            'total_cost_usd': total_cost,
            'cost_per_video': total_cost / num_videos if num_videos > 0 else 0
        }
    
    @classmethod
    def compare_service_costs(cls, num_videos: int = 336, avg_duration_minutes: float = 75) -> Dict[str, Any]:
        """Compare costs between OpenAI and Google services"""
        openai_cost = cls.estimate_processing_cost(num_videos, avg_duration_minutes, 'openai', 'whisper-1')
        google_best_cost = cls.estimate_processing_cost(num_videos, avg_duration_minutes, 'google', 'latest_long')
        google_premium_cost = cls.estimate_processing_cost(num_videos, avg_duration_minutes, 'google', 'chirp_2')
        
        # Calculate savings
        openai_total = openai_cost['total_cost_usd']
        google_best_total = google_best_cost['total_cost_usd']
        google_premium_total = google_premium_cost['total_cost_usd']
        
        savings_vs_google_best = google_best_total - openai_total
        savings_vs_google_premium = google_premium_total - openai_total
        
        return {
            'comparison_for': f'{num_videos} videos × {avg_duration_minutes} min',
            'openai_whisper': openai_cost,
            'google_best': google_best_cost,
            'google_premium': google_premium_cost,
            'savings': {
                'vs_google_best': {
                    'amount_usd': savings_vs_google_best,
                    'percentage': (savings_vs_google_best / google_best_total) * 100
                },
                'vs_google_premium': {
                    'amount_usd': savings_vs_google_premium,
                    'percentage': (savings_vs_google_premium / google_premium_total) * 100
                }
            },
            'recommendation': 'openai' if openai_total < min(google_best_total, google_premium_total) else 'google'
        }
    
    @classmethod
    def get_installation_requirements(cls, service: str = None) -> Dict[str, Any]:
        """Get installation requirements for transcription services"""
        service = service or cls.DEFAULT_SERVICE
        
        # Common requirements for both services
        common_packages = ['boto3', 'requests', 'tempfile']
        common_env = {
            'AWS_ACCESS_KEY_ID': 'For S3 access to videos',
            'AWS_SECRET_ACCESS_KEY': 'For S3 access to videos',
            'TRANSCRIPTION_SERVICE': f'Service to use: "openai" (recommended) or "google"',
            'TRANSCRIPTION_LANGUAGE': 'Language code (en, es, fr, etc.)'
        }
        
        requirements = {
            'service': service,
            'python_packages': common_packages.copy(),
            'environment_variables': common_env.copy()
        }
        
        if service == 'openai':
            # OpenAI Whisper requirements
            requirements['python_packages'].extend(['openai'])
            requirements['environment_variables'].update({
                'OPENAI_API_KEY': 'Your OpenAI API key (required)',
                'OPENAI_WHISPER_MODEL': 'whisper-1 (default)'
            })
            requirements['service_setup'] = {
                'get_api_key': 'Get API key from https://platform.openai.com/api-keys',
                'pricing': '$0.006/minute (87.5% cheaper than Google)',
                'file_limits': '25MB max file size per request',
                'supported_formats': 'm4a, mp3, webm, mp4, mpga, wav, mpeg'
            }
        else:
            # Google Cloud requirements
            requirements['python_packages'].extend(['google-cloud-speech', 'google-auth'])
            requirements['environment_variables'].update({
                'GOOGLE_CLOUD_PROJECT': 'Your Google Cloud project ID',
                'GOOGLE_APPLICATION_CREDENTIALS': 'Path to service account key file',
                'GOOGLE_SPEECH_MODEL': 'latest_long (recommended for cost)'
            })
            requirements['service_setup'] = {
                'enable_speech_api': 'Enable Cloud Speech-to-Text API in your project',
                'service_account': 'Create service account with Speech API permissions',
                'billing': 'Ensure billing is enabled for API usage',
                'pricing': '$0.036-0.048/minute (25-33% more expensive than OpenAI)'
            }
        
        # Add cost comparison
        if service == 'openai':
            requirements['cost_comparison'] = {
                'openai_whisper': '$151.20 for 336 videos (25,200 minutes)',
                'google_best': '$907.20 for same workload (500% more expensive)',
                'recommendation': 'OpenAI Whisper offers the best value'
            }
        
        return requirements


def main():
    """Test configuration and show diagnostics"""
    service = TranscriptionConfig.DEFAULT_SERVICE
    service_name = "OpenAI Whisper" if service == 'openai' else "Google Cloud Speech"
    
    print(f"🚀 {service_name} Transcription Configuration")
    print("=" * 60)
    
    validation = TranscriptionConfig.validate_config(service)
    
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
    print(f"   Setup: {requirements.get('service_setup', {})}")


if __name__ == "__main__":
    main()