#!/usr/bin/env python3
"""
Utility to generate presigned URLs for S3 files

Usage:
    python presign_s3_url.py s3://bucket/path/to/file.ext
    python presign_s3_url.py bucket/path/to/file.ext
    python presign_s3_url.py https://bucket.s3.amazonaws.com/path/to/file.ext
    python presign_s3_url.py path/to/file.ext --bucket my-bucket
    python presign_s3_url.py file1.ext file2.ext --bucket my-bucket
"""

import argparse
import sys
import re
import boto3
from botocore.exceptions import ClientError
from urllib.parse import urlparse


def parse_s3_url(url):
    """Parse various S3 URL formats and return bucket and key"""
    
    # Handle s3:// URLs
    if url.startswith('s3://'):
        parts = url[5:].split('/', 1)
        if len(parts) == 2:
            return parts[0], parts[1]
        else:
            raise ValueError(f"Invalid S3 URL format: {url}")
    
    # Handle https:// S3 URLs
    elif url.startswith('https://'):
        parsed = urlparse(url)
        # Format: https://bucket.s3.amazonaws.com/key
        if '.s3.amazonaws.com' in parsed.netloc:
            bucket = parsed.netloc.split('.s3.amazonaws.com')[0]
            key = parsed.path.lstrip('/')
            return bucket, key
        # Format: https://s3.amazonaws.com/bucket/key
        elif parsed.netloc == 's3.amazonaws.com':
            path_parts = parsed.path.lstrip('/').split('/', 1)
            if len(path_parts) == 2:
                return path_parts[0], path_parts[1]
        raise ValueError(f"Unrecognized S3 URL format: {url}")
    
    # Handle bucket/key format
    elif '/' in url:
        parts = url.split('/', 1)
        return parts[0], parts[1]
    
    # Just a key, bucket must be specified separately
    else:
        return None, url


def generate_presigned_url(bucket, key, expiration=3600, profile='zenex'):
    """Generate a presigned URL for an S3 object"""
    
    try:
        # Create S3 client with specified profile
        session = boto3.Session(profile_name=profile)
        s3_client = session.client('s3')
        
        # Generate presigned URL
        url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': bucket, 'Key': key},
            ExpiresIn=expiration
        )
        
        return url
        
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'NoSuchKey':
            print(f"Error: Object not found: s3://{bucket}/{key}")
        elif error_code == 'NoSuchBucket':
            print(f"Error: Bucket not found: {bucket}")
        elif error_code == 'AccessDenied':
            print(f"Error: Access denied to s3://{bucket}/{key}")
        else:
            print(f"Error generating presigned URL: {e}")
        return None
    except Exception as e:
        print(f"Error: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(
        description='Generate presigned URLs for S3 files',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    %(prog)s s3://my-bucket/path/to/file.mp4
    %(prog)s my-bucket/path/to/file.mp4
    %(prog)s https://my-bucket.s3.amazonaws.com/path/to/file.mp4
    %(prog)s path/to/file.mp4 --bucket my-bucket
    %(prog)s file1.mp4 file2.json --bucket my-bucket --expiration 7200
        """
    )
    
    parser.add_argument('urls', nargs='+', help='S3 URLs or keys to generate presigned URLs for')
    parser.add_argument('--bucket', '-b', help='S3 bucket name (if not included in URL)')
    parser.add_argument('--expiration', '-e', type=int, default=3600,
                        help='URL expiration time in seconds (default: 3600)')
    parser.add_argument('--profile', '-p', default='zenex',
                        help='AWS profile to use (default: zenex)')
    
    args = parser.parse_args()
    
    # Process each URL
    for url in args.urls:
        bucket, key = parse_s3_url(url)
        
        # Use command-line bucket if provided and URL didn't contain one
        if not bucket and args.bucket:
            bucket = args.bucket
        elif not bucket:
            print(f"Error: No bucket specified for '{url}'. Use --bucket option or include bucket in URL.")
            continue
        
        # Default bucket for this project
        if bucket == 'xenodx' or bucket == 'xenodex':
            bucket = 'xenodx-video-archive'
        
        print(f"\nGenerating presigned URL for: s3://{bucket}/{key}")
        print(f"Expiration: {args.expiration} seconds")
        
        presigned_url = generate_presigned_url(bucket, key, args.expiration, args.profile)
        
        if presigned_url:
            print(f"Presigned URL: {presigned_url}")
        else:
            print(f"Failed to generate presigned URL for s3://{bucket}/{key}")


if __name__ == '__main__':
    main()