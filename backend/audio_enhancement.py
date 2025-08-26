# backend/audio_enhancement.py
import os
import tempfile
import numpy as np
import librosa
import soundfile as sf
import webrtcvad
import noisereduce as nr
from scipy import signal
from typing import Tuple, Optional, List
import logging

logger = logging.getLogger(__name__)

class AudioEnhancer:
    """Audio preprocessing with VAD and noise reduction"""
    
    def __init__(self, 
                 vad_aggressiveness: int = 1,
                 frame_duration: float = 0.03,
                 padding_duration: float = 0.3,
                 noise_reduce_strength: float = 0.6):
        """
        Initialize AudioEnhancer
        
        Args:
            vad_aggressiveness: WebRTC VAD aggressiveness (0-3, higher = more aggressive)
            frame_duration: Frame duration for VAD in seconds (0.01, 0.02, or 0.03)
            padding_duration: Padding around speech segments in seconds
            noise_reduce_strength: Noise reduction strength (0.0-1.0)
        """
        self.vad_aggressiveness = vad_aggressiveness
        self.frame_duration = frame_duration
        self.padding_duration = padding_duration
        self.noise_reduce_strength = noise_reduce_strength
        
        # Initialize WebRTC VAD
        self.vad = webrtcvad.Vad()
        self.vad.set_mode(vad_aggressiveness)
        
    def enhance_audio(self, 
                     input_path: str, 
                     enable_vad: bool = True,
                     enable_noise_reduction: bool = True) -> str:
        """
        Enhance audio with VAD and noise reduction
        
        Args:
            input_path: Path to input audio file
            enable_vad: Enable voice activity detection
            enable_noise_reduction: Enable noise reduction
            
        Returns:
            Path to enhanced audio file
        """
        logger.info(f"Enhancing audio: {input_path}")
        
        # Load audio
        audio, sr = librosa.load(input_path, sr=None)
        original_sr = sr
        
        # Convert to 16kHz for VAD processing
        if sr != 16000:
            audio_16k = librosa.resample(audio, orig_sr=sr, target_sr=16000)
            sr_vad = 16000
        else:
            audio_16k = audio
            sr_vad = sr
            
        enhanced_audio = audio
        processing_sr = original_sr
        
        # Apply noise reduction first
        if enable_noise_reduction:
            logger.info("Applying noise reduction...")
            enhanced_audio = self._apply_noise_reduction(enhanced_audio, processing_sr)
        
        # Apply VAD filtering
        if enable_vad:
            logger.info("Applying voice activity detection...")
            speech_segments = self._detect_speech_segments(audio_16k, sr_vad)
            enhanced_audio = self._filter_by_vad(enhanced_audio, speech_segments, 
                                               processing_sr, sr_vad)
        
        # Save enhanced audio
        suffix = os.path.splitext(input_path)[1] or '.wav'
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            output_path = tmp.name
        
        # Normalize audio to prevent clipping
        if len(enhanced_audio) > 0:
            enhanced_audio = self._normalize_audio(enhanced_audio)
            sf.write(output_path, enhanced_audio, processing_sr)
            logger.info(f"Enhanced audio saved: {output_path}")
        else:
            # Fallback: copy original if no audio detected
            logger.warning("No audio detected after enhancement, using original")
            sf.write(output_path, audio, original_sr)
            
        return output_path
        
    def _apply_noise_reduction(self, audio: np.ndarray, sr: int) -> np.ndarray:
        """Apply noise reduction to audio"""
        try:
            # Use noisereduce library for spectral gating
            reduced_noise = nr.reduce_noise(
                y=audio,
                sr=sr,
                prop_decrease=self.noise_reduce_strength,
                stationary=False  # Non-stationary noise reduction
            )
            return reduced_noise
        except Exception as e:
            logger.warning(f"Noise reduction failed: {e}, using original audio")
            return audio
    
    def _detect_speech_segments(self, audio: np.ndarray, sr: int) -> List[Tuple[float, float]]:
        """Detect speech segments using WebRTC VAD"""
        if sr != 16000:
            raise ValueError("VAD requires 16kHz sample rate")
            
        frame_samples = int(self.frame_duration * sr)
        
        # Ensure audio is int16
        audio_int16 = (audio * 32768).astype(np.int16)
        
        speech_segments = []
        current_segment_start = None
        
        # Process audio in frames
        for i in range(0, len(audio_int16) - frame_samples + 1, frame_samples):
            frame = audio_int16[i:i + frame_samples]
            
            # WebRTC VAD requires specific frame sizes
            frame_bytes = frame.tobytes()
            
            try:
                is_speech = self.vad.is_speech(frame_bytes, sr)
                
                frame_time = i / sr
                
                if is_speech:
                    if current_segment_start is None:
                        current_segment_start = frame_time
                else:
                    if current_segment_start is not None:
                        # End of speech segment
                        segment_end = frame_time
                        speech_segments.append((current_segment_start, segment_end))
                        current_segment_start = None
                        
            except Exception as e:
                logger.warning(f"VAD processing failed for frame at {frame_time:.2f}s: {e}")
                continue
        
        # Handle case where audio ends during speech
        if current_segment_start is not None:
            speech_segments.append((current_segment_start, len(audio_int16) / sr))
            
        # Apply padding and merge close segments
        speech_segments = self._apply_padding_and_merge(speech_segments, len(audio_int16) / sr)
        
        logger.info(f"Detected {len(speech_segments)} speech segments")
        return speech_segments
    
    def _apply_padding_and_merge(self, 
                                segments: List[Tuple[float, float]], 
                                total_duration: float) -> List[Tuple[float, float]]:
        """Apply padding to segments and merge overlapping ones"""
        if not segments:
            return segments
            
        padded_segments = []
        
        for start, end in segments:
            # Apply padding
            padded_start = max(0, start - self.padding_duration)
            padded_end = min(total_duration, end + self.padding_duration)
            padded_segments.append((padded_start, padded_end))
        
        # Sort by start time
        padded_segments.sort()
        
        # Merge overlapping segments
        merged_segments = []
        current_start, current_end = padded_segments[0]
        
        for start, end in padded_segments[1:]:
            if start <= current_end:  # Overlapping
                current_end = max(current_end, end)
            else:
                merged_segments.append((current_start, current_end))
                current_start, current_end = start, end
                
        merged_segments.append((current_start, current_end))
        
        return merged_segments
    
    def _filter_by_vad(self, 
                      audio: np.ndarray, 
                      speech_segments: List[Tuple[float, float]], 
                      audio_sr: int,
                      vad_sr: int) -> np.ndarray:
        """Filter audio to keep only speech segments"""
        if not speech_segments:
            logger.warning("No speech segments detected")
            return np.array([])  # Return empty array if no speech
            
        # Convert segment times to match audio sample rate
        sr_ratio = audio_sr / vad_sr
        
        filtered_segments = []
        
        for start_time, end_time in speech_segments:
            # Convert times to sample indices for the original audio
            start_sample = int(start_time * audio_sr * sr_ratio)
            end_sample = int(end_time * audio_sr * sr_ratio)
            
            # Ensure indices are within bounds
            start_sample = max(0, start_sample)
            end_sample = min(len(audio), end_sample)
            
            if start_sample < end_sample:
                segment_audio = audio[start_sample:end_sample]
                filtered_segments.append(segment_audio)
        
        if filtered_segments:
            # Concatenate all speech segments
            return np.concatenate(filtered_segments)
        else:
            logger.warning("No valid speech segments found")
            return audio  # Return original if filtering failed
    
    def _normalize_audio(self, audio: np.ndarray) -> np.ndarray:
        """Normalize audio to prevent clipping"""
        if len(audio) == 0:
            return audio
            
        max_val = np.abs(audio).max()
        if max_val > 0:
            # Normalize to 95% of max range to prevent clipping
            return audio * (0.95 / max_val)
        return audio
    
    def get_audio_stats(self, audio_path: str) -> dict:
        """Get audio file statistics"""
        try:
            audio, sr = librosa.load(audio_path, sr=None)
            
            return {
                "duration": len(audio) / sr,
                "sample_rate": int(sr),
                "channels": 1,  # librosa loads as mono by default
                "samples": len(audio),
                "rms_energy": float(np.sqrt(np.mean(audio**2))),
                "max_amplitude": float(np.abs(audio).max())
            }
        except Exception as e:
            logger.error(f"Failed to analyze audio: {e}")
            return {"error": str(e)}


# Default enhancer instance
default_enhancer = AudioEnhancer()


def enhance_audio_file(input_path: str,
                      enable_vad: bool = True,
                      enable_noise_reduction: bool = True,
                      vad_aggressiveness: int = 1,
                      noise_reduce_strength: float = 0.6) -> str:
    """
    Convenience function to enhance audio with custom parameters
    
    Args:
        input_path: Path to input audio file
        enable_vad: Enable voice activity detection
        enable_noise_reduction: Enable noise reduction
        vad_aggressiveness: WebRTC VAD aggressiveness (0-3)
        noise_reduce_strength: Noise reduction strength (0.0-1.0)
        
    Returns:
        Path to enhanced audio file
    """
    enhancer = AudioEnhancer(
        vad_aggressiveness=vad_aggressiveness,
        noise_reduce_strength=noise_reduce_strength
    )
    
    return enhancer.enhance_audio(
        input_path=input_path,
        enable_vad=enable_vad,
        enable_noise_reduction=enable_noise_reduction
    )