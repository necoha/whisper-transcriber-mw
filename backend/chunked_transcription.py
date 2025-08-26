#!/usr/bin/env python3
"""
Chunked transcription with real progress tracking
"""
import librosa
import numpy as np
import asyncio
from typing import Optional

async def transcribe_with_progress(
    asr_engine, 
    audio_path: str, 
    language: Optional[str],
    manager,
    job_id: str,
    chunk_size: int = 30  # seconds per chunk
):
    """
    Transcribe audio in chunks with real progress updates
    """
    # Load audio file
    await manager.broadcast({
        "type": "transcribe_progress",
        "job_id": job_id,
        "status": "loading_audio",
        "progress": 5,
        "message": "音声ファイルを読み込み中..."
    })
    
    try:
        # Load full audio
        audio, sr = librosa.load(audio_path, sr=None)
        duration = len(audio) / sr
        
        await manager.broadcast({
            "type": "transcribe_progress", 
            "job_id": job_id,
            "status": "preparing",
            "progress": 10,
            "message": f"音声時間: {duration:.1f}秒 - チャンク分割中..."
        })
        
        # Calculate chunks
        chunk_samples = int(chunk_size * sr)
        total_chunks = int(np.ceil(len(audio) / chunk_samples))
        
        if total_chunks == 1:
            # Short audio - process normally
            await manager.broadcast({
                "type": "transcribe_progress",
                "job_id": job_id, 
                "status": "transcribing",
                "progress": 15,
                "message": "短い音声のため一括処理中..."
            })
            
            result = asr_engine.transcribe(audio_path, language, return_segments=True)
            
            await manager.broadcast({
                "type": "transcribe_progress",
                "job_id": job_id,
                "status": "completed", 
                "progress": 100,
                "message": "文字起こし完了！"
            })
            
            return result
        
        # Process in chunks
        full_text = ""
        all_segments = []
        
        for chunk_idx in range(total_chunks):
            start_sample = chunk_idx * chunk_samples
            end_sample = min((chunk_idx + 1) * chunk_samples, len(audio))
            
            # Progress calculation
            base_progress = 15 + (chunk_idx / total_chunks) * 70  # 15% to 85%
            
            await manager.broadcast({
                "type": "transcribe_progress",
                "job_id": job_id,
                "status": "transcribing",
                "progress": int(base_progress),
                "message": f"チャンク {chunk_idx + 1}/{total_chunks} を処理中..."
            })
            
            # Save chunk to temporary file
            import tempfile
            import soundfile as sf
            
            chunk_audio = audio[start_sample:end_sample]
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_file:
                sf.write(tmp_file.name, chunk_audio, sr)
                chunk_path = tmp_file.name
            
            try:
                # Transcribe chunk
                chunk_result = asr_engine.transcribe(chunk_path, language, return_segments=True)
                
                if chunk_result and 'text' in chunk_result:
                    full_text += chunk_result['text'] + " "
                    
                if chunk_result and 'segments' in chunk_result:
                    # Adjust segment timestamps for chunk offset
                    time_offset = start_sample / sr
                    for segment in chunk_result['segments']:
                        segment['start'] += time_offset
                        segment['end'] += time_offset
                    all_segments.extend(chunk_result['segments'])
                    
            finally:
                # Clean up temporary file
                import os
                try:
                    os.unlink(chunk_path)
                except:
                    pass
        
        # Final processing
        await manager.broadcast({
            "type": "transcribe_progress",
            "job_id": job_id,
            "status": "finalizing",
            "progress": 90,
            "message": "結果をまとめています..."
        })
        
        # Combine results
        final_result = {
            'text': full_text.strip(),
            'segments': all_segments
        }
        
        await manager.broadcast({
            "type": "transcribe_progress",
            "job_id": job_id,
            "status": "completed",
            "progress": 100,
            "message": "文字起こし完了！"
        })
        
        return final_result
        
    except Exception as e:
        await manager.broadcast({
            "type": "transcribe_progress",
            "job_id": job_id,
            "status": "error",
            "progress": 0,
            "message": f"エラー: {str(e)}"
        })
        raise