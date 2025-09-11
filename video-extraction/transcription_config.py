"""
Transcription Configuration
"""
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class TranscriptionConfig:
    """Configuration for transcription services"""
    
    # Service selection
    DEFAULT_SERVICE = os.getenv('TRANSCRIPTION_SERVICE', 'openai')
    
    # API Keys
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    REPLICATE_API_TOKEN = os.getenv('REPLICATE_API_TOKEN')
    HUGGINGFACE_API_KEY = os.getenv('HUGGINGFACE_API_KEY')
    
    # Processing settings
    BATCH_SIZE = int(os.getenv('TRANSCRIPTION_BATCH_SIZE', '10'))
    MAX_FILE_SIZE_MB = float(os.getenv('TRANSCRIPTION_MAX_FILE_SIZE_MB', '25'))
    ENABLE_AUTO_TRANSCRIPTION = os.getenv('ENABLE_AUTO_TRANSCRIPTION', 'false').lower() == 'true'
    
    # Retry settings
    MAX_RETRIES = 3
    RETRY_DELAY = 30  # seconds
    
    # Rate limiting
    DELAY_BETWEEN_REQUESTS = 5  # seconds
    
    # Service-specific settings
    SERVICE_CONFIGS = {
        'openai': {
            'model': 'whisper-1',
            'language': 'en',
            'max_file_size_mb': 25,
            'cost_per_minute': 0.006
        },
        'replicate': {
            'model_version': '30414ee7c4fffc37e260fcab7842b5be470b9b840f2b608f5baa9bbef9a259ed',
            'model_name': 'large-v3',
            'cost_per_minute': 0.01  # Approximate
        },
        'huggingface': {
            'model_id': 'openai/whisper-large-v3',
            'cost_per_minute': 0.0  # Free tier
        }
    }
    
    @classmethod
    def get_api_key(cls, service: str) -> str:
        """Get API key for specified service"""
        key_map = {
            'openai': cls.OPENAI_API_KEY,
            'replicate': cls.REPLICATE_API_TOKEN,
            'huggingface': cls.HUGGINGFACE_API_KEY
        }
        return key_map.get(service)
    
    @classmethod
    def validate_config(cls, service: str = None) -> bool:
        """Validate configuration for specified service"""
        service = service or cls.DEFAULT_SERVICE
        
        if service not in cls.SERVICE_CONFIGS:
            print(f"❌ Unknown service: {service}")
            return False
            
        api_key = cls.get_api_key(service)
        if not api_key and service != 'huggingface':
            print(f"❌ No API key configured for {service}")
            print(f"   Set {service.upper()}_API_KEY in .env file")
            return False
            
        return True
    
    @classmethod
    def estimate_cost(cls, num_videos: int, avg_duration_minutes: float = 75) -> dict:
        """Estimate transcription costs for different services"""
        total_minutes = num_videos * avg_duration_minutes
        
        costs = {}
        for service, config in cls.SERVICE_CONFIGS.items():
            cost_per_minute = config.get('cost_per_minute', 0)
            costs[service] = {
                'total_cost': total_minutes * cost_per_minute,
                'per_video': avg_duration_minutes * cost_per_minute
            }
            
        return costs