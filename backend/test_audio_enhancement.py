#!/usr/bin/env python3
"""
Audio enhancement functionality test
"""
import numpy as np
import soundfile as sf
import tempfile
import os
from audio_enhancement import AudioEnhancer, enhance_audio_file

def generate_test_audio():
    """Generate a simple test audio file"""
    # Generate 3 seconds of test audio: 1 second of noise, 1 second of tone, 1 second of noise
    sample_rate = 16000
    duration = 3
    samples = duration * sample_rate
    
    # Create audio with noise at beginning and end, tone in middle
    audio = np.random.normal(0, 0.05, samples)  # Background noise
    
    # Add a tone in the middle second (1000 Hz)
    middle_start = sample_rate
    middle_end = sample_rate * 2
    t = np.linspace(0, 1, sample_rate)
    tone = 0.5 * np.sin(2 * np.pi * 1000 * t)  # 1000 Hz sine wave
    audio[middle_start:middle_end] = tone + np.random.normal(0, 0.02, sample_rate)
    
    # Save to temporary file
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
        sf.write(tmp.name, audio, sample_rate)
        return tmp.name

def test_audio_enhancement():
    """Test audio enhancement functionality"""
    print("Generating test audio...")
    test_file = generate_test_audio()
    
    try:
        print(f"Test audio file: {test_file}")
        
        # Test AudioEnhancer class
        print("\nTesting AudioEnhancer class...")
        enhancer = AudioEnhancer(vad_aggressiveness=1, noise_reduce_strength=0.6)
        
        # Get original audio stats
        stats = enhancer.get_audio_stats(test_file)
        print(f"Original audio stats: {stats}")
        
        # Test VAD only
        print("\nTesting VAD only...")
        vad_only_file = enhancer.enhance_audio(
            test_file, 
            enable_vad=True, 
            enable_noise_reduction=False
        )
        print(f"VAD processed file: {vad_only_file}")
        
        vad_stats = enhancer.get_audio_stats(vad_only_file)
        print(f"VAD processed stats: {vad_stats}")
        
        # Test noise reduction only
        print("\nTesting noise reduction only...")
        nr_only_file = enhancer.enhance_audio(
            test_file,
            enable_vad=False,
            enable_noise_reduction=True
        )
        print(f"Noise reduction processed file: {nr_only_file}")
        
        nr_stats = enhancer.get_audio_stats(nr_only_file)
        print(f"Noise reduction processed stats: {nr_stats}")
        
        # Test both VAD and noise reduction
        print("\nTesting VAD + Noise Reduction...")
        enhanced_file = enhance_audio_file(
            test_file,
            enable_vad=True,
            enable_noise_reduction=True,
            vad_aggressiveness=2,
            noise_reduce_strength=0.7
        )
        print(f"Full enhancement processed file: {enhanced_file}")
        
        enhanced_stats = enhancer.get_audio_stats(enhanced_file)
        print(f"Full enhancement processed stats: {enhanced_stats}")
        
        print("\n✅ Audio enhancement test PASSED")
        
        # Cleanup
        for f in [vad_only_file, nr_only_file, enhanced_file]:
            try:
                os.unlink(f)
            except:
                pass
                
    except Exception as e:
        print(f"❌ Audio enhancement test FAILED: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Cleanup test file
        try:
            os.unlink(test_file)
        except:
            pass

if __name__ == "__main__":
    test_audio_enhancement()