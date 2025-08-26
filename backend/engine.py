# backend/engine.py
import os, sys, platform
from typing import Optional, List, Dict, Any

BACKEND = os.getenv("ASR_BACKEND", "auto")  # auto | mlx | ctranslate2
MODEL_ID = os.getenv("MODEL_ID")  # 明示指定がなければ各バックエンドのデフォルトを使う
LANG = os.getenv("ASR_LANG")  # 例: "ja", "en"。未指定なら自動検出

# Model definitions for each backend
MLX_MODELS = {
    "large-v3": "mlx-community/whisper-large-v3-mlx",
    "large-v3-turbo": "mlx-community/whisper-large-v3-turbo",
    "medium": "mlx-community/whisper-medium-mlx",
    "base": "mlx-community/whisper-base-mlx"
}

FASTER_WHISPER_MODELS = {
    "large-v3": "large-v3",
    "large-v3-turbo": "large-v3",  # Note: faster-whisper doesn't have separate turbo model
    "medium": "medium",
    "base": "base"
}

# DirectML (ONNX Runtime) models - uses OpenAI's official ONNX models
DIRECTML_MODELS = {
    "large-v3": "openai/whisper-large-v3",
    "large-v2": "openai/whisper-large-v2", 
    "medium": "openai/whisper-medium",
    "base": "openai/whisper-base"
}

class BaseASR:
    def __init__(self):
        self.current_model = None
        self.available_models = {}
    
    def transcribe(self, path: str, language: Optional[str] = None, return_segments: bool = False) -> Dict[str, Any]:
        """
        Transcribe audio file
        
        Returns:
        - return_segments=False: {"text": str}
        - return_segments=True: {"text": str, "segments": [{"start": float, "end": float, "text": str}]}
        """
        raise NotImplementedError
    
    def switch_model(self, model_name: str) -> Dict[str, Any]:
        """
        Switch to a different model
        
        Returns:
        - {"success": bool, "message": str, "current_model": str}
        """
        raise NotImplementedError
    
    def get_available_models(self) -> Dict[str, str]:
        """Get list of available models for this backend"""
        return self.available_models
    
    def get_current_model(self) -> str:
        """Get current model name"""
        return self.current_model or "unknown"

class MlxASR(BaseASR):
    def __init__(self):
        super().__init__()
        try:
            import mlx_whisper as mlxw  # pip: mlx-whisper
        except Exception as e:
            raise RuntimeError("mlx-whisper が見つかりません。requirements-mac.txt をインストールしてください") from e
        self.mlxw = mlxw
        self.available_models = MLX_MODELS
        
        # 初期モデルを設定 - 最高精度を重視
        default_model = "large-v3"
        if MODEL_ID:
            # 環境変数で指定されている場合はそれを使用
            for key, repo in MLX_MODELS.items():
                if MODEL_ID in repo or MODEL_ID == key:
                    default_model = key
                    break
        
        self.current_model = default_model
        self.repo = MLX_MODELS[self.current_model]

    def transcribe(self, path: str, language: Optional[str] = None, return_segments: bool = False) -> Dict[str, Any]:
        # mlx-whisper は辞書を返す実装です（コミュニティ実装を想定）。
        out = self.mlxw.transcribe(
            path,
            path_or_hf_repo=self.repo,
            language=language,
        )
        
        result = {"text": out.get("text", "")}
        
        if return_segments and "segments" in out:
            # MLX-whisperのsegments形式をそのまま使用
            result["segments"] = [
                {
                    "start": seg.get("start", 0.0),
                    "end": seg.get("end", 0.0),
                    "text": seg.get("text", "")
                }
                for seg in out["segments"]
            ]
        
        return result
    
    def switch_model(self, model_name: str) -> Dict[str, Any]:
        """Switch to a different MLX model"""
        if model_name not in MLX_MODELS:
            return {
                "success": False,
                "message": f"Model '{model_name}' not available. Available: {list(MLX_MODELS.keys())}",
                "current_model": self.current_model
            }
        
        try:
            self.current_model = model_name
            self.repo = MLX_MODELS[model_name]
            return {
                "success": True,
                "message": f"Successfully switched to {model_name}",
                "current_model": self.current_model
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Failed to switch model: {str(e)}",
                "current_model": self.current_model
            }

class FasterWhisperASR(BaseASR):
    def __init__(self):
        super().__init__()
        try:
            from faster_whisper import WhisperModel
            self.WhisperModel = WhisperModel
        except Exception as e:
            raise RuntimeError("faster-whisper が見つかりません。requirements-win.txt をインストールしてください") from e
        
        self.available_models = FASTER_WHISPER_MODELS
        self.device = os.getenv("GPU_DEVICE", "cuda")
        self.compute_type = os.getenv("COMPUTE_TYPE", "float16")  # float16 / int8_float16 / int8
        
        # 初期モデルを設定
        default_model = "large-v3"
        if MODEL_ID:
            # 環境変数で指定されている場合はそれを使用
            for key, model_name in FASTER_WHISPER_MODELS.items():
                if MODEL_ID == model_name or MODEL_ID == key:
                    default_model = key
                    break
        
        self.current_model = default_model
        self._load_model(default_model)
    
    def _load_model(self, model_name: str):
        """Load faster-whisper model"""
        model_id = FASTER_WHISPER_MODELS[model_name]
        try:
            self.model = self.WhisperModel(model_id, device=self.device, compute_type=self.compute_type)
            self.device_used = self.device
        except Exception:
            # CUDA が使えない場合は自動フォールバック
            self.model = self.WhisperModel(model_id, device="cpu", compute_type="int8")
            self.device_used = "cpu"

    def transcribe(self, path: str, language: Optional[str] = None, return_segments: bool = False) -> Dict[str, Any]:
        segments, info = self.model.transcribe(
            path,
            language=language,
            vad_filter=True,
            beam_size=5,
        )
        
        segments_list = list(segments)  # GeneratorをListに変換
        full_text = "".join(seg.text for seg in segments_list)
        
        result = {"text": full_text}
        
        if return_segments:
            result["segments"] = [
                {
                    "start": seg.start,
                    "end": seg.end,
                    "text": seg.text
                }
                for seg in segments_list
            ]
        
        return result
    
    def switch_model(self, model_name: str) -> Dict[str, Any]:
        """Switch to a different faster-whisper model"""
        if model_name not in FASTER_WHISPER_MODELS:
            return {
                "success": False,
                "message": f"Model '{model_name}' not available. Available: {list(FASTER_WHISPER_MODELS.keys())}",
                "current_model": self.current_model
            }
        
        try:
            old_model = self.current_model
            self.current_model = model_name
            self._load_model(model_name)
            return {
                "success": True,
                "message": f"Successfully switched from {old_model} to {model_name}",
                "current_model": self.current_model
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Failed to switch model: {str(e)}",
                "current_model": self.current_model
            }


class DirectMLASR(BaseASR):
    def __init__(self):
        super().__init__()
        try:
            import torch
            import transformers
            from transformers import WhisperProcessor, WhisperForConditionalGeneration
            import onnxruntime as ort
            self.torch = torch
            self.transformers = transformers
            self.WhisperProcessor = WhisperProcessor
            self.WhisperForConditionalGeneration = WhisperForConditionalGeneration
            self.ort = ort
        except Exception as e:
            raise RuntimeError(f"DirectML dependencies not found. Please install: pip install torch transformers onnxruntime-directml\nError: {e}") from e
        
        self.available_models = DIRECTML_MODELS
        
        # 初期モデルを設定 - 最高精度を重視
        default_model = "large-v3"
        if MODEL_ID:
            # 環境変数で指定されている場合はそれを使用
            for key, model_repo in DIRECTML_MODELS.items():
                if MODEL_ID in model_repo or MODEL_ID == key:
                    default_model = key
                    break
        
        self.current_model = default_model
        self._load_model(default_model)
    
    def _load_model(self, model_name: str):
        """Load DirectML-enabled Whisper model via transformers + ONNX Runtime"""
        model_repo = DIRECTML_MODELS[model_name]
        
        try:
            # Set DirectML provider for ONNX Runtime
            providers = ['DmlExecutionProvider', 'CPUExecutionProvider']
            
            print(f"Loading DirectML model: {model_repo}")
            self.processor = self.WhisperProcessor.from_pretrained(model_repo)
            self.model = self.WhisperForConditionalGeneration.from_pretrained(model_repo)
            
            # Try to use DirectML device if available
            if self.torch.cuda.is_available():
                # Use CUDA if available (DirectML can coexist)
                self.device = "cuda"
                self.model = self.model.to("cuda")
            else:
                # Use CPU as fallback (DirectML will be used internally by ONNX Runtime)
                self.device = "cpu"
                self.model = self.model.to("cpu")
            
            print(f"DirectML model loaded successfully on {self.device}")
            
        except Exception as e:
            print(f"DirectML model loading failed: {e}")
            raise e
    
    def transcribe(self, path: str, language: Optional[str] = None, return_segments: bool = False) -> Dict[str, Any]:
        """Transcribe audio using DirectML-enabled Whisper model"""
        try:
            import librosa
            
            # Load audio file
            audio, sr = librosa.load(path, sr=16000)
            
            # Process audio
            inputs = self.processor(audio, sampling_rate=16000, return_tensors="pt")
            
            # Move inputs to same device as model
            if self.device == "cuda":
                inputs = {k: v.to("cuda") for k, v in inputs.items()}
            
            # Generate transcription
            with self.torch.no_grad():
                if language:
                    # Force language if specified
                    forced_decoder_ids = self.processor.get_decoder_prompt_ids(language=language, task="transcribe")
                    predicted_ids = self.model.generate(
                        inputs["input_features"],
                        forced_decoder_ids=forced_decoder_ids,
                        return_timestamps=return_segments
                    )
                else:
                    predicted_ids = self.model.generate(
                        inputs["input_features"],
                        return_timestamps=return_segments
                    )
            
            # Decode results
            transcription = self.processor.batch_decode(predicted_ids, skip_special_tokens=True)[0]
            
            result = {"text": transcription}
            
            if return_segments:
                # For now, return the full text as a single segment
                # More sophisticated segment extraction would require additional processing
                duration = len(audio) / sr
                result["segments"] = [
                    {
                        "start": 0.0,
                        "end": duration,
                        "text": transcription
                    }
                ]
            
            return result
            
        except Exception as e:
            return {"text": f"DirectML transcription failed: {str(e)}"}
    
    def switch_model(self, model_name: str) -> Dict[str, Any]:
        """Switch to a different DirectML model"""
        if model_name not in DIRECTML_MODELS:
            return {
                "success": False,
                "message": f"Model '{model_name}' not available. Available: {list(DIRECTML_MODELS.keys())}",
                "current_model": self.current_model
            }
        
        try:
            old_model = self.current_model
            self.current_model = model_name
            self._load_model(model_name)
            return {
                "success": True,
                "message": f"Successfully switched from {old_model} to {model_name} (DirectML)",
                "current_model": self.current_model
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Failed to switch DirectML model: {str(e)}",
                "current_model": self.current_model
            }


def pick_backend() -> BaseASR:
    is_mac_arm = (sys.platform == "darwin" and platform.machine() == "arm64")
    is_windows = (sys.platform == "win32")

    if BACKEND == "mlx":
        return MlxASR()
    if BACKEND == "ctranslate2":
        return FasterWhisperASR()
    if BACKEND == "directml":
        return DirectMLASR()

    # auto selection
    if is_mac_arm:
        # macOS Apple Silicon: prefer MLX
        try:
            return MlxASR()
        except Exception:
            return FasterWhisperASR()
    elif is_windows:
        # Windows: try CUDA first, then DirectML, then CPU
        try:
            return FasterWhisperASR()
        except Exception:
            try:
                return DirectMLASR()
            except Exception:
                return FasterWhisperASR()  # CPU fallback
    else:
        # Linux/other: prefer faster-whisper
        return FasterWhisperASR()