"""S3 Manager for direct video streaming to AWS S3."""
import boto3
import os
import sys
from typing import Optional, Dict
from botocore.exceptions import ClientError, NoCredentialsError
import time
import unicodedata


class S3UploadProgress:
    """Track S3 upload progress."""
    
    def __init__(self, total_size: int):
        self.total_size = total_size
        self.uploaded = 0
        self.start_time = time.time()
        
    def __call__(self, bytes_amount):
        self.uploaded += bytes_amount
        percentage = (self.uploaded / self.total_size) * 100
        elapsed_time = time.time() - self.start_time
        
        if elapsed_time > 0:
            upload_speed = self.uploaded / elapsed_time
            speed_mb = upload_speed / (1024 * 1024)
            
            print(f"\rProgress: {percentage:.1f}% ({self.uploaded}/{self.total_size} bytes) "
                  f"Speed: {speed_mb:.2f} MB/s", end="", flush=True)
        
        if self.uploaded >= self.total_size:
            print()  # New line when complete


def clean_metadata_value(value: str) -> str:
    """Convert non-ASCII characters to ASCII-safe equivalents."""
    if not value:
        return value
    
    # Common replacements
    replacements = {
        '…': '...',
        '—': '--',  # Em dash
        '–': '-',   # En dash
        ''': "'",   # Left single quote
        ''': "'",   # Right single quote
        '"': '"',   # Left double quote
        '"': '"',   # Right double quote
        '•': '*',   # Bullet
        '™': '(TM)',
        '®': '(R)',
        '©': '(C)',
        '°': ' degrees',
        '±': '+/-',
        '×': 'x',
        '÷': '/',
        '≈': '~',
        '≤': '<=',
        '≥': '>=',
        '≠': '!=',
        '∞': 'infinity',
        '€': 'EUR',
        '£': 'GBP',
        '¥': 'JPY',
        '¢': 'cents',
        '§': 'section',
        '¶': 'paragraph',
        '†': '+',
        '‡': '++',
        '‰': 'per mille',
        '′': "'",   # Prime
        '″': '"',   # Double prime
        '‹': '<',
        '›': '>',
        '«': '<<',
        '»': '>>',
    }
    
    # Apply replacements
    for char, replacement in replacements.items():
        value = value.replace(char, replacement)
    
    # Normalize remaining Unicode characters to ASCII
    # First try NFKD normalization (compatibility decomposition)
    normalized = unicodedata.normalize('NFKD', value)
    ascii_value = normalized.encode('ascii', 'ignore').decode('ascii')
    
    # If we lost too much content, try a more conservative approach
    if len(ascii_value) < len(value) * 0.5:
        # Just replace non-ASCII with '?'
        ascii_value = ''.join(c if ord(c) < 128 else '?' for c in value)
    
    # Clean up any double spaces or weird formatting
    ascii_value = ' '.join(ascii_value.split())
    
    return ascii_value


class S3Manager:
    """Manage S3 operations for video storage."""
    
    def __init__(self, bucket_name: Optional[str] = None, region: str = "us-west-2"):
        """Initialize S3 client with credentials."""
        self.bucket_name = bucket_name or os.getenv('S3_BUCKET', 'xenodx-video-archive')
        self.region = os.getenv('AWS_DEFAULT_REGION', region)
        
        try:
            # Initialize S3 client with profile support
            aws_profile = os.getenv('AWS_PROFILE', 'zenex')
            if aws_profile:
                # Use specific profile
                session = boto3.Session(profile_name=aws_profile)
                self.s3_client = session.client('s3', region_name=self.region)
            else:
                # Use default credentials
                self.s3_client = boto3.client('s3', region_name=self.region)
            
            # Verify bucket exists
            self._ensure_bucket_exists()
            
        except NoCredentialsError:
            print("AWS credentials not found. Please configure AWS CLI or set environment variables.")
            sys.exit(1)
        except Exception as e:
            print(f"Failed to initialize S3 client: {e}")
            sys.exit(1)
    
    def _ensure_bucket_exists(self):
        """Create bucket if it doesn't exist."""
        try:
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            print(f"✓ S3 bucket '{self.bucket_name}' exists")
        except ClientError as e:
            error_code = int(e.response['Error']['Code'])
            if error_code == 404:
                print(f"Creating S3 bucket '{self.bucket_name}'...")
                try:
                    if self.region == 'us-east-1':
                        self.s3_client.create_bucket(Bucket=self.bucket_name)
                    else:
                        self.s3_client.create_bucket(
                            Bucket=self.bucket_name,
                            CreateBucketConfiguration={'LocationConstraint': self.region}
                        )
                    print(f"✓ Created S3 bucket '{self.bucket_name}'")
                except Exception as create_error:
                    print(f"Failed to create bucket: {create_error}")
                    raise
            else:
                raise
    
    def stream_video_to_s3(self, video_response, s3_key: str, total_size: int, 
                          metadata: Optional[Dict[str, str]] = None) -> bool:
        """Stream video directly from HTTP response to S3."""
        try:
            # Prepare extra arguments
            extra_args = {
                'ContentType': 'video/mp4',
                'StorageClass': 'GLACIER_IR'  # Glacier Instant Retrieval
            }
            
            if metadata:
                # Clean metadata values to ensure ASCII compatibility
                cleaned_metadata = {}
                for key, value in metadata.items():
                    cleaned_key = clean_metadata_value(str(key))
                    cleaned_value = clean_metadata_value(str(value))
                    cleaned_metadata[cleaned_key] = cleaned_value
                extra_args['Metadata'] = cleaned_metadata
            
            # Create progress callback
            progress = S3UploadProgress(total_size)
            
            print(f"Streaming video to S3: s3://{self.bucket_name}/{s3_key}")
            
            # Stream directly to S3
            self.s3_client.upload_fileobj(
                video_response.raw,
                self.bucket_name,
                s3_key,
                ExtraArgs=extra_args,
                Callback=progress
            )
            
            print(f"✓ Successfully uploaded to S3: {s3_key}")
            return True
            
        except Exception as e:
            print(f"✗ Failed to upload to S3: {e}")
            return False
    
    def check_s3_exists(self, s3_key: str) -> bool:
        """Check if object exists in S3."""
        try:
            self.s3_client.head_object(Bucket=self.bucket_name, Key=s3_key)
            return True
        except ClientError:
            return False
    
    def get_presigned_url(self, s3_key: str, expiration: int = 3600) -> Optional[str]:
        """Generate presigned URL for S3 object."""
        try:
            url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket_name, 'Key': s3_key},
                ExpiresIn=expiration
            )
            return url
        except Exception as e:
            print(f"Failed to generate presigned URL: {e}")
            return None
    
    def delete_object(self, s3_key: str) -> bool:
        """Delete object from S3."""
        try:
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=s3_key)
            return True
        except Exception as e:
            print(f"Failed to delete S3 object: {e}")
            return False