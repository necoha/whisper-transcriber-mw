# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Whisper Transcriber is a cross-platform speech-to-text application with automatic GPU acceleration:
- **Frontend**: Electron application with web-based UI
- **Backend**: FastAPI server with platform-specific Whisper backends
- **Platform Support**: macOS (Apple Silicon MLX) and Windows (CUDA faster-whisper)
- **Models**: Whisper Large-v3 and Large-v3-Turbo with automatic backend selection

## Architecture

### Core Components
1. **Electron Main Process**: Spawns FastAPI backend and manages application lifecycle
2. **FastAPI Backend** (`backend/server.py`): Handles `/transcribe` endpoint with audio processing
3. **Engine Abstraction** (`backend/engine.py`): Automatic backend selection:
   - **macOS Apple Silicon**: MLX-whisper with Metal GPU acceleration
   - **Windows/NVIDIA**: faster-whisper with CUDA acceleration  
   - **Fallback**: CPU processing when GPU unavailable

### Backend Selection Logic
- Environment variable `ASR_BACKEND` (auto/mlx/ctranslate2)
- Automatic platform detection via `sys.platform` and `platform.machine()`
- Runtime fallback from GPU to CPU if hardware acceleration fails

## Development Commands

### Quick Start (3 Steps)
```bash
# 1. Dependency setup
# macOS:
bash scripts/setup_venv_mac.sh

# Windows:
./scripts/setup_venv_win.ps1

# 2. Development startup
cd electron
npm i
npm run dev

# 3. Test the application:
# - Click "接続確認" (Connection Test) → should return {"status": "ok"}
# - Select audio/video file and click "送信" for transcription
# - Use "● 録音開始" for real-time recording (FFmpeg recommended)
```

### Environment Variables
```bash
# Backend selection
ASR_BACKEND=auto|mlx|ctranslate2

# Model configuration  
MODEL_ID=mlx-community/whisper-large-v3-turbo  # MLX format
MODEL_ID=large-v3                              # faster-whisper format

# Language settings
ASR_LANG=ja|en|auto

# GPU settings (Windows)
GPU_DEVICE=cuda|cpu
COMPUTE_TYPE=float16|int8_float16|int8

# Server configuration
PORT=8765
```

### Manual Backend Testing
```bash
# Test FastAPI backend directly
cd backend
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
python server.py

# Check health endpoint
curl http://127.0.0.1:8765/health
```

### Building
```bash
# Development
cd electron && npm run dev

# Production build
cd electron && npm run build
```

## Key Implementation Details

### File Structure
```
whisper-transcriber/
├─ electron/                   # Electron application
│  ├─ src/main.js             # Main process + backend spawning
│  ├─ src/preload.js          # API bridge to renderer
│  ├─ src/renderer/           # Frontend UI
│  └─ src/util/bootstrap.js   # Backend process management
├─ backend/                    # FastAPI backend
│  ├─ server.py              # FastAPI endpoints (/health, /transcribe)
│  ├─ engine.py              # Backend abstraction (MlxASR, FasterWhisperASR)
│  ├─ requirements-common.txt # FastAPI, uvicorn, python-multipart
│  ├─ requirements-mac.txt    # mlx, mlx-whisper
│  └─ requirements-win.txt    # faster-whisper
└─ scripts/
   ├─ setup_venv_mac.sh      # macOS venv setup
   └─ setup_venv_win.ps1     # Windows venv setup
```

### Backend Process Management
- **Development**: `bootstrap.js` spawns `python server.py` with venv detection
- **Production**: `extraResources` bundles entire `backend/` directory
- **Fallback**: Uses system Python if venv not available
- **Cleanup**: Automatic process termination on app quit

### Audio Processing Pipeline
1. **File Upload**: Multipart form data to `/transcribe` endpoint
2. **Temporary Storage**: `tempfile.NamedTemporaryFile` with proper suffix detection
3. **Transcription**: Platform-appropriate backend (MLX/faster-whisper)
4. **Response**: JSON with transcribed text

### Platform-Specific Features
- **macOS MLX**: Metal GPU acceleration with `mlx-community` models
- **Windows CUDA**: VRAM optimization with `COMPUTE_TYPE` settings
- **Cross-platform**: WebM/Opus recording with MediaRecorder API

## Features Ready for Implementation

### Implemented Features
- ✅ **SRT/字幕出力**: Multiple subtitle formats with automatic download
- ✅ **Large-v3/Turbo切替UI**: Dynamic model switching via dropdown interface  
- ✅ **DirectML対応**: AMD/Intel GPU support with automatic detection
- ✅ **ストリーミング処理**: Chunked processing for long audio with real-time progress

### Planned Extensions  
- **テーマ切替**: Dark/Light mode support
- **音声品質向上**: VAD + noise reduction integration
- **WebSocket通信**: Enhanced real-time communication

### Configuration Options
- Model selection UI connected to `MODEL_ID` environment variable
- Language selection with automatic detection fallback
- GPU/CPU backend forcing for testing and optimization

## Troubleshooting

### Common Issues
- **MLX import error**: Ensure `requirements-mac.txt` installed in venv
- **CUDA not detected**: Check NVIDIA drivers, try `COMPUTE_TYPE=int8_float16`
- **WebM playback issues**: Install FFmpeg via system package manager
- **Backend connection refused**: Check if port 8765 is available
- **venv not found**: Scripts will fallback to system Python automatically

### Prerequisites
- **Node.js 20+**
- **Python 3.10+** 
- **FFmpeg** (optional, for audio format stability)
- **CUDA drivers** (Windows/NVIDIA)
- **Xcode Command Line Tools** (macOS)