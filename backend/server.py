# backend/server.py
import os, tempfile
from pathlib import Path
from fastapi import FastAPI, UploadFile, Form, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
import json
from engine import pick_backend, LANG
from subtitles import segments_to_srt, segments_to_vtt, segments_to_txt
from streaming import StreamingProcessor
from audio_enhancement import enhance_audio_file

PORT = int(os.getenv("PORT", "8765"))

# ユーザーのホームディレクトリベースの保存先を設定
import platform
from pathlib import Path

def get_default_save_dir():
    """プラットフォームに応じたデフォルト保存先を取得"""
    home = Path.home()
    system = platform.system()
    
    if system == "Darwin":  # macOS
        # Desktopが存在すればそちら、なければDownloads
        desktop = home / "Desktop"
        downloads = home / "Downloads"
        if desktop.exists():
            return desktop
        elif downloads.exists():
            return downloads
        else:
            return home
    elif system == "Windows":
        # Downloadsフォルダを優先
        downloads = home / "Downloads"
        if downloads.exists():
            return downloads
        else:
            return home / "Desktop" if (home / "Desktop").exists() else home
    else:  # Linux
        downloads = home / "Downloads"
        if downloads.exists():
            return downloads
        else:
            return home

OUTPUT_DIR = get_default_save_dir()

app = FastAPI(title="Whisper Local ASR")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

asr = pick_backend()
streaming_processor = StreamingProcessor(asr, websocket_manager=None)  # Will be set after manager is created

class ConnectionManager:
    """WebSocket connection manager"""
    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}
        
    async def connect(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        self.active_connections[client_id] = websocket
        
    def disconnect(self, client_id: str):
        if client_id in self.active_connections:
            del self.active_connections[client_id]
            
    async def send_personal_message(self, message: dict, client_id: str):
        if client_id in self.active_connections:
            try:
                await self.active_connections[client_id].send_text(json.dumps(message))
            except:
                # Connection closed, remove it
                self.disconnect(client_id)
                
    async def send_progress_update(self, job_id: str, progress_data: dict):
        """Send progress update to all clients interested in this job"""
        message = {
            "type": "progress_update",
            "job_id": job_id,
            "data": progress_data
        }
        
        # Send to all connected clients (in real implementation, 
        # you might want to track which clients are interested in which jobs)
        disconnected_clients = []
        for client_id, websocket in self.active_connections.items():
            try:
                await websocket.send_text(json.dumps(message))
            except:
                disconnected_clients.append(client_id)
                
        # Clean up disconnected clients
        for client_id in disconnected_clients:
            self.disconnect(client_id)
    
    async def broadcast(self, message: dict):
        """Broadcast message to all connected clients"""
        disconnected_clients = []
        for client_id, websocket in self.active_connections.items():
            try:
                await websocket.send_text(json.dumps(message))
            except:
                disconnected_clients.append(client_id)
                
        # Clean up disconnected clients
        for client_id in disconnected_clients:
            self.disconnect(client_id)

manager = ConnectionManager()

# Set the WebSocket manager for streaming processor
streaming_processor.websocket_manager = manager

def auto_save_transcription(filename: str, content: str, format: str, custom_path: str = None) -> str:
    """
    入力ファイル名と同じ名前でテキストファイルを自動保存
    
    Args:
        filename: 元のファイル名
        content: 保存する内容
        format: ファイル形式 (text, srt, vtt, txt)
        custom_path: カスタム保存先パス (指定されない場合はデフォルト)
    
    Returns:
        保存されたファイルのパス
    """
    if not filename:
        filename = "transcription"
    
    # 拡張子を除去してベースファイル名を取得
    base_name = Path(filename).stem
    
    # フォーマットに応じた拡張子を決定
    if format == "text":
        ext = ".txt"
    elif format == "srt":
        ext = ".srt"
    elif format == "vtt":
        ext = ".vtt"
    elif format == "txt":
        ext = ".txt"
    else:
        ext = ".txt"
    
    # 保存先ディレクトリを決定
    if custom_path:
        save_dir = Path(custom_path)
        if not save_dir.exists():
            try:
                save_dir.mkdir(parents=True, exist_ok=True)
            except:
                print(f"⚠️ カスタムパス作成失敗、デフォルトパスを使用: {OUTPUT_DIR}")
                save_dir = OUTPUT_DIR
    else:
        save_dir = OUTPUT_DIR
    
    # 保存ファイルパスを生成
    save_path = save_dir / f"{base_name}{ext}"
    
    # 同名ファイルが存在する場合は番号を付加
    counter = 1
    original_save_path = save_path
    while save_path.exists():
        save_path = save_dir / f"{base_name}_{counter}{ext}"
        counter += 1
    
    # ファイルに保存
    try:
        save_path.write_text(content, encoding='utf-8')
        print(f"✅ 自動保存完了: {save_path}")
        return str(save_path)
    except Exception as e:
        print(f"❌ 自動保存エラー: {e}")
        # フォールバック: デフォルトディレクトリに保存を試行
        if custom_path and save_dir != OUTPUT_DIR:
            try:
                fallback_path = OUTPUT_DIR / f"{base_name}{ext}"
                counter = 1
                while fallback_path.exists():
                    fallback_path = OUTPUT_DIR / f"{base_name}_{counter}{ext}"
                    counter += 1
                fallback_path.write_text(content, encoding='utf-8')
                print(f"✅ フォールバック保存完了: {fallback_path}")
                return str(fallback_path)
            except Exception as fallback_error:
                print(f"❌ フォールバック保存エラー: {fallback_error}")
        return ""

@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    """WebSocket endpoint for real-time communication"""
    await manager.connect(websocket, client_id)
    try:
        while True:
            # Keep connection alive and handle incoming messages
            data = await websocket.receive_text()
            message = json.loads(data)
            
            # Handle different message types
            if message.get("type") == "ping":
                await manager.send_personal_message({"type": "pong"}, client_id)
            elif message.get("type") == "subscribe_job":
                job_id = message.get("job_id")
                # In a more sophisticated implementation, you'd track job subscriptions
                await manager.send_personal_message({
                    "type": "job_subscribed", 
                    "job_id": job_id
                }, client_id)
                
    except WebSocketDisconnect:
        manager.disconnect(client_id)
    except Exception as e:
        print(f"WebSocket error for client {client_id}: {e}")
        manager.disconnect(client_id)

@app.get("/health")
async def health():
    return {
        "status": "ok", 
        "backend": type(asr).__name__,
        "current_model": asr.get_current_model(),
        "available_models": asr.get_available_models()
    }

@app.post("/transcribe")
async def transcribe(
    file: UploadFile, 
    language: str | None = Form(default=LANG),
    format: str = Form(default="text"),  # text | srt | vtt | txt
    enable_vad: bool = Form(default=True),
    enable_noise_reduction: bool = Form(default=True),
    vad_aggressiveness: int = Form(default=1),
    noise_reduce_strength: float = Form(default=0.6),
    save_path: str | None = Form(default=None)  # カスタム保存先パス
):
    """
    Transcribe audio file with optional audio enhancement
    
    Parameters:
    - file: Audio/video file to transcribe
    - language: Language code (ja, en, auto, etc.)
    - format: Output format (text, srt, vtt, txt)
    - enable_vad: Enable voice activity detection
    - enable_noise_reduction: Enable noise reduction
    - vad_aggressiveness: VAD aggressiveness level (0-3)
    - noise_reduce_strength: Noise reduction strength (0.0-1.0)
    - save_path: Custom save directory path (optional)
    """
    # 一時保存してから処理
    suffix = os.path.splitext(file.filename or "")[1] or ".webm"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(await file.read())
        path = tmp.name

    try:
        # Apply audio enhancement if requested
        enhanced_path = path
        if enable_vad or enable_noise_reduction:
            try:
                enhanced_path = enhance_audio_file(
                    input_path=path,
                    enable_vad=enable_vad,
                    enable_noise_reduction=enable_noise_reduction,
                    vad_aggressiveness=vad_aggressiveness,
                    noise_reduce_strength=noise_reduce_strength
                )
            except Exception as e:
                # Log enhancement error but continue with original audio
                print(f"Audio enhancement failed: {e}, using original audio")
                enhanced_path = path
        
        # Segments が必要な形式かどうかを判定
        return_segments = format in ["srt", "vtt", "txt"]
        
        # MLXWhisperでautoはサポートされていないため、Noneに変換
        if language == "auto":
            language = None
        
        # Generate job ID for progress tracking
        import uuid
        import librosa
        job_id = str(uuid.uuid4())[:8]
        
        # Get audio duration to decide processing method
        try:
            duration = librosa.get_duration(path=enhanced_path)
        except:
            duration = 60  # Default fallback
        
        # Send initial progress
        await manager.broadcast({
            "type": "transcribe_progress",
            "job_id": job_id,
            "status": "starting",
            "progress": 0,
            "message": "音声処理を開始中..."
        })
        
        # Use chunked processing for longer audio (>60 seconds)
        if duration > 60:
            from chunked_transcription import transcribe_with_progress
            result = await transcribe_with_progress(
                asr, enhanced_path, language, manager, job_id
            )
        else:
            # Short audio - use simple progress simulation
            stages = [
                (20, "モデルを読み込み中..."),
                (50, "音声を解析中..."),
                (80, "文字起こし処理中..."),
            ]
            
            import asyncio
            for progress, message in stages:
                await manager.broadcast({
                    "type": "transcribe_progress",
                    "job_id": job_id,
                    "status": "processing",
                    "progress": progress,
                    "message": message
                })
                await asyncio.sleep(0.2)  # Brief delay for visual effect
            
            result = asr.transcribe(enhanced_path, language, return_segments=return_segments)
            
            await manager.broadcast({
                "type": "transcribe_progress",
                "job_id": job_id, 
                "status": "completed",
                "progress": 100,
                "message": "文字起こし完了！"
            })
        
        if format == "text":
            # 自動保存
            saved_path = auto_save_transcription(file.filename, result["text"], format, save_path)
            return JSONResponse({
                "text": result["text"], 
                "format": "text",
                "saved_path": saved_path
            })
        
        elif format == "srt":
            if "segments" not in result:
                return JSONResponse(
                    {"error": "Segments not available for SRT format"}, 
                    status_code=400
                )
            srt_content = segments_to_srt(result["segments"])
            # 自動保存
            saved_path = auto_save_transcription(file.filename, srt_content, format, save_path)
            return Response(
                content=srt_content,
                media_type="text/plain",
                headers={
                    "Content-Disposition": f"attachment; filename={file.filename or 'transcription'}.srt",
                    "X-Saved-Path": saved_path
                }
            )
        
        elif format == "vtt":
            if "segments" not in result:
                return JSONResponse(
                    {"error": "Segments not available for VTT format"}, 
                    status_code=400
                )
            vtt_content = segments_to_vtt(result["segments"])
            # 自動保存
            saved_path = auto_save_transcription(file.filename, vtt_content, format, save_path)
            return Response(
                content=vtt_content,
                media_type="text/vtt",
                headers={
                    "Content-Disposition": f"attachment; filename={file.filename or 'transcription'}.vtt",
                    "X-Saved-Path": saved_path
                }
            )
        
        elif format == "txt":
            if "segments" not in result:
                return JSONResponse(
                    {"error": "Segments not available for TXT format"}, 
                    status_code=400
                )
            txt_content = segments_to_txt(result["segments"])
            # 自動保存
            saved_path = auto_save_transcription(file.filename, txt_content, format, save_path)
            return Response(
                content=txt_content,
                media_type="text/plain",
                headers={
                    "Content-Disposition": f"attachment; filename={file.filename or 'transcription'}.txt",
                    "X-Saved-Path": saved_path
                }
            )
        
        else:
            return JSONResponse(
                {"error": f"Unsupported format: {format}"}, 
                status_code=400
            )
    
    finally:
        # Clean up temporary files
        try:
            os.unlink(path)
        except:
            pass
        
        # Clean up enhanced audio file if different from original
        if 'enhanced_path' in locals() and enhanced_path != path:
            try:
                os.unlink(enhanced_path)
            except:
                pass

@app.get("/formats")
async def get_supported_formats():
    """Get list of supported output formats"""
    return {
        "formats": {
            "text": "Plain text transcription",
            "srt": "SubRip subtitle format (.srt)",
            "vtt": "WebVTT subtitle format (.vtt)",
            "txt": "Text with timestamps (.txt)"
        }
    }

@app.get("/save-config")
async def get_save_config():
    """現在の保存設定を取得"""
    return {
        "default_save_dir": str(OUTPUT_DIR),
        "platform": platform.system(),
        "available_dirs": {
            "home": str(Path.home()),
            "desktop": str(Path.home() / "Desktop") if (Path.home() / "Desktop").exists() else None,
            "downloads": str(Path.home() / "Downloads") if (Path.home() / "Downloads").exists() else None,
        }
    }

@app.get("/models")
async def get_models():
    """Get available models and current model"""
    return {
        "backend": type(asr).__name__,
        "current_model": asr.get_current_model(),
        "available_models": asr.get_available_models()
    }

@app.post("/models/switch")
async def switch_model(model_name: str = Form(...)):
    """Switch to a different model"""
    result = asr.switch_model(model_name)
    if result["success"]:
        return JSONResponse(result)
    else:
        return JSONResponse(result, status_code=400)

@app.get("/gpu")
async def get_gpu_info():
    """Get GPU information and backend recommendations"""
    try:
        from gpu_detect import get_gpu_info, check_directml_support, check_cuda_support
        
        info = get_gpu_info()
        info.update({
            "directml_available": check_directml_support(),
            "cuda_available": check_cuda_support(),
            "current_backend": type(asr).__name__
        })
        
        return JSONResponse(info)
    except Exception as e:
        return JSONResponse({
            "error": f"GPU detection failed: {str(e)}",
            "current_backend": type(asr).__name__,
            "platform": "unknown"
        })

@app.post("/transcribe/streaming")
async def transcribe_streaming(
    file: UploadFile, 
    language: str | None = Form(default=LANG),
    format: str = Form(default="text"),  # text | srt | vtt | txt
    chunk_duration: int = Form(default=30),  # seconds
    overlap_duration: int = Form(default=3),   # seconds
    enable_vad: bool = Form(default=True),
    enable_noise_reduction: bool = Form(default=True),
    vad_aggressiveness: int = Form(default=1),
    noise_reduce_strength: float = Form(default=0.6)
):
    """
    Start streaming transcription for long audio files
    
    Returns job_id for tracking progress
    """
    # Save uploaded file temporarily
    suffix = os.path.splitext(file.filename or "")[1] or ".webm"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(await file.read())
        path = tmp.name
    
    try:
        # Configure chunker
        from streaming import AudioChunker
        chunker = AudioChunker(
            chunk_duration=chunk_duration,
            overlap_duration=overlap_duration
        )
        streaming_processor.chunker = chunker
        
        # Determine if segments are needed
        return_segments = format in ["srt", "vtt", "txt"]
        
        # MLXWhisperでautoはサポートされていないため、Noneに変換
        if language == "auto":
            language = None
        
        # Start streaming processing with audio enhancement options
        result = await streaming_processor.process_streaming(
            path, language, return_segments,
            enable_vad=enable_vad,
            enable_noise_reduction=enable_noise_reduction,
            vad_aggressiveness=vad_aggressiveness,
            noise_reduce_strength=noise_reduce_strength
        )
        
        return JSONResponse(result)
        
    except Exception as e:
        # Clean up file on error
        try:
            os.unlink(path)
        except:
            pass
        return JSONResponse(
            {"error": f"Streaming transcription failed: {str(e)}"},
            status_code=500
        )

@app.get("/transcribe/streaming/{job_id}")
async def get_streaming_status(job_id: str):
    """Get streaming transcription job status"""
    status = streaming_processor.get_job_status(job_id)
    return JSONResponse(status)

@app.get("/transcribe/streaming/{job_id}/result")
async def get_streaming_result(job_id: str, format: str = "text"):
    """Get final streaming transcription result in specified format"""
    status = streaming_processor.get_job_status(job_id)
    
    if "error" in status:
        return JSONResponse(status, status_code=404)
    
    if status.get("status") != "completed":
        return JSONResponse(
            {"error": "Job not completed yet", "current_status": status.get("status")},
            status_code=202
        )
    
    try:
        if format == "text":
            return JSONResponse({
                "text": status.get("full_text", ""),
                "format": "text",
                "chunks_processed": status.get("total_chunks", 0)
            })
        
        elif format in ["srt", "vtt", "txt"]:
            segments = status.get("combined_segments", [])
            if not segments:
                return JSONResponse(
                    {"error": "No segments available for subtitle format"},
                    status_code=400
                )
            
            if format == "srt":
                content = segments_to_srt(segments)
                media_type = "text/plain"
            elif format == "vtt":
                content = segments_to_vtt(segments)
                media_type = "text/vtt"
            elif format == "txt":
                content = segments_to_txt(segments)
                media_type = "text/plain"
            
            return Response(
                content=content,
                media_type=media_type,
                headers={
                    "Content-Disposition": f"attachment; filename=streaming_transcription.{format}"
                }
            )
        
        else:
            return JSONResponse(
                {"error": f"Unsupported format: {format}"},
                status_code=400
            )
    
    finally:
        # Clean up completed job after retrieving result
        streaming_processor.cleanup_job(job_id)

@app.delete("/transcribe/streaming/{job_id}")
async def cancel_streaming_job(job_id: str):
    """Cancel streaming transcription job"""
    success = streaming_processor.cleanup_job(job_id)
    if success:
        return JSONResponse({"message": "Job cancelled"})
    else:
        return JSONResponse({"error": "Job not found"}, status_code=404)

@app.get("/transcribe/streaming")
async def list_streaming_jobs():
    """List active streaming jobs"""
    jobs = streaming_processor.list_active_jobs()
    return JSONResponse({"active_jobs": jobs})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=PORT)