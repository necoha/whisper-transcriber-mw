#!/usr/bin/env python3
"""
WebSocket connection test script
"""
import asyncio
import websockets
import json

async def test_websocket():
    uri = "ws://127.0.0.1:8765/ws/test_client"
    
    try:
        print(f"Connecting to {uri}...")
        async with websockets.connect(uri) as websocket:
            print("Connected successfully!")
            
            # Send ping message
            ping_message = {"type": "ping"}
            await websocket.send(json.dumps(ping_message))
            print("Sent ping message")
            
            # Wait for response
            response = await websocket.recv()
            data = json.loads(response)
            print(f"Received response: {data}")
            
            if data.get("type") == "pong":
                print("✅ WebSocket connection test PASSED")
            else:
                print("❌ Unexpected response")
                
    except Exception as e:
        print(f"❌ WebSocket connection test FAILED: {e}")

if __name__ == "__main__":
    asyncio.run(test_websocket())