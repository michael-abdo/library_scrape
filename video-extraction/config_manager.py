"""Configuration manager for video downloader."""
import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional


class ConfigManager:
    """Manage configuration from YAML and environment variables."""
    
    def __init__(self, config_dir: Optional[str] = None):
        """Initialize configuration manager."""
        self.config_dir = Path(config_dir) if config_dir else Path(__file__).parent.parent / "config"
        self.config = self._load_config()
        
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML and environment."""
        config = {
            's3': {
                'default_bucket': os.getenv('S3_BUCKET', 'op-videos-storage'),
                'region': os.getenv('AWS_REGION', 'us-west-2'),
                'key_prefix': os.getenv('S3_KEY_PREFIX', 'videos/'),
            },
            'download': {
                'chunk_size': int(os.getenv('DOWNLOAD_CHUNK_SIZE', '8192')),
                'timeout': int(os.getenv('DOWNLOAD_TIMEOUT', '300')),
                'max_retries': int(os.getenv('DOWNLOAD_MAX_RETRIES', '3')),
            }
        }
        
        # Try to load from YAML file
        yaml_path = self.config_dir / "config.yaml"
        if yaml_path.exists():
            try:
                with open(yaml_path, 'r') as f:
                    yaml_config = yaml.safe_load(f)
                    if yaml_config:
                        self._deep_merge(config, yaml_config)
            except Exception as e:
                print(f"Warning: Failed to load config.yaml: {e}")
        
        return config
    
    def _deep_merge(self, base: dict, update: dict):
        """Deep merge two dictionaries."""
        for key, value in update.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._deep_merge(base[key], value)
            else:
                base[key] = value
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value using dot notation."""
        keys = key.split('.')
        value = self.config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def get_s3_config(self) -> Dict[str, Any]:
        """Get S3 configuration."""
        return self.config.get('s3', {})
    
    def get_download_config(self) -> Dict[str, Any]:
        """Get download configuration."""
        return self.config.get('download', {})