#!/usr/bin/env python3
"""
Test streaming transcription with WebSocket updates
"""
import asyncio
import websockets
import requests
import json
import tempfile
import numpy as np
import soundfile as sf
import time

def generate_longer_audio():
    """Generate a longer test audio file for streaming test"""
    sample_rate = 16000
    duration = 10  # 10 seconds to test chunking
    samples = duration * sample_rate
    
    t = np.linspace(0, duration, samples)
    
    # Create audio with different patterns in different sections
    audio = np.zeros(samples)
    
    # Different frequency patterns for different time periods
    for i in range(5):  # 5 different 2-second segments
        start_idx = i * sample_rate * 2
        end_idx = (i + 1) * sample_rate * 2
        segment_t = t[start_idx:end_idx]
        
        # Different frequency for each segment
        freq = 200 + i * 100
        segment_audio = 0.3 * np.sin(2 * np.pi * freq * segment_t)
        segment_audio += 0.1 * np.sin(2 * np.pi * freq * 2 * segment_t)
        
        # Add modulation
        mod_freq = 2 + i
        modulation = 0.5 + 0.5 * np.sin(2 * np.pi * mod_freq * segment_t)
        segment_audio = segment_audio * modulation
        
        audio[start_idx:end_idx] = segment_audio
    
    # Add some noise
    audio += np.random.normal(0, 0.02, samples)
    
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
        sf.write(tmp.name, audio, sample_rate)
        return tmp.name

async def test_streaming_with_websocket():
    """Test streaming transcription with WebSocket progress updates"""
    print("Generating longer test audio...")
    test_file = generate_longer_audio()
    
    try:
        print(f"Test audio file: {test_file}")
        
        # Connect to WebSocket first
        client_id = "test_streaming_client"
        uri = f"ws://127.0.0.1:8765/ws/{client_id}"
        
        print(f"\nConnecting to WebSocket: {uri}")
        
        messages_received = []
        job_id = None
        
        async with websockets.connect(uri) as websocket:
            print("WebSocket connected!")
            
            # Start streaming transcription
            print("\nStarting streaming transcription...")
            with open(test_file, 'rb') as f:
                files = {'file': ('test_long.wav', f, 'audio/wav')}
                data = {
                    'language': 'ja',
                    'format': 'text',
                    'chunk_duration': 3,  # 3 second chunks
                    'overlap_duration': 1,  # 1 second overlap
                    'enable_vad': True,
                    'enable_noise_reduction': True,
                    'vad_aggressiveness': 1,
                    'noise_reduce_strength': 0.6
                }
                
                response = requests.post(
                    'http://127.0.0.1:8765/transcribe/streaming', 
                    files=files, 
                    data=data
                )
            
            if response.status_code != 200:
                print(f"❌ Failed to start streaming: {response.text}")
                return
                
            result = response.json()
            job_id = result.get('job_id')
            print(f"Streaming job started: {job_id}")
            
            # Listen for WebSocket messages
            print("\nListening for WebSocket progress updates...")
            start_time = time.time()
            timeout = 60  # 60 seconds timeout
            
            while time.time() - start_time < timeout:
                try:
                    # Wait for WebSocket message with timeout
                    message = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                    data = json.loads(message)
                    messages_received.append(data)
                    
                    print(f"WebSocket message: {data}")
                    
                    if data.get('type') == 'progress_update' and data.get('job_id') == job_id:
                        progress_data = data.get('data', {})
                        status = progress_data.get('status')
                        progress = progress_data.get('progress', 0)
                        
                        print(f"Progress: {progress:.1f}% - Status: {status}")
                        
                        if status == 'completed':
                            print("✅ Streaming completed!")
                            break
                        elif status == 'failed':
                            print(f"❌ Streaming failed: {progress_data.get('error')}")
                            break
                            
                except asyncio.TimeoutError:
                    # No message received, continue listening
                    continue
                except Exception as e:
                    print(f"Error receiving WebSocket message: {e}")
                    break
            
            print(f"\nReceived {len(messages_received)} WebSocket messages")
            
            # Get final result
            if job_id:
                print("\nFetching final result...")
                final_response = requests.get(
                    f'http://127.0.0.1:8765/transcribe/streaming/{job_id}/result?format=text'
                )
                
                if final_response.status_code == 200:
                    final_result = final_response.json()
                    print(f"Final transcription: {final_result}")
                    print("✅ Streaming with WebSocket test PASSED")
                else:
                    print(f"❌ Failed to get final result: {final_response.text}")
            
    except Exception as e:
        print(f"❌ Streaming WebSocket test FAILED: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Cleanup
        import os
        try:
            os.unlink(test_file)
        except:
            pass

if __name__ == "__main__":
    asyncio.run(test_streaming_with_websocket())