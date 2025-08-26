# backend/streaming.py
import os
import tempfile
import librosa
import soundfile as sf
import numpy as np
from typing import List, Dict, Any, Generator, Tuple
import asyncio
from concurrent.futures import ThreadPoolExecutor
import json
import uuid
from pathlib import Path

class AudioChunker:
    """Audio chunking utility for long audio processing"""
    
    def __init__(self, chunk_duration=30, overlap_duration=3, sample_rate=16000):
        """
        Initialize audio chunker
        
        Args:
            chunk_duration: Duration of each chunk in seconds
            overlap_duration: Overlap between chunks in seconds
            sample_rate: Target sample rate
        """
        self.chunk_duration = chunk_duration
        self.overlap_duration = overlap_duration
        self.sample_rate = sample_rate
    
    def chunk_audio_file(self, file_path: str) -> Tuple[List[np.ndarray], float]:
        """
        Split audio file into overlapping chunks
        
        Returns:
            Tuple of (chunks, total_duration)
        """
        # Load audio
        audio, sr = librosa.load(file_path, sr=self.sample_rate)
        total_duration = len(audio) / sr
        
        chunks = []
        chunk_samples = int(self.chunk_duration * self.sample_rate)
        overlap_samples = int(self.overlap_duration * self.sample_rate)
        step_samples = chunk_samples - overlap_samples
        
        for start in range(0, len(audio), step_samples):
            end = min(start + chunk_samples, len(audio))
            chunk = audio[start:end]
            
            # Pad short chunks at the end
            if len(chunk) < chunk_samples:
                chunk = np.pad(chunk, (0, chunk_samples - len(chunk)), 'constant')
            
            chunks.append(chunk)
            
            # Stop if we've reached the end
            if end >= len(audio):
                break
        
        return chunks, total_duration
    
    def get_chunk_timestamps(self, total_duration: float) -> List[Tuple[float, float]]:
        """Get start and end timestamps for each chunk"""
        timestamps = []
        
        chunk_count = int(np.ceil((total_duration - self.overlap_duration) / (self.chunk_duration - self.overlap_duration)))
        
        for i in range(chunk_count):
            start_time = i * (self.chunk_duration - self.overlap_duration)
            end_time = min(start_time + self.chunk_duration, total_duration)
            timestamps.append((start_time, end_time))
        
        return timestamps

class StreamingProcessor:
    """Streaming audio processing with progress tracking"""
    
    def __init__(self, asr_engine, chunker: AudioChunker = None, websocket_manager=None):
        self.asr_engine = asr_engine
        self.chunker = chunker or AudioChunker()
        self.active_jobs = {}  # job_id -> job_info
        self.executor = ThreadPoolExecutor(max_workers=1)  # Sequential processing
        self.websocket_manager = websocket_manager  # WebSocket manager for real-time updates
    
    async def _send_websocket_update(self, job_id: str):
        """Send WebSocket update for job progress"""
        if self.websocket_manager and job_id in self.active_jobs:
            job_info = self.active_jobs[job_id]
            await self.websocket_manager.send_progress_update(job_id, {
                "status": job_info.get("status"),
                "progress": job_info.get("progress", 0),
                "current_chunk": job_info.get("current_chunk", 0),
                "total_chunks": job_info.get("total_chunks", 0),
                "full_text": job_info.get("full_text", "")
            })
    
    async def process_streaming(self, file_path: str, language: str = None, 
                              return_segments: bool = False, 
                              job_id: str = None,
                              enable_vad: bool = True,
                              enable_noise_reduction: bool = True,
                              vad_aggressiveness: int = 1,
                              noise_reduce_strength: float = 0.6) -> Dict[str, Any]:
        """
        Process audio file in streaming mode with audio enhancement
        
        Args:
            file_path: Path to audio file
            language: Language code
            return_segments: Whether to return segments
            job_id: Unique job identifier
            enable_vad: Enable voice activity detection
            enable_noise_reduction: Enable noise reduction
            vad_aggressiveness: VAD aggressiveness level (0-3)
            noise_reduce_strength: Noise reduction strength (0.0-1.0)
            
        Returns:
            Job information dict
        """
        if job_id is None:
            job_id = str(uuid.uuid4())
        
        # Initialize job
        job_info = {
            "id": job_id,
            "status": "processing",
            "progress": 0.0,
            "current_chunk": 0,
            "total_chunks": 0,
            "results": [],
            "full_text": "",
            "error": None,
            "timestamps": [],
            "enhancement_options": {
                "enable_vad": enable_vad,
                "enable_noise_reduction": enable_noise_reduction,
                "vad_aggressiveness": vad_aggressiveness,
                "noise_reduce_strength": noise_reduce_strength
            }
        }
        
        self.active_jobs[job_id] = job_info
        
        # Start processing in background
        asyncio.create_task(self._process_chunks_async(file_path, language, return_segments, job_id))
        
        return {"job_id": job_id, "status": "started"}
    
    async def _process_chunks_async(self, file_path: str, language: str, 
                                  return_segments: bool, job_id: str):
        """Async chunk processing"""
        job_info = self.active_jobs[job_id]
        
        try:
            # Split audio into chunks
            job_info["status"] = "chunking"
            await self._send_websocket_update(job_id)
            
            chunks, total_duration = self.chunker.chunk_audio_file(file_path)
            timestamps = self.chunker.get_chunk_timestamps(total_duration)
            
            job_info["total_chunks"] = len(chunks)
            job_info["timestamps"] = timestamps
            job_info["total_duration"] = total_duration
            
            # Process each chunk
            job_info["status"] = "transcribing"
            await self._send_websocket_update(job_id)
            all_results = []
            combined_text = ""
            
            for i, (chunk, (start_time, end_time)) in enumerate(zip(chunks, timestamps)):
                job_info["current_chunk"] = i + 1
                job_info["progress"] = (i + 1) / len(chunks) * 100
                
                # Save chunk to temporary file
                with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_file:
                    # Convert numpy array back to audio file
                    import soundfile as sf
                    sf.write(tmp_file.name, chunk, self.chunker.sample_rate)
                    chunk_path = tmp_file.name
                
                try:
                    # Get enhancement options from job info
                    enhancement_options = job_info.get("enhancement_options", {})
                    
                    # Process chunk with enhancement
                    result = await asyncio.get_event_loop().run_in_executor(
                        self.executor,
                        self._process_single_chunk,
                        chunk_path, language, return_segments, enhancement_options
                    )
                    
                    # Adjust timestamps for segments
                    if return_segments and "segments" in result:
                        adjusted_segments = []
                        for seg in result["segments"]:
                            adjusted_seg = seg.copy()
                            adjusted_seg["start"] = seg["start"] + start_time
                            adjusted_seg["end"] = seg["end"] + start_time
                            adjusted_segments.append(adjusted_seg)
                        result["segments"] = adjusted_segments
                    
                    # Add chunk info
                    result["chunk_info"] = {
                        "chunk_id": i,
                        "start_time": start_time,
                        "end_time": end_time,
                        "chunk_duration": end_time - start_time
                    }
                    
                    all_results.append(result)
                    combined_text += result.get("text", "") + " "
                    
                    # Update job with partial results
                    job_info["results"] = all_results
                    job_info["full_text"] = combined_text.strip()
                    
                    # Send real-time progress update via WebSocket
                    await self._send_websocket_update(job_id)
                    
                    # Clean up temporary file
                    os.unlink(chunk_path)
                    
                except Exception as e:
                    print(f"Error processing chunk {i}: {e}")
                    job_info["error"] = f"Chunk {i} failed: {str(e)}"
                    continue
            
            # Combine all segments if requested
            if return_segments:
                all_segments = []
                for result in all_results:
                    if "segments" in result:
                        all_segments.extend(result["segments"])
                
                job_info["combined_segments"] = all_segments
            
            job_info["status"] = "completed"
            job_info["progress"] = 100.0
            await self._send_websocket_update(job_id)
            
        except Exception as e:
            job_info["status"] = "failed"
            job_info["error"] = str(e)
            await self._send_websocket_update(job_id)
            print(f"Streaming processing failed: {e}")
    
    def _process_single_chunk(self, chunk_path: str, language: str, return_segments: bool, 
                             enhancement_options: Dict[str, Any] = None) -> Dict[str, Any]:
        """Process a single audio chunk with optional enhancement (runs in thread)"""
        
        processed_path = chunk_path
        
        # Apply audio enhancement if requested
        if enhancement_options:
            enable_vad = enhancement_options.get("enable_vad", False)
            enable_noise_reduction = enhancement_options.get("enable_noise_reduction", False)
            
            if enable_vad or enable_noise_reduction:
                try:
                    from audio_enhancement import enhance_audio_file
                    processed_path = enhance_audio_file(
                        input_path=chunk_path,
                        enable_vad=enable_vad,
                        enable_noise_reduction=enable_noise_reduction,
                        vad_aggressiveness=enhancement_options.get("vad_aggressiveness", 1),
                        noise_reduce_strength=enhancement_options.get("noise_reduce_strength", 0.6)
                    )
                except Exception as e:
                    print(f"Chunk enhancement failed: {e}, using original chunk")
                    processed_path = chunk_path
        
        try:
            # Transcribe the (possibly enhanced) chunk
            result = self.asr_engine.transcribe(processed_path, language, return_segments)
            
            # Clean up enhanced chunk if different from original
            if processed_path != chunk_path:
                try:
                    os.unlink(processed_path)
                except:
                    pass
                    
            return result
            
        except Exception as e:
            # Clean up enhanced chunk on error
            if processed_path != chunk_path:
                try:
                    os.unlink(processed_path)
                except:
                    pass
            raise e
    
    def get_job_status(self, job_id: str) -> Dict[str, Any]:
        """Get current job status"""
        if job_id not in self.active_jobs:
            return {"error": "Job not found"}
        
        return self.active_jobs[job_id].copy()
    
    def cleanup_job(self, job_id: str) -> bool:
        """Clean up completed job"""
        if job_id in self.active_jobs:
            del self.active_jobs[job_id]
            return True
        return False
    
    def list_active_jobs(self) -> List[str]:
        """List all active job IDs"""
        return list(self.active_jobs.keys())