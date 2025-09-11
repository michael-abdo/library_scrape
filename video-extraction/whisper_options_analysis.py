#!/usr/bin/env python3
"""
Analyze Whisper transcription options for current environment
"""

import subprocess
import os
import platform

def check_environment():
    """Check current environment capabilities"""
    print("🔍 Analyzing Whisper Transcription Options")
    print("=" * 60)
    
    # System info
    print("\n📊 Current System:")
    print(f"   CPU: Intel Xeon @ 2.20GHz (4 cores)")
    print(f"   RAM: 15 GB available")
    print(f"   GPU: None detected")
    print(f"   OS: {platform.system()} {platform.release()}")
    
    print("\n🎯 Your Options for Whisper Transcription:")
    print("=" * 60)
    
    # Option 1: CPU-only Whisper
    print("\n1. 🖥️  CPU-Only Whisper (This VM)")
    print("   Pros:")
    print("   - Can run immediately on current VM")
    print("   - No additional costs")
    print("   - Complete privacy")
    print("   Cons:")
    print("   - VERY slow (10-20x slower than GPU)")
    print("   - 75-min video might take 6-12 hours")
    print("   Setup:")
    print("   ```bash")
    print("   pip install openai-whisper")
    print("   whisper video.mp3 --model base")
    print("   ```")
    print("   Speed: ~0.1x realtime (10 hours processing = 1 hour audio)")
    
    # Option 2: Cloud GPU Instance
    print("\n\n2. ☁️  Cloud GPU Instance")
    print("   Pros:")
    print("   - Fast processing (2-4x realtime)")
    print("   - Pay only for what you use")
    print("   - No hardware investment")
    print("   Cons:")
    print("   - Hourly costs ($0.50-$3/hour)")
    print("   - Setup complexity")
    print("   - Data transfer time")
    
    print("\n   📦 Easiest Cloud GPU Options:")
    
    print("\n   A) Google Colab Pro ($10/month)")
    print("      - T4 GPU included")
    print("      - Simple notebook interface")
    print("      - 100 GB storage")
    print("      - Setup: 5 minutes")
    
    print("\n   B) Paperspace Gradient ($8/hour for A100)")
    print("      - Powerful GPUs")
    print("      - Pre-built ML templates")
    print("      - Setup: 10 minutes")
    print("      ```bash")
    print("      # One-click Whisper template available")
    print("      ```")
    
    print("\n   C) AWS EC2 g4dn.xlarge (~$0.526/hour)")
    print("      - T4 GPU")
    print("      - More control")
    print("      - Setup: 30 minutes")
    print("      ```bash")
    print("      # Launch instance with Deep Learning AMI")
    print("      # Pre-installed CUDA/PyTorch")
    print("      ```")
    
    print("\n   D) RunPod ($0.36/hour for 3080)")
    print("      - Cheapest option")
    print("      - Docker-based")
    print("      - Setup: 15 minutes")
    
    # Option 3: Whisper API
    print("\n\n3. 🌐 OpenAI Whisper API")
    print("   Pros:")
    print("   - Zero setup")
    print("   - Fastest to implement")
    print("   - No infrastructure")
    print("   Cons:")
    print("   - $0.006/minute ($0.45/video)")
    print("   - Requires internet")
    print("   - File size limits (25MB)")
    print("   Implementation:")
    print("   ```python")
    print("   # Already have code for this!")
    print("   openai.Audio.transcribe('whisper-1', audio_file)")
    print("   ```")
    
    # Option 4: Hybrid approach
    print("\n\n4. 🔄 Hybrid Approach")
    print("   - Use Whisper API for quick results")
    print("   - Set up cloud GPU for bulk processing")
    print("   - CPU-only for testing small files")
    
    print("\n\n💡 Recommendations for Your 296 Videos:")
    print("=" * 60)
    
    total_videos = 296
    avg_duration = 75  # minutes
    total_hours = total_videos * avg_duration / 60
    
    print(f"\n📊 Processing {total_videos} videos ({total_hours:.0f} hours):")
    
    print("\n1. Quick & Easy: Whisper API")
    print(f"   Cost: ${total_videos * 0.45:.2f}")
    print(f"   Time: ~{total_hours/2:.0f} hours (parallel processing)")
    print("   Setup: 10 minutes")
    
    print("\n2. Cost-Effective: Google Colab Pro + Whisper") 
    print(f"   Cost: $10/month + time")
    print(f"   Time: ~{total_hours/3:.0f} hours")
    print("   Setup: 30 minutes")
    
    print("\n3. Fastest: RunPod/Paperspace GPU")
    print(f"   Cost: ~${total_hours/3 * 0.36:.2f}")
    print(f"   Time: ~{total_hours/3:.0f} hours")
    print("   Setup: 1 hour")
    
    # Quick test
    print("\n\n🧪 Want to Test CPU Whisper Right Now?")
    print("=" * 60)
    print("Try with a SHORT audio file first:")
    print("```bash")
    print("# Install")
    print("pip install openai-whisper")
    print("")
    print("# Test with tiny model (39M parameters)")
    print("whisper short_audio.mp3 --model tiny --language en")
    print("")
    print("# For your 75-min videos (not recommended on CPU!):")
    print("whisper video.mp3 --model base --language en")
    print("```")
    
    print("\n⚡ Quick Cloud GPU Setup (RunPod):")
    print("1. Sign up at runpod.io")
    print("2. Deploy 'Whisper' template")
    print("3. Upload videos via web UI")
    print("4. Results download automatically")

if __name__ == "__main__":
    check_environment()