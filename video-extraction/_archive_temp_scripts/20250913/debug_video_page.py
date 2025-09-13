#!/usr/bin/env python3
"""
Debug script to analyze video page content and find video URLs
"""

import requests
import json
import re
from pathlib import Path

def debug_video_page():
    """Debug what's actually in the video page"""
    
    # Load cookies
    with open('cookies.json', 'r') as f:
        cookies_data = json.load(f)
    
    # Create session with cookies
    session = requests.Session()
    for cookie in cookies_data:
        session.cookies.set(
            cookie['name'], 
            cookie['value'],
            domain=cookie.get('domain', '.objectivepersonality.com'),
            path=cookie.get('path', '/')
        )
    
    # Test URL
    url = "https://www.objectivepersonality.com/videos/marc-randolph"
    
    print(f"🔍 Analyzing: {url}")
    response = session.get(url)
    
    print(f"📊 Response: {response.status_code}")
    print(f"📏 Content length: {len(response.content):,} bytes")
    
    # Save content for analysis
    with open('debug_page_content.html', 'w', encoding='utf-8') as f:
        f.write(response.text)
    
    print(f"💾 Page content saved to debug_page_content.html")
    
    # Look for various video patterns
    patterns = {
        'Streamable': [
            r'streamable\.com/([a-z0-9]+)',
            r'cdn-cf-east\.streamable\.com/video/mp4/([a-z0-9]+)',
            r'streamable\.com/o/([a-z0-9]+)'
        ],
        'YouTube': [
            r'youtube\.com/watch\?v=([a-zA-Z0-9_-]+)',
            r'youtube\.com/embed/([a-zA-Z0-9_-]+)',
            r'youtu\.be/([a-zA-Z0-9_-]+)'
        ],
        'Vimeo': [
            r'vimeo\.com/([0-9]+)',
            r'player\.vimeo\.com/video/([0-9]+)'
        ],
        'Wistia': [
            r'fast\.wistia\.net/embed/iframe/([a-z0-9]+)',
            r'wistia\.com/medias/([a-z0-9]+)'
        ]
    }
    
    print(f"\n🎯 Searching for video patterns:")
    
    found_any = False
    for platform, platform_patterns in patterns.items():
        matches = []
        for pattern in platform_patterns:
            pattern_matches = re.findall(pattern, response.text, re.IGNORECASE)
            matches.extend(pattern_matches)
        
        if matches:
            found_any = True
            unique_matches = list(dict.fromkeys(matches))  # Remove duplicates
            print(f"   {platform}: {unique_matches}")
        else:
            print(f"   {platform}: None found")
    
    if not found_any:
        print(f"\n❌ No video patterns found!")
        
        # Look for common video-related keywords
        keywords = ['video', 'embed', 'iframe', 'src=', 'mp4', 'stream', 'player']
        print(f"\n🔍 Searching for video-related content:")
        
        for keyword in keywords:
            count = response.text.lower().count(keyword)
            print(f"   '{keyword}': {count} occurrences")
        
        # Look for iframe sources
        iframe_pattern = r'<iframe[^>]*src="([^"]*)"'
        iframes = re.findall(iframe_pattern, response.text, re.IGNORECASE)
        if iframes:
            print(f"\n📺 Found iframes:")
            for i, iframe in enumerate(iframes[:5], 1):  # Show first 5
                print(f"   {i}. {iframe}")
        
        # Look for script tags that might contain video data
        script_pattern = r'<script[^>]*>(.*?)</script>'
        scripts = re.findall(script_pattern, response.text, re.DOTALL | re.IGNORECASE)
        
        video_scripts = []
        for script in scripts:
            if any(word in script.lower() for word in ['video', 'stream', 'embed', 'player']):
                video_scripts.append(script[:200] + "..." if len(script) > 200 else script)
        
        if video_scripts:
            print(f"\n📜 Found {len(video_scripts)} scripts with video-related content:")
            for i, script in enumerate(video_scripts[:3], 1):  # Show first 3
                print(f"   Script {i}: {script}")

if __name__ == "__main__":
    debug_video_page()