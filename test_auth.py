#!/usr/bin/env python3
"""
Quick authentication test for ObjectivePersonality.com
"""

import json
import requests
import websocket
import threading
import time
from pathlib import Path

def test_authentication():
    # Get Chrome tabs
    try:
        response = requests.get('http://localhost:9222/json/list', timeout=5)
        tabs = response.json()
    except:
        print("❌ Can't connect to Chrome debug port 9222")
        return False
    
    # Find or create OP tab
    op_tab = None
    for tab in tabs:
        if 'objectivepersonality.com' in tab.get('url', ''):
            op_tab = tab
            print(f"✅ Found existing OP tab: {tab.get('url', 'Unknown')}")
            break
    
    if not op_tab:
        print("❌ No ObjectivePersonality.com tab found")
        print("Please manually navigate to https://www.objectivepersonality.com/library in Chrome")
        return False
    
    # Load cookies
    cookie_path = Path("cookies.json")
    if not cookie_path.exists():
        print("❌ No cookies.json file found")
        return False
    
    with open(cookie_path) as f:
        cookies = json.load(f)
    print(f"✅ Loaded {len(cookies)} cookies:")
    for cookie in cookies:
        value_preview = cookie['value'][:20] + "..." if len(cookie['value']) > 20 else cookie['value']
        print(f"   - {cookie['name']}: {value_preview}")
    
    # Test WebSocket connection and authentication
    ws_url = op_tab.get('webSocketDebuggerUrl')
    result = {'done': False, 'authenticated': False, 'error': None}
    
    def on_message(ws, message):
        try:
            data = json.loads(message)
            
            if data.get('id') == 1:  # Page enable
                ws.send(json.dumps({'id': 2, 'method': 'Network.enable', 'params': {}}))
                
            elif data.get('id') == 2:  # Network enable
                # Set cookies
                for i, cookie in enumerate(cookies[:10]):
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
                
                # Navigate to library page to test auth
                time.sleep(2)
                ws.send(json.dumps({
                    'id': 200, 
                    'method': 'Page.navigate', 
                    'params': {'url': 'https://www.objectivepersonality.com/library'}
                }))
            
            elif data.get('id') == 200:  # Navigation complete
                print("📍 Navigated to library page, checking content...")
                time.sleep(5)  # Wait for page load
                
                # Check if we're authenticated
                ws.send(json.dumps({
                    'id': 300,
                    'method': 'Runtime.evaluate',
                    'params': {
                        'expression': '''
                        (() => {
                            const body = document.body.innerHTML.toLowerCase();
                            const hasSignIn = body.includes('sign in') || body.includes('login') || body.includes('authenticate');
                            const hasLibrary = body.includes('library') && body.includes('video');
                            const hasPaywall = body.includes('subscribe') || body.includes('membership');
                            
                            return {
                                title: document.title,
                                url: window.location.href,
                                bodyLength: document.body.innerHTML.length,
                                hasSignIn: hasSignIn,
                                hasLibrary: hasLibrary,
                                hasPaywall: hasPaywall,
                                authenticated: !hasSignIn && hasLibrary
                            };
                        })()
                        ''',
                        'returnByValue': True
                    }
                }))
            
            elif data.get('id') == 300:  # Auth check complete
                if 'result' in data and 'value' in data['result']:
                    auth_data = data['result']['value']
                    print(f"📄 Page title: {auth_data.get('title', 'Unknown')}")
                    print(f"🔗 URL: {auth_data.get('url', 'Unknown')}")
                    print(f"📏 Body length: {auth_data.get('bodyLength', 0):,} chars")
                    print(f"🔐 Has sign-in content: {auth_data.get('hasSignIn', False)}")
                    print(f"📚 Has library content: {auth_data.get('hasLibrary', False)}")
                    print(f"💳 Has paywall: {auth_data.get('hasPaywall', False)}")
                    
                    result['authenticated'] = auth_data.get('authenticated', False)
                    
                    if result['authenticated']:
                        print("✅ AUTHENTICATED - Ready to extract videos!")
                    else:
                        print("❌ NOT AUTHENTICATED - Please sign in manually")
                
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
        ws.send(json.dumps({'id': 1, 'method': 'Page.enable', 'params': {}}))
    
    # Connect
    ws = websocket.WebSocketApp(ws_url, on_open=on_open, on_message=on_message, on_error=on_error)
    ws_thread = threading.Thread(target=ws.run_forever)
    ws_thread.daemon = True
    ws_thread.start()
    
    # Wait for completion
    timeout = 30
    while not result['done'] and timeout > 0:
        time.sleep(0.5)
        timeout -= 0.5
    
    if result['error']:
        print(f"❌ Error: {result['error']}")
        return False
    
    return result['authenticated']

if __name__ == "__main__":
    print("🔐 TESTING OBJECTIVEPERSONALITY.COM AUTHENTICATION")
    print("=" * 60)
    
    authenticated = test_authentication()
    
    if authenticated:
        print("\n✅ Authentication test PASSED - Ready to run extraction!")
    else:
        print("\n❌ Authentication test FAILED")
        print("Please:")
        print("1. Open Chrome and navigate to https://www.objectivepersonality.com")
        print("2. Sign in with your credentials")
        print("3. Navigate to https://www.objectivepersonality.com/library")
        print("4. Run this test again")