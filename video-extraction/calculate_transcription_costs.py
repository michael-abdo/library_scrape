#!/usr/bin/env python3
"""
Calculate transcription costs for uploaded videos
"""
import sqlite3
import json
import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def calculate_transcription_costs():
    """Calculate transcription costs for different services"""
    
    # Connect to database
    db_path = "../library_videos.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get uploaded videos count
    cursor.execute("""
        SELECT COUNT(*) 
        FROM videos 
        WHERE s3_key IS NOT NULL
    """)
    total_videos = cursor.fetchone()[0]
    
    # Average video duration (based on your typical videos being 45-90 minutes)
    avg_duration_minutes = 75
    total_minutes = total_videos * avg_duration_minutes
    total_hours = total_minutes / 60
    
    print(f"\n📊 Transcription Cost Analysis")
    print(f"{'='*60}")
    print(f"📹 Videos in S3: {total_videos:,}")
    print(f"⏱️  Estimated average duration: {avg_duration_minutes} minutes")
    print(f"📏 Total content: {total_minutes:,} minutes ({total_hours:,.1f} hours)")
    
    print(f"\n💰 Transcription Service Costs:")
    print(f"{'='*60}")
    
    # AWS Transcribe pricing
    aws_price_per_minute = 0.024  # $0.024 per minute
    aws_total = total_minutes * aws_price_per_minute
    print(f"\n1. AWS Transcribe:")
    print(f"   Price: ${aws_price_per_minute:.3f} per minute")
    print(f"   Total cost: ${aws_total:,.2f}")
    print(f"   Features: Speaker diarization, custom vocabulary, real-time")
    
    # OpenAI Whisper API pricing
    whisper_price_per_minute = 0.006  # $0.006 per minute
    whisper_total = total_minutes * whisper_price_per_minute
    print(f"\n2. OpenAI Whisper API:")
    print(f"   Price: ${whisper_price_per_minute:.3f} per minute")
    print(f"   Total cost: ${whisper_total:,.2f}")
    print(f"   Features: 99+ language support, high accuracy")
    
    # Google Cloud Speech-to-Text pricing
    google_price_per_minute = 0.016  # $0.016 per minute (standard model)
    google_total = total_minutes * google_price_per_minute
    print(f"\n3. Google Cloud Speech-to-Text:")
    print(f"   Price: ${google_price_per_minute:.3f} per minute")
    print(f"   Total cost: ${google_total:,.2f}")
    print(f"   Features: Real-time, speaker diarization, word confidence")
    
    # Assembly AI pricing
    assembly_price_per_hour = 0.65  # $0.65 per hour
    assembly_total = total_hours * assembly_price_per_hour
    print(f"\n4. AssemblyAI:")
    print(f"   Price: ${assembly_price_per_hour:.2f} per hour")
    print(f"   Total cost: ${assembly_total:,.2f}")
    print(f"   Features: Speaker diarization, entity detection, sentiment")
    
    # Behavioral Signals (estimate based on enterprise pricing)
    behavioral_estimate = total_videos * 5  # Estimated $5 per video for full analysis
    print(f"\n5. Behavioral Signals (Full Analysis):")
    print(f"   Estimated: ~${behavioral_estimate:,.2f}")
    print(f"   Features: Transcription + emotion + speaker analysis + deepfake")
    print(f"   Note: Enterprise pricing, actual costs may vary")
    
    # Hume AI (estimate)
    hume_estimate = total_videos * 3  # Estimated $3 per video
    print(f"\n6. Hume AI:")
    print(f"   Estimated: ~${hume_estimate:,.2f}")
    print(f"   Features: Transcription + emotion detection")
    print(f"   Note: Pricing depends on plan")
    
    # Local Whisper (self-hosted)
    print(f"\n7. Self-Hosted Whisper (Open Source):")
    print(f"   Software cost: $0 (open source)")
    print(f"   Compute cost (GPU):")
    
    # GPU compute estimates
    gpu_hours_needed = total_hours * 0.5  # Whisper processes ~2x realtime on good GPU
    gpu_cost_per_hour = 0.50  # Typical cloud GPU cost
    gpu_total = gpu_hours_needed * gpu_cost_per_hour
    print(f"     - Cloud GPU: ${gpu_total:,.2f} (at ${gpu_cost_per_hour}/hour)")
    print(f"     - Local GPU: $0 (if you have one)")
    print(f"   Features: Complete privacy, customizable, no API limits")
    
    # Summary
    print(f"\n🎯 Recommendations:")
    print(f"{'='*60}")
    print(f"1. **Most Cost-Effective**: OpenAI Whisper API (${whisper_total:,.2f})")
    print(f"2. **Best Features**: AWS Transcribe (${aws_total:,.2f})")
    print(f"3. **Free Option**: Self-hosted Whisper (GPU required)")
    print(f"4. **Full Analysis**: Behavioral Signals (~${behavioral_estimate:,.2f})")
    
    # Cost per video comparison
    print(f"\n📊 Cost Per Video ({avg_duration_minutes} min):")
    print(f"   Whisper API: ${(whisper_price_per_minute * avg_duration_minutes):.2f}")
    print(f"   AWS Transcribe: ${(aws_price_per_minute * avg_duration_minutes):.2f}")
    print(f"   Google Speech: ${(google_price_per_minute * avg_duration_minutes):.2f}")
    print(f"   AssemblyAI: ${(assembly_price_per_hour * avg_duration_minutes / 60):.2f}")
    
    conn.close()

if __name__ == "__main__":
    calculate_transcription_costs()