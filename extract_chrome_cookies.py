#!/usr/bin/env python3
"""
Extract current authentication cookies from Chrome debug session
"""

import json
import requests
import websocket
import threading
import time

def extract_cookies_from_chrome():
    print("🔍 Extracting cookies from Chrome debug session...")
    
    # Get Chrome tabs
    try:
        response = requests.get('http://localhost:9222/json/list', timeout=5)
        tabs = response.json()
    except:
        print("❌ Can't connect to Chrome debug port 9222")
        return None
    
    # Find OP tab
    op_tab = None
    for tab in tabs:
        if 'objectivepersonality.com' in tab.get('url', ''):
            op_tab = tab
            print(f"✅ Found OP tab: {tab.get('url', 'Unknown')}")
            break
    
    if not op_tab:
        print("❌ No ObjectivePersonality.com tab found")
        return None
    
    # Extract cookies via WebSocket
    ws_url = op_tab.get('webSocketDebuggerUrl')
    result = {'done': False, 'cookies': None, 'error': None}
    
    def on_message(ws, message):
        try:
            data = json.loads(message)
            
            if data.get('id') == 1:  # Network enable
                print("✅ Network enabled, getting cookies...")
                ws.send(json.dumps({'id': 2, 'method': 'Network.getAllCookies', 'params': {}}))
                
            elif data.get('id') == 2:  # Cookies response
                if 'result' in data and 'cookies' in data['result']:
                    all_cookies = data['result']['cookies']
                    
                    # Filter for ObjectivePersonality cookies
                    op_cookies = []
                    for cookie in all_cookies:
                        if 'objectivepersonality.com' in cookie.get('domain', ''):
                            op_cookies.append({
                                'name': cookie['name'],
                                'value': cookie['value'],
                                'domain': cookie['domain'],
                                'path': cookie['path'],
                                'secure': cookie.get('secure', False),
                                'httpOnly': cookie.get('httpOnly', False)
                            })
                    
                    result['cookies'] = op_cookies
                    print(f"✅ Extracted {len(op_cookies)} ObjectivePersonality cookies")
                
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
        ws.send(json.dumps({'id': 1, 'method': 'Network.enable', 'params': {}}))
    
    # Connect
    ws = websocket.WebSocketApp(ws_url, on_open=on_open, on_message=on_message, on_error=on_error)
    ws_thread = threading.Thread(target=ws.run_forever)
    ws_thread.daemon = True
    ws_thread.start()
    
    # Wait for completion
    timeout = 15
    while not result['done'] and timeout > 0:
        time.sleep(0.5)
        timeout -= 0.5
    
    if result['error']:
        print(f"❌ Error: {result['error']}")
        return None
    
    return result['cookies']

def main():
    print("🍪 EXTRACTING CHROME AUTHENTICATION COOKIES")
    print("=" * 60)
    
    cookies = extract_cookies_from_chrome()
    
    if cookies:
        # Show what we found
        print(f"\n📋 Found {len(cookies)} cookies:")
        for cookie in cookies:
            value_preview = cookie['value'][:20] + "..." if len(cookie['value']) > 20 else cookie['value']
            print(f"   - {cookie['name']}: {value_preview}")
        
        # Save to cookies.json
        with open('cookies.json', 'w') as f:
            json.dump(cookies, f, indent=2)
        
        print(f"\n✅ Cookies saved to cookies.json")
        print(f"🔄 You can now run the unified batch processor with fresh authentication!")
        
        # Show key cookies
        key_cookies = ['XSRF-TOKEN', 'svSession', 'smSession', 'bSession', 'hs']
        print(f"\n🔑 Key authentication cookies found:")
        for key in key_cookies:
            found = any(c['name'] == key for c in cookies)
            status = "✅" if found else "❌"
            print(f"   {status} {key}")
    
    else:
        print("\n❌ Failed to extract cookies")
        print("Make sure:")
        print("1. Chrome is running with --remote-debugging-port=9222")
        print("2. You're signed in to ObjectivePersonality.com")
        print("3. There's an ObjectivePersonality tab open")

if __name__ == "__main__":
    main()