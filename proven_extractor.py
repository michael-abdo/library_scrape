#!/usr/bin/env python3
"""
Proven Streamable ID Extractor
Exact replication of the WebSocket method that successfully found yiv10d
"""

import json
import requests
import websocket
import threading
import time
import re
from pathlib import Path
from typing import List, Optional

class ProvenExtractor:
    def __init__(self, chrome_port: int = 9222):
        """Initialize extractor with Chrome WebSocket connection"""
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
    
    def extract_streamable_id(self, url: str) -> Optional[str]:
        """Extract Streamable ID using the exact proven method"""
        print(f"🎬 Processing: {url}")
        print(f"🔗 Connecting to Chrome on port {self.chrome_port}")
        
        try:
            # First, look for existing objectivepersonality.com tabs
            response = requests.get(f'http://localhost:{self.chrome_port}/json/list', timeout=5)
            tabs = response.json()
            
            # Find existing objectivepersonality.com tab
            op_tab = None
            for tab in tabs:
                if 'objectivepersonality.com' in tab.get('url', ''):
                    op_tab = tab
                    print(f"✅ Found existing OP tab: {tab.get('id')} - {tab.get('title', '')[:50]}")
                    break
            
            if op_tab:
                tab = op_tab
                ws_url = tab.get('webSocketDebuggerUrl')
            else:
                # No OP tab found - ONLY use OP tabs as requested
                print("❌ No ObjectivePersonality.com tabs available")
                print("💡 Please open https://www.objectivepersonality.com in Chrome and try again")
                return None
            
            if not ws_url:
                print("❌ No WebSocket URL available")
                return None
            
            print(f"✅ Using WebSocket: {ws_url}")
            
            # Result container
            result = {'html': None, 'done': False, 'error': None}
            
            def on_message(ws, message):
                try:
                    data = json.loads(message)
                    
                    # Handle enable responses
                    if data.get('id') == 1:  # Page enable
                        print("✅ Page domain enabled")
                        # Enable Network domain for cookies
                        command = {
                            'id': 2,
                            'method': 'Network.enable',
                            'params': {}
                        }
                        ws.send(json.dumps(command))
                        
                    elif data.get('id') == 2:  # Network enable
                        print("✅ Network domain enabled, setting cookies...")
                        # Set authentication cookies
                        for i, cookie in enumerate(self.cookies[:10]):  # Limit to first 10 for speed
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
                        
                        # Wait then navigate
                        time.sleep(2)
                        navigate_command = {
                            'id': 200,
                            'method': 'Page.navigate',
                            'params': {'url': url}
                        }
                        ws.send(json.dumps(navigate_command))
                    
                    # Handle navigation response
                    elif data.get('id') == 200:
                        print("📍 Page navigated with cookies, waiting longer for JavaScript...")
                        time.sleep(15)  # Wait much longer for authenticated content to load
                        
                        # Extract DOM
                        command = {
                            'id': 300,
                            'method': 'Runtime.evaluate',
                            'params': {
                                'expression': 'document.documentElement.outerHTML',
                                'returnByValue': True
                            }
                        }
                        ws.send(json.dumps(command))
                    
                    # Handle DOM extraction response
                    elif data.get('id') == 300 and 'result' in data:
                        result_data = data['result']
                        
                        if 'result' in result_data and 'value' in result_data['result']:
                            html = result_data['result']['value']
                            result['html'] = html
                            print(f"✅ Got authenticated DOM: {len(html):,} bytes")
                        
                        result['done'] = True
                        ws.close()
                        
                except Exception as e:
                    result['error'] = str(e)
                    result['done'] = True
                    ws.close()
            
            def on_error(ws, error):
                result['error'] = str(error)
                result['done'] = True
            
            def on_open(ws):
                print("🔗 WebSocket connected")
                # Enable Page domain first
                command = {
                    'id': 1,
                    'method': 'Page.enable',
                    'params': {}
                }
                ws.send(json.dumps(command))
            
            # Connect and execute - same WebSocket setup
            ws = websocket.WebSocketApp(
                ws_url, 
                on_open=on_open, 
                on_message=on_message,
                on_error=on_error
            )
            
            ws_thread = threading.Thread(target=ws.run_forever)
            ws_thread.daemon = True
            ws_thread.start()
            
            # Wait with extended timeout for cookie authentication and slower loading
            timeout = 45
            while not result['done'] and timeout > 0:
                time.sleep(0.5)
                timeout -= 0.5
            
            if result['error']:
                print(f"❌ WebSocket error: {result['error']}")
                return None
            
            if not result['html']:
                print("❌ No HTML retrieved")
                return None
            
            # Extract Streamable IDs using exact same patterns that found yiv10d
            streamable_id = self._extract_ids_from_html(result['html'])
            
            # Don't clean up OP tabs - keep them for reuse
            print("✅ Reused existing OP tab (no cleanup needed)")
            
            return streamable_id
            
        except Exception as e:
            print(f"❌ Extraction error: {e}")
            # Clean up tab on error too, but only if we created it
            try:
                if 'tab' in locals() and 'op_tab' in locals() and not op_tab:
                    requests.get(f'http://localhost:{self.chrome_port}/json/close/{tab.get("id")}', timeout=2)
            except:
                pass
            return None
    
    def _extract_ids_from_html(self, html: str) -> Optional[str]:
        """Extract Streamable IDs using exact patterns that found yiv10d"""
        print("🔍 Searching for Streamable IDs...")
        
        # Exact same regex patterns that successfully found yiv10d
        patterns = [
            r'streamable\.com/([a-z0-9]{6,})',
            r'cdn-cf-east\.streamable\.com/image/([a-z0-9]+)',
            r'api\.streamable\.com/videos/([a-z0-9]+)'
        ]
        
        found_ids = set()
        
        for pattern in patterns:
            matches = re.findall(pattern, html, re.IGNORECASE)
            found_ids.update(matches)
            if matches:
                print(f"✅ Pattern '{pattern}' found: {matches}")
        
        # Filter to IDs with 6+ characters (same filtering as successful attempt)
        valid_ids = [id for id in found_ids if len(id) >= 6]
        
        print(f"🎯 Found {len(valid_ids)} potential Streamable IDs: {valid_ids}")
        
        # Validate each ID using exact same API validation
        for streamable_id in valid_ids:
            if self._validate_streamable_id(streamable_id):
                return streamable_id
        
        return None
    
    def _validate_streamable_id(self, streamable_id: str) -> bool:
        """Validate Streamable ID using exact same API approach"""
        try:
            print(f"🧪 Testing ID: {streamable_id}")
            response = requests.get(f'https://api.streamable.com/videos/{streamable_id}', timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                title = data.get('title', 'Unknown')
                print(f"✅ {streamable_id} - Valid! Title: {title}")
                return True
            else:
                print(f"❌ {streamable_id} - Invalid (HTTP {response.status_code})")
                return False
                
        except Exception as e:
            print(f"❌ {streamable_id} - API error: {e}")
            return False


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Proven Streamable ID Extractor')
    parser.add_argument('url', help='URL to extract Streamable ID from')
    parser.add_argument('--chrome-port', type=int, default=9222, help='Chrome debugging port')
    
    args = parser.parse_args()
    
    print("🚀 Starting Proven Streamable ID Extractor")
    print(f"📋 URL: {args.url}")
    print(f"🌐 Chrome Port: {args.chrome_port}")
    print("=" * 60)
    
    extractor = ProvenExtractor(chrome_port=args.chrome_port)
    streamable_id = extractor.extract_streamable_id(args.url)
    
    print("=" * 60)
    if streamable_id:
        print(f"🎯 SUCCESS: Found valid Streamable ID: {streamable_id}")
    else:
        print("❌ FAILED: No valid Streamable ID found")


if __name__ == "__main__":
    main()