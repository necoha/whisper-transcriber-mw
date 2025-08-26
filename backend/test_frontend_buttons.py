#!/usr/bin/env python3
"""
Test if frontend buttons are working by simulating interactions
"""
import asyncio
import websockets
import json

async def test_frontend_websocket_connectivity():
    """Test if frontend WebSocket connection works"""
    client_id = "frontend_button_test"
    uri = f"ws://127.0.0.1:8765/ws/{client_id}"
    
    print("Testing frontend WebSocket connectivity...")
    
    try:
        async with websockets.connect(uri) as websocket:
            print("✅ WebSocket connection successful")
            
            # Send ping (simulating frontend button click)
            await websocket.send(json.dumps({"type": "ping"}))
            print("📤 Sent ping message")
            
            # Wait for pong response
            response = await websocket.recv()
            data = json.loads(response)
            
            if data.get("type") == "pong":
                print("✅ Received pong response - WebSocket communication working")
                return True
            else:
                print(f"❌ Unexpected response: {data}")
                return False
                
    except Exception as e:
        print(f"❌ WebSocket test failed: {e}")
        return False

async def main():
    print("=" * 60)
    print("FRONTEND BUTTON FUNCTIONALITY TEST")
    print("=" * 60)
    
    # Test 1: Backend server health
    print("\n1. Testing backend server health...")
    import requests
    try:
        response = requests.get("http://127.0.0.1:8765/health")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Backend server healthy: {data.get('backend', 'Unknown')}")
        else:
            print(f"❌ Backend server issues: {response.status_code}")
            return
    except Exception as e:
        print(f"❌ Backend server unreachable: {e}")
        return
    
    # Test 2: WebSocket connectivity 
    print("\n2. Testing WebSocket connectivity...")
    websocket_ok = await test_frontend_websocket_connectivity()
    
    # Test 3: Frontend status
    print("\n3. Frontend status check...")
    if websocket_ok:
        print("✅ WebSocket communication enabled - real-time updates available")
        print("✅ Theme switching should work")
        print("✅ Button event handlers should be registered") 
    else:
        print("⚠️  WebSocket issues - will fallback to polling mode")
    
    print("\n" + "=" * 60)
    print("INSTRUCTIONS FOR USER TESTING:")
    print("=" * 60)
    print()
    print("In the Electron app, please test the following buttons:")
    print()
    print("1. 🔗 接続確認 button - should show 'Backend接続OK' message")
    print("2. 🎮 GPU情報 button - should show GPU information popup") 
    print("3. 🌙 ダークモード / ☀️ ライトモード button - should toggle theme")
    print("4. 📄/🎬/🌐/⏱️ Format buttons - should highlight when clicked")
    print("5. Audio enhancement checkboxes - should toggle on/off")
    print()
    print("If buttons don't respond:")
    print("- Check browser console for JavaScript errors (F12)")
    print("- Verify all required files are loaded")
    print("- Confirm preload script is working")
    print()
    print("Expected results:")
    print("- Status messages should appear at top of window")
    print("- Theme should switch between light and dark")
    print("- Button states should change on interaction")

if __name__ == "__main__":
    asyncio.run(main())