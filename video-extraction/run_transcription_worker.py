#!/usr/bin/env python3
"""
Automated Transcription Worker
Runs continuously to transcribe videos that have been uploaded to S3
"""
import os
import sys
import time
import logging
from datetime import datetime
import subprocess

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from transcription_pipeline import TranscriptionPipeline
from transcription_config import TranscriptionConfig

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('transcription_worker.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

def run_detached_worker():
    """Run the transcription worker in detached mode"""
    cmd = [
        sys.executable,
        __file__,
        "--worker"
    ]
    
    log_file = f"transcription_worker_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    
    with open(log_file, 'w') as log:
        process = subprocess.Popen(
            cmd,
            stdout=log,
            stderr=log,
            start_new_session=True
        )
        
    print(f"✅ Transcription worker started (PID: {process.pid})")
    print(f"📄 Log file: {log_file}")
    print(f"🛑 To stop: kill {process.pid}")
    
    # Save PID for easy stopping
    with open('transcription_worker.pid', 'w') as f:
        f.write(str(process.pid))

def stop_worker():
    """Stop the running worker"""
    try:
        with open('transcription_worker.pid', 'r') as f:
            pid = int(f.read().strip())
            
        os.kill(pid, 15)  # SIGTERM
        print(f"✅ Stopped worker (PID: {pid})")
        os.remove('transcription_worker.pid')
    except FileNotFoundError:
        print("❌ No worker PID file found")
    except ProcessLookupError:
        print(f"❌ Process {pid} not found")
        os.remove('transcription_worker.pid')

def run_worker():
    """Run the transcription worker continuously"""
    logger.info("Starting Transcription Worker")
    
    # Validate configuration
    if not TranscriptionConfig.validate_config():
        logger.error("Invalid configuration. Exiting.")
        return
        
    # Get configuration
    service = TranscriptionConfig.DEFAULT_SERVICE
    api_key = TranscriptionConfig.get_api_key(service)
    batch_size = TranscriptionConfig.BATCH_SIZE
    
    logger.info(f"Configuration:")
    logger.info(f"  Service: {service}")
    logger.info(f"  Batch size: {batch_size}")
    logger.info(f"  Auto-transcription: {TranscriptionConfig.ENABLE_AUTO_TRANSCRIPTION}")
    
    # Create pipeline
    pipeline = TranscriptionPipeline(
        service=service,
        api_key=api_key
    )
    
    # Run continuously
    try:
        pipeline.run_continuous(
            batch_size=batch_size,
            wait_between_batches=60
        )
    except KeyboardInterrupt:
        logger.info("Worker stopped by user")
    except Exception as e:
        logger.error(f"Worker error: {e}")
        raise

def check_worker_status():
    """Check if worker is running"""
    try:
        with open('transcription_worker.pid', 'r') as f:
            pid = int(f.read().strip())
            
        # Check if process exists
        os.kill(pid, 0)
        print(f"✅ Worker is running (PID: {pid})")
        
        # Show recent progress
        pipeline = TranscriptionPipeline()
        progress = pipeline.get_progress_report()
        print(f"\n📊 Transcription Progress:")
        print(f"  Total videos: {progress['total_videos']}")
        print(f"  Videos in S3: {progress['videos_in_s3']}")
        print(f"  Transcribed: {progress['transcribed']}")
        print(f"  Pending: {progress['pending']}")
        print(f"  Failed: {progress['failed']}")
        
    except FileNotFoundError:
        print("❌ Worker is not running (no PID file)")
    except ProcessLookupError:
        print(f"❌ Worker process {pid} is not running")
        os.remove('transcription_worker.pid')

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Transcription Worker Manager')
    parser.add_argument('action', nargs='?', default='status',
                       choices=['start', 'stop', 'status', 'restart'],
                       help='Worker action')
    parser.add_argument('--worker', action='store_true',
                       help='Run as worker (internal use)')
    
    args = parser.parse_args()
    
    if args.worker:
        # Running as the actual worker
        run_worker()
    else:
        # Managing the worker
        if args.action == 'start':
            run_detached_worker()
        elif args.action == 'stop':
            stop_worker()
        elif args.action == 'restart':
            stop_worker()
            time.sleep(2)
            run_detached_worker()
        elif args.action == 'status':
            check_worker_status()

if __name__ == "__main__":
    main()