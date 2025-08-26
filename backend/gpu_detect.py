# backend/gpu_detect.py
import sys, platform, subprocess

def get_gpu_info():
    """Get detailed GPU information for backend selection"""
    info = {
        "platform": platform.system(),
        "machine": platform.machine(), 
        "gpus": [],
        "recommended_backend": "cpu"
    }
    
    if platform.system() == "Windows":
        info.update(get_windows_gpu_info())
    elif platform.system() == "Darwin":
        info.update(get_macos_gpu_info())
    else:
        info.update(get_linux_gpu_info())
    
    return info

def get_windows_gpu_info():
    """Get Windows GPU information using wmic"""
    gpus = []
    recommended = "cpu"
    
    try:
        # Query GPU information
        result = subprocess.run([
            "wmic", "path", "win32_VideoController", "get", 
            "name,AdapterCompatibility,AdapterRAM", "/format:csv"
        ], capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            lines = [line.strip() for line in result.stdout.split('\n') if line.strip()]
            headers = lines[0].split(',') if lines else []
            
            for line in lines[1:]:
                if not line:
                    continue
                fields = line.split(',')
                if len(fields) >= len(headers):
                    gpu_name = ""
                    compatibility = ""
                    
                    # Find name and compatibility fields
                    for i, header in enumerate(headers):
                        if 'name' in header.lower() and i < len(fields):
                            gpu_name = fields[i]
                        elif 'compatibility' in header.lower() and i < len(fields):
                            compatibility = fields[i]
                    
                    if gpu_name and gpu_name != "Name":
                        gpu_info = {
                            "name": gpu_name,
                            "vendor": compatibility,
                            "type": classify_gpu(gpu_name)
                        }
                        gpus.append(gpu_info)
        
        # Determine recommended backend
        nvidia_found = any(gpu["type"] == "nvidia" for gpu in gpus)
        amd_found = any(gpu["type"] == "amd" for gpu in gpus)
        intel_found = any(gpu["type"] == "intel" for gpu in gpus)
        
        if nvidia_found:
            recommended = "ctranslate2"  # CUDA
        elif amd_found or intel_found:
            recommended = "directml"  # DirectML for AMD/Intel
        else:
            recommended = "cpu"
    
    except Exception as e:
        print(f"GPU detection failed: {e}")
    
    return {"gpus": gpus, "recommended_backend": recommended}

def get_macos_gpu_info():
    """Get macOS GPU information"""
    gpus = []
    recommended = "cpu"
    
    try:
        # Check for Apple Silicon
        if platform.machine() == "arm64":
            gpus.append({
                "name": f"Apple {platform.processor()} GPU",
                "vendor": "Apple", 
                "type": "apple"
            })
            recommended = "mlx"
        else:
            # Intel Mac - check system profiler
            result = subprocess.run([
                "system_profiler", "SPDisplaysDataType"
            ], capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                lines = result.stdout.split('\n')
                current_gpu = {}
                for line in lines:
                    line = line.strip()
                    if "Chipset Model:" in line:
                        gpu_name = line.split(":")[-1].strip()
                        gpu_info = {
                            "name": gpu_name,
                            "vendor": "Unknown",
                            "type": classify_gpu(gpu_name)
                        }
                        gpus.append(gpu_info)
            
            recommended = "ctranslate2"  # Intel Mac uses CPU/CUDA if available
    
    except Exception as e:
        print(f"macOS GPU detection failed: {e}")
    
    return {"gpus": gpus, "recommended_backend": recommended}

def get_linux_gpu_info():
    """Get Linux GPU information using lspci"""
    gpus = []
    recommended = "cpu"
    
    try:
        result = subprocess.run(["lspci"], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            lines = result.stdout.split('\n')
            for line in lines:
                if any(keyword in line.lower() for keyword in ["vga", "3d", "display"]):
                    gpu_info = {
                        "name": line.strip(),
                        "vendor": "Unknown",
                        "type": classify_gpu(line)
                    }
                    gpus.append(gpu_info)
        
        # Simple classification for Linux
        nvidia_found = any("nvidia" in gpu["name"].lower() for gpu in gpus)
        amd_found = any("amd" in gpu["name"].lower() or "radeon" in gpu["name"].lower() for gpu in gpus)
        
        if nvidia_found:
            recommended = "ctranslate2"
        elif amd_found:
            recommended = "directml"  # If available on Linux
        else:
            recommended = "ctranslate2"  # CPU fallback
    
    except Exception as e:
        print(f"Linux GPU detection failed: {e}")
    
    return {"gpus": gpus, "recommended_backend": recommended}

def classify_gpu(gpu_name: str) -> str:
    """Classify GPU type based on name"""
    name_lower = gpu_name.lower()
    
    if any(keyword in name_lower for keyword in ["nvidia", "geforce", "rtx", "gtx", "quadro", "tesla"]):
        return "nvidia"
    elif any(keyword in name_lower for keyword in ["amd", "radeon", "rx ", "vega", "navi"]):
        return "amd" 
    elif any(keyword in name_lower for keyword in ["intel", "iris", "uhd", "hd graphics", "xe"]):
        return "intel"
    elif "apple" in name_lower:
        return "apple"
    else:
        return "unknown"

def check_directml_support():
    """Check if DirectML is available"""
    try:
        import onnxruntime as ort
        providers = ort.get_available_providers()
        return 'DmlExecutionProvider' in providers
    except:
        return False

def check_cuda_support():
    """Check if CUDA is available"""
    try:
        import torch
        return torch.cuda.is_available()
    except:
        return False

if __name__ == "__main__":
    info = get_gpu_info()
    print("GPU Detection Results:")
    print(f"Platform: {info['platform']} ({info['machine']})")
    print(f"Recommended backend: {info['recommended_backend']}")
    print("\nDetected GPUs:")
    for i, gpu in enumerate(info['gpus'], 1):
        print(f"  {i}. {gpu['name']} ({gpu['type']})")
    
    print(f"\nDirectML support: {check_directml_support()}")
    print(f"CUDA support: {check_cuda_support()}")