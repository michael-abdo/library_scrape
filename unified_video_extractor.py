#!/usr/bin/env python3
"""
Unified Video Extractor - Handles multiple video platforms
Supports: Streamable, YouTube, Vimeo, Wistia, and generic iframes
"""

import json
import requests
import websocket
import threading
import time
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse, parse_qs

class UnifiedVideoExtractor:
    def __init__(self, chrome_port: int = 9222):
        """Initialize unified extractor with Chrome WebSocket connection"""
        self.chrome_port = chrome_port
        self.cookies = self._load_cookies()
        print(f"✅ Loaded {len(self.cookies)} authentication cookies")
    
    def _load_cookies(self) -> List[dict]:
        """Load authentication cookies from file"""
        cookie_paths = [
            "cookies.json",
            "../cookies.json", 
            "/Users/Mike/Xenodex/library_scrape/cookies.json"
        ]
        
        for path in cookie_paths:
            if Path(path).exists():
                with open(path, 'r') as f:
                    return json.load(f)
        return []
    
    def extract_video_info(self, url: str) -> Dict[str, Optional[str]]:
        """Extract video information from any supported platform"""
        print(f"🎬 Processing: {url}")
        print(f"🔗 Connecting to Chrome on port {self.chrome_port}")
        
        result = {
            'streamable_id': None,
            'youtube_id': None,
            'vimeo_id': None,
            'wistia_id': None,
            'other_video_url': None,
            'platform': None,
            'error': None
        }
        
        try:
            # Get Chrome tabs
            response = requests.get(f'http://localhost:{self.chrome_port}/json/list', timeout=5)
            tabs = response.json()
            
            # Find OP tab
            op_tab = None
            for tab in tabs:
                if 'objectivepersonality.com' in tab.get('url', ''):
                    op_tab = tab
                    print(f"✅ Found OP tab: {tab.get('id')}")
                    break
            
            if not op_tab:
                # Use any available tab
                for tab in tabs:
                    if not tab.get('url', '').startswith(('chrome-extension:', 'chrome:', 'devtools:')):
                        op_tab = tab
                        print(f"⚠️  Using non-OP tab: {tab.get('id')}")
                        break
            
            if not op_tab:
                result['error'] = "No usable Chrome tabs available"
                return result
            
            ws_url = op_tab.get('webSocketDebuggerUrl')
            ws_result = {'html': None, 'done': False, 'error': None}
            
            def on_message(ws, message):
                try:
                    data = json.loads(message)
                    
                    if data.get('id') == 1:  # Page enable
                        print("✅ Page domain enabled")
                        ws.send(json.dumps({'id': 2, 'method': 'Network.enable', 'params': {}}))
                        
                    elif data.get('id') == 2:  # Network enable
                        print("✅ Network domain enabled, setting fresh cookies...")
                        # Set cookies
                        for i, cookie in enumerate(self.cookies[:15]):
                            command = {
                                'id': 100 + i,
                                'method': 'Network.setCookie',
                                'params': {
                                    'name': cookie['name'],
                                    'value': cookie['value'],
                                    'domain': cookie.get('domain', '.objectivepersonality.com'),
                                    'path': cookie.get('path', '/'),
                                    'secure': cookie.get('secure', False),
                                    'httpOnly': cookie.get('httpOnly', False)
                                }
                            }
                            ws.send(json.dumps(command))
                        
                        time.sleep(2)
                        ws.send(json.dumps({'id': 200, 'method': 'Page.navigate', 'params': {'url': url}}))
                    
                    elif data.get('id') == 200:  # Navigation complete
                        print("📍 Page navigated, waiting for content...")
                        time.sleep(15)  # Wait for JavaScript
                        
                        # Extract all video information
                        extraction_script = '''
                        (() => {
                            const findings = {
                                streamable: [],
                                youtube: [],
                                vimeo: [],
                                wistia: [],
                                iframes: [],
                                video_elements: []
                            };
                            
                            // Get full HTML
                            const html = document.documentElement.outerHTML;
                            
                            // 1. Streamable patterns
                            const streamableMatches = html.match(/streamable\\.com\\/([a-z0-9]{6,})/gi) || [];
                            const cdnMatches = html.match(/cdn-cf-east\\.streamable\\.com\\/image\\/([a-z0-9]+)/gi) || [];
                            findings.streamable = [...streamableMatches, ...cdnMatches];
                            
                            // 2. YouTube
                            document.querySelectorAll('iframe').forEach(iframe => {
                                const src = iframe.src || iframe.getAttribute('data-src') || '';
                                if (src.includes('youtube.com') || src.includes('youtu.be')) {
                                    findings.youtube.push(src);
                                }
                            });
                            
                            // Also check for YouTube embeds in data attributes
                            document.querySelectorAll('[data-video-id]').forEach(el => {
                                const videoId = el.getAttribute('data-video-id');
                                if (videoId && videoId.match(/^[a-zA-Z0-9_-]{11}$/)) {
                                    findings.youtube.push(videoId);
                                }
                            });
                            
                            // 3. Vimeo
                            document.querySelectorAll('iframe').forEach(iframe => {
                                const src = iframe.src || iframe.getAttribute('data-src') || '';
                                if (src.includes('vimeo.com') || src.includes('player.vimeo.com')) {
                                    findings.vimeo.push(src);
                                }
                            });
                            
                            // 4. Wistia
                            // Look for Wistia embeds and scripts
                            const wistiaElements = document.querySelectorAll('[class*="wistia"], [id*="wistia"]');
                            wistiaElements.forEach(el => {
                                const classes = el.className || '';
                                const id = el.id || '';
                                const match = (classes + ' ' + id).match(/wistia_[a-z0-9]{10}/i);
                                if (match) {
                                    findings.wistia.push(match[0]);
                                }
                            });
                            
                            // Also check scripts for Wistia
                            document.querySelectorAll('script').forEach(script => {
                                const src = script.src || '';
                                const content = script.innerHTML || '';
                                if (src.includes('wistia') || content.includes('wistia')) {
                                    const match = content.match(/[a-z0-9]{10}/);
                                    if (match) findings.wistia.push(match[0]);
                                }
                            });
                            
                            // 5. All iframes (for unknown platforms)
                            document.querySelectorAll('iframe').forEach(iframe => {
                                const src = iframe.src || iframe.getAttribute('data-src') || '';
                                if (src && !src.includes('recaptcha')) {
                                    findings.iframes.push({
                                        src: src,
                                        id: iframe.id,
                                        class: iframe.className
                                    });
                                }
                            });
                            
                            // 6. Video elements
                            document.querySelectorAll('video').forEach(video => {
                                const src = video.src || '';
                                const sources = Array.from(video.querySelectorAll('source')).map(s => s.src);
                                if (src || sources.length > 0) {
                                    findings.video_elements.push({
                                        src: src,
                                        sources: sources
                                    });
                                }
                            });
                            
                            return {
                                findings: findings,
                                pageInfo: {
                                    title: document.title,
                                    url: window.location.href,
                                    htmlSize: html.length
                                }
                            };
                        })()
                        ''';
                        
                        ws.send(json.dumps({
                            'id': 300,
                            'method': 'Runtime.evaluate',
                            'params': {
                                'expression': extraction_script,
                                'returnByValue': True
                            }
                        }))
                    
                    elif data.get('id') == 300:  # Extraction complete
                        result_data = data.get('result', {})
                        if 'result' in result_data and 'value' in result_data['result']:
                            ws_result['html'] = result_data['result']['value']
                            print(f"✅ Got extraction results")
                        
                        ws_result['done'] = True
                        ws.close()
                        
                except Exception as e:
                    ws_result['error'] = str(e)
                    ws_result['done'] = True
                    ws.close()
            
            def on_error(ws, error):
                ws_result['error'] = str(error)
                ws_result['done'] = True
            
            def on_open(ws):
                print("🔗 WebSocket connected")
                ws.send(json.dumps({'id': 1, 'method': 'Page.enable', 'params': {}}))
            
            # Connect
            ws = websocket.WebSocketApp(ws_url, on_open=on_open, on_message=on_message, on_error=on_error)
            ws_thread = threading.Thread(target=ws.run_forever)
            ws_thread.daemon = True
            ws_thread.start()
            
            # Wait
            timeout = 45
            while not ws_result['done'] and timeout > 0:
                time.sleep(0.5)
                timeout -= 0.5
            
            if ws_result['error']:
                result['error'] = ws_result['error']
                return result
            
            # Process extraction results
            if ws_result['html']:
                findings = ws_result['html'].get('findings', {})
                page_info = ws_result['html'].get('pageInfo', {})
                
                print(f"📄 Page: {page_info.get('title', 'Unknown')}")
                print(f"📏 HTML Size: {page_info.get('htmlSize', 0):,} bytes")
                
                # Extract IDs from each platform
                result.update(self._process_findings(findings))
            
            return result
            
        except Exception as e:
            result['error'] = str(e)
            return result
    
    def _process_findings(self, findings: Dict) -> Dict[str, Optional[str]]:
        """Process findings and extract video IDs"""
        result = {
            'streamable_id': None,
            'youtube_id': None,
            'vimeo_id': None,
            'wistia_id': None,
            'other_video_url': None,
            'platform': None
        }
        
        # 1. Streamable
        if findings.get('streamable'):
            for item in findings['streamable']:
                match = re.search(r'([a-z0-9]{6,})', item, re.IGNORECASE)
                if match:
                    streamable_id = match.group(1)
                    if len(streamable_id) >= 6:
                        if self._validate_streamable_id(streamable_id):
                            result['streamable_id'] = streamable_id
                            result['platform'] = 'streamable'
                            print(f"✅ Found Streamable: {streamable_id}")
                            break
        
        # 2. YouTube
        if findings.get('youtube'):
            for url_or_id in findings['youtube']:
                youtube_id = self._extract_youtube_id(url_or_id)
                if youtube_id:
                    result['youtube_id'] = youtube_id
                    if not result['platform']:
                        result['platform'] = 'youtube'
                    print(f"✅ Found YouTube: {youtube_id}")
                    break
        
        # 3. Vimeo
        if findings.get('vimeo'):
            for url in findings['vimeo']:
                vimeo_id = self._extract_vimeo_id(url)
                if vimeo_id:
                    result['vimeo_id'] = vimeo_id
                    if not result['platform']:
                        result['platform'] = 'vimeo'
                    print(f"✅ Found Vimeo: {vimeo_id}")
                    break
        
        # 4. Wistia
        if findings.get('wistia'):
            for item in findings['wistia']:
                match = re.search(r'([a-z0-9]{10})', item, re.IGNORECASE)
                if match:
                    wistia_id = match.group(1)
                    result['wistia_id'] = wistia_id
                    if not result['platform']:
                        result['platform'] = 'wistia'
                    print(f"✅ Found Wistia: {wistia_id}")
                    break
        
        # 5. Other video sources
        if not result['platform']:
            # Check iframes
            if findings.get('iframes'):
                for iframe in findings['iframes']:
                    src = iframe.get('src', '')
                    # Accept any iframe that looks like it could be a video player
                    # Exclude known non-video iframes
                    exclude_patterns = ['recaptcha', 'analytics', 'tracking', 'ads', 'facebook.com/plugins', 'twitter.com/widgets']
                    if src and not any(pattern in src.lower() for pattern in exclude_patterns):
                        # Check for video-related keywords or patterns
                        video_indicators = ['video', 'player', 'embed', 'media', 'stream', 'watch', 'herokuapp.com/worker']
                        if any(indicator in src.lower() for indicator in video_indicators) or 'w-gcb-app' in src:
                            result['other_video_url'] = src
                            result['platform'] = 'other'
                            print(f"✅ Found other video iframe: {src[:100]}...")
                            break
            
            # Check video elements
            if not result['platform'] and findings.get('video_elements'):
                for video in findings['video_elements']:
                    src = video.get('src') or (video.get('sources', [])[0] if video.get('sources') else None)
                    if src:
                        result['other_video_url'] = src
                        result['platform'] = 'direct'
                        print(f"✅ Found direct video: {src}")
                        break
        
        if not result['platform']:
            print("❌ No video content found on page")
        
        return result
    
    def _extract_youtube_id(self, url_or_id: str) -> Optional[str]:
        """Extract YouTube video ID from URL or return ID if already extracted"""
        # If it's already an ID
        if re.match(r'^[a-zA-Z0-9_-]{11}$', url_or_id):
            return url_or_id
        
        # Extract from URL
        patterns = [
            r'youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})',
            r'youtube\.com/embed/([a-zA-Z0-9_-]{11})',
            r'youtu\.be/([a-zA-Z0-9_-]{11})',
            r'youtube\.com/v/([a-zA-Z0-9_-]{11})'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url_or_id)
            if match:
                return match.group(1)
        
        return None
    
    def _extract_vimeo_id(self, url: str) -> Optional[str]:
        """Extract Vimeo video ID from URL"""
        patterns = [
            r'vimeo\.com/(\d+)',
            r'player\.vimeo\.com/video/(\d+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        
        return None
    
    def _validate_streamable_id(self, streamable_id: str) -> bool:
        """Validate Streamable ID using API"""
        try:
            response = requests.get(f'https://api.streamable.com/videos/{streamable_id}', timeout=5)
            if response.status_code == 200:
                return True
        except:
            pass
        return False


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Unified Video Extractor')
    parser.add_argument('url', help='URL to extract video information from')
    parser.add_argument('--chrome-port', type=int, default=9222, help='Chrome debugging port')
    
    args = parser.parse_args()
    
    print("🚀 Starting Unified Video Extractor")
    print("=" * 60)
    
    extractor = UnifiedVideoExtractor(chrome_port=args.chrome_port)
    result = extractor.extract_video_info(args.url)
    
    print("=" * 60)
    print("📊 EXTRACTION RESULTS:")
    print("=" * 60)
    
    if result['error']:
        print(f"❌ Error: {result['error']}")
    else:
        print(f"🎯 Platform: {result['platform'] or 'None'}")
        if result['streamable_id']:
            print(f"   Streamable ID: {result['streamable_id']}")
        if result['youtube_id']:
            print(f"   YouTube ID: {result['youtube_id']}")
        if result['vimeo_id']:
            print(f"   Vimeo ID: {result['vimeo_id']}")
        if result['wistia_id']:
            print(f"   Wistia ID: {result['wistia_id']}")
        if result['other_video_url']:
            print(f"   Other Video: {result['other_video_url'][:80]}...")
    
    return result


if __name__ == "__main__":
    main()