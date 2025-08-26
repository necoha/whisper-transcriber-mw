#!/usr/bin/env python3
"""
Test transcription functionality
"""
import requests
import tempfile
import numpy as np
import soundfile as sf
import json

def generate_speech_like_audio():
    """Generate a simple speech-like audio file"""
    sample_rate = 16000
    duration = 2  # 2 seconds
    samples = duration * sample_rate
    
    # Create a more speech-like pattern with multiple frequencies
    t = np.linspace(0, duration, samples)
    
    # Mix of frequencies that might resemble speech
    audio = 0.3 * np.sin(2 * np.pi * 200 * t)   # Base frequency
    audio += 0.2 * np.sin(2 * np.pi * 400 * t)  # Harmonic
    audio += 0.1 * np.sin(2 * np.pi * 800 * t)  # Higher harmonic
    
    # Add some modulation to make it more speech-like
    modulation = 0.5 + 0.5 * np.sin(2 * np.pi * 5 * t)
    audio = audio * modulation
    
    # Add some noise
    audio += np.random.normal(0, 0.02, samples)
    
    # Save to temporary file
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
        sf.write(tmp.name, audio, sample_rate)
        return tmp.name

def test_transcription_api():
    """Test transcription API endpoints"""
    print("Generating test audio...")
    test_file = generate_speech_like_audio()
    
    try:
        print(f"Test audio file: {test_file}")
        
        # Test basic transcription
        print("\nTesting basic transcription...")
        with open(test_file, 'rb') as f:
            files = {'file': ('test.wav', f, 'audio/wav')}
            data = {
                'language': 'ja',
                'format': 'text',
                'enable_vad': True,
                'enable_noise_reduction': True,
                'vad_aggressiveness': 1,
                'noise_reduce_strength': 0.6
            }
            
            response = requests.post('http://127.0.0.1:8765/transcribe', files=files, data=data)
            
        print(f"Response status: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            print(f"Transcription result: {result}")
            print("✅ Basic transcription test PASSED")
        else:
            print(f"❌ Basic transcription test FAILED: {response.text}")
            return
            
        # Test formats endpoint
        print("\nTesting formats endpoint...")
        response = requests.get('http://127.0.0.1:8765/formats')
        if response.status_code == 200:
            formats = response.json()
            print(f"Available formats: {formats}")
            print("✅ Formats endpoint test PASSED")
        else:
            print(f"❌ Formats endpoint test FAILED: {response.text}")
            
        # Test models endpoint
        print("\nTesting models endpoint...")
        response = requests.get('http://127.0.0.1:8765/models')
        if response.status_code == 200:
            models = response.json()
            print(f"Available models: {models}")
            print("✅ Models endpoint test PASSED")
        else:
            print(f"❌ Models endpoint test FAILED: {response.text}")
            
    except Exception as e:
        print(f"❌ Transcription API test FAILED: {e}")
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
    test_transcription_api()