#!/usr/bin/env python3
import boto3
from botocore.config import Config

# Initialize S3 client with zenex profile
session = boto3.Session(profile_name='zenex')
s3_client = session.client(
    's3',
    region_name='us-west-2',
    config=Config(signature_version='s3v4')
)

bucket = 'xenodx-video-archive'

print("Checking for transcripts in S3...")
try:
    # First check all prefixes
    print("\nChecking all top-level prefixes in bucket...")
    response = s3_client.list_objects_v2(
        Bucket=bucket,
        Delimiter='/',
        MaxKeys=50
    )
    
    if 'CommonPrefixes' in response:
        print("Prefixes found:")
        for prefix in response['CommonPrefixes']:
            print(f"  - {prefix['Prefix']}")
    
    # List objects with transcripts prefix
    print("\nChecking transcripts prefix...")
    response = s3_client.list_objects_v2(
        Bucket=bucket,
        Prefix='transcripts/',
        MaxKeys=20
    )
    
    if 'Contents' in response:
        print(f"\nFound {len(response['Contents'])} transcript files:")
        json_transcripts = []
        
        for obj in response['Contents']:
            key = obj['Key']
            size = obj['Size']
            print(f"  - {key} ({size:,} bytes)")
            
            # Collect JSON transcripts
            if key.endswith('.json'):
                json_transcripts.append(key)
        
        # Generate presigned URL for first JSON transcript
        if json_transcripts:
            first_json = json_transcripts[0]
            print(f"\nGenerating presigned URL for: {first_json}")
            
            presigned_url = s3_client.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': bucket,
                    'Key': first_json
                },
                ExpiresIn=3600
            )
            print(f"\nPresigned URL (valid for 1 hour):\n{presigned_url}")
        else:
            print("\nNo JSON transcripts found")
    else:
        print("No transcripts found in S3")
        
except Exception as e:
    print(f"Error: {e}")