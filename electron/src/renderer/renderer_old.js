const API = window.WHISPER_APP.apiBase;
const WS_API = API.replace('http', 'ws'); // Convert HTTP to WebSocket URL

const $ = (id) => document.getElementById(id);

let currentFormat = 'text';
let lastResult = null;
let currentBackend = null;
let availableModels = {};
let currentStreamingJob = null;
let streamingPollInterval = null;

// WebSocket connection management
let websocket = null;
let clientId = generateClientId();
let useWebSocket = true; // Feature flag for WebSocket usage

function generateClientId() {
  return 'client_' + Math.random().toString(36).substr(2, 9);
}

// WebSocket connection
function initWebSocket() {
  if (!useWebSocket) return;
  
  const wsUrl = `${WS_API}/ws/${clientId}`;
  console.log('Connecting to WebSocket:', wsUrl);
  
  websocket = new WebSocket(wsUrl);
  
  websocket.onopen = function(event) {
    console.log('WebSocket connected');
    showStatus('リアルタイム通信が有効になりました', 'success');
  };
  
  websocket.onmessage = function(event) {
    const message = JSON.parse(event.data);
    handleWebSocketMessage(message);
  };
  
  websocket.onclose = function(event) {
    console.log('WebSocket disconnected');
    // Try to reconnect after 3 seconds
    setTimeout(() => {
      if (useWebSocket) {
        initWebSocket();
      }
    }, 3000);
  };
  
  websocket.onerror = function(error) {
    console.error('WebSocket error:', error);
    useWebSocket = false; // Fallback to polling
    showStatus('WebSocket接続失敗、ポーリングモードに切り替えました', 'error');
  };
}

// Handle WebSocket messages
function handleWebSocketMessage(message) {
  console.log('WebSocket message:', message);
  
  if (message.type === 'progress_update') {
    const data = message.data;
    
    // Update progress UI
    if (message.job_id === currentStreamingJob) {
      updateStreamingProgress(data);
    }
  } else if (message.type === 'pong') {
    // Handle ping response
    console.log('WebSocket pong received');
  }
}

// Update streaming progress from WebSocket data
function updateStreamingProgress(data) {
  const progress = data.progress || 0;
  const currentChunk = data.current_chunk || 0;
  const totalChunks = data.total_chunks || 0;
  
  let statusText = '';
  if (data.status === 'chunking') {
    statusText = '音声を分割中...';
  } else if (data.status === 'transcribing') {
    statusText = `チャンク ${currentChunk}/${totalChunks} を処理中`;
  } else if (data.status === 'completed') {
    statusText = '処理完了！';
    handleStreamingCompletion(data);
  } else if (data.status === 'failed') {
    statusText = `処理失敗: ${data.error || 'Unknown error'}`;
    showStatus(`ストリーミング処理失敗: ${data.error || 'Unknown error'}`, 'error');
    resetStreamingUI();
  }
  
  updateProgress(progress, statusText);
  
  // Update partial results in real-time
  if (data.full_text) {
    $('out').value = data.full_text;
    lastResult = data.full_text;
  }
}

// Handle streaming completion from WebSocket
function handleStreamingCompletion(data) {
  // Show completed result
  if (data.full_text) {
    $('out').value = data.full_text;
    lastResult = data.full_text;
    $('copy').style.display = 'inline-block';
    $('save').style.display = 'inline-block';
  }
  
  showStatus(`ストリーミング処理完了 (${data.total_chunks || 0} チャンク処理)`, 'success');
  
  // For subtitle formats, still need to fetch the file
  if (currentFormat !== 'text') {
    downloadStreamingResult();
  } else {
    resetStreamingUI();
  }
}

// Download streaming result file for subtitle formats
async function downloadStreamingResult() {
  try {
    const resultRes = await fetch(`${API}/transcribe/streaming/${currentStreamingJob}/result?format=${currentFormat}`);
    
    if (currentFormat !== 'text') {
      const blob = await resultRes.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.style.display = 'none';
      a.href = url;
      a.download = `streaming_transcription.${currentFormat}`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
      
      showStatus(`ストリーミング${currentFormat.toUpperCase()}ファイル完成`, 'success');
    }
  } catch (error) {
    showStatus(`結果取得エラー: ${error.message}`, 'error');
  } finally {
    resetStreamingUI();
  }
}

// Initialize everything on page load
document.addEventListener('DOMContentLoaded', () => {
  initializeTheme();
  initWebSocket();
  initializeFormatSelection();
  initializeEventHandlers();
});

// Format selection handling
function initializeFormatSelection() {
  document.querySelectorAll('.format-btn').forEach(btn => {
    btn.onclick = () => {
      document.querySelectorAll('.format-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      currentFormat = btn.dataset.format;
      console.log('Selected format:', currentFormat);
    };
  });
}

// Initialize all event handlers
function initializeEventHandlers() {
  // Health check and model loading
  $('health').onclick = async () => {
    try {
      const r = await fetch(`${API}/health`).then((r) => r.json());
      currentBackend = r.backend;
      availableModels = r.available_models || {};
      
      // Update model dropdown
      updateModelDropdown(r.current_model);
      
      // Update model info display
      updateModelInfo(r);
      
      showStatus(`Backend接続OK: ${r.backend || 'Unknown'} (${r.status})`, 'success');
      
      // Enable model switching
      $('switch-model').disabled = false;
      
    } catch (error) {
      showStatus(`Backend接続失敗: ${error.message}`, 'error');
      console.error('Health check failed:', error);
    }
  };
  
  // Model switching
  $('switch-model').onclick = async () => {
    const selectedModel = $('model').value;
    if (!selectedModel) {
      showStatus('モデルを選択してください', 'error');
      return;
    }
    
    try {
      $('switch-model').disabled = true;
      showStatus(`${selectedModel}に切り替え中...`, 'success');
      
      const fd = new FormData();
      fd.append('model_name', selectedModel);
      
      const response = await fetch(`${API}/models/switch`, {
        method: 'POST',
        body: fd
      });
      
      const result = await response.json();
      
      if (response.ok && result.success) {
        showStatus(`モデル切り替え完了: ${result.current_model}`, 'success');
        updateModelInfo(result);
      } else {
        showStatus(`モデル切り替え失敗: ${result.error || 'Unknown error'}`, 'error');
      }
      
    } catch (error) {
      showStatus(`モデル切り替え失敗: ${error.message}`, 'error');
    } finally {
      $('switch-model').disabled = false;
    }
  };
  
  // GPU info
  $('gpu-info').onclick = async () => {
    try {
      const response = await fetch(`${API}/gpu`);
      const info = await response.json();
      
      let message = `Platform: ${info.platform}\n`;
      message += `Current Backend: ${info.current_backend}\n`;
      message += `Recommended: ${info.recommended_backend}\n`;
      
      if (info.gpus && info.gpus.length > 0) {
        message += `GPUs:\n`;
        info.gpus.forEach((gpu, i) => {
          const emoji = getGpuEmoji(gpu.type);
          message += `  ${emoji} ${gpu.name} (${gpu.vendor})\n`;
        });
      }
      
      message += `\nDirectML Available: ${info.directml_available ? '✅' : '❌'}`;
      message += `\nCUDA Available: ${info.cuda_available ? '✅' : '❌'}`;
      
      alert(message);
      
    } catch (error) {
      showStatus(`GPU情報取得失敗: ${error.message}`, 'error');
    }
  };
  
  // File transcription
  $('send').onclick = async () => {
    const file = $('file').files[0];
    if (!file) {
      showStatus('ファイルを選択してください', 'error');
      return;
    }

    const fd = new FormData();
    fd.append('file', file, file.name);
    
    const lang = $('lang').value.trim();
    if (lang) fd.append('language', lang);
    
    fd.append('format', currentFormat);
    
    // Add audio enhancement parameters
    fd.append('enable_vad', $('enable-vad').checked);
    fd.append('enable_noise_reduction', $('enable-noise-reduction').checked);
    fd.append('vad_aggressiveness', $('vad-aggressiveness').value);
    fd.append('noise_reduce_strength', $('noise-strength').value);

    try {
      showStatus('処理中...', 'success');
      $('send').disabled = true;
      
      const res = await fetch(`${API}/transcribe`, { method: 'POST', body: fd });
      
      if (currentFormat === 'text') {
        const data = await res.json();
        if (res.ok) {
          $('out').value = data.text;
          lastResult = data.text;
          $('copy').style.display = 'inline-block';
          $('save').style.display = 'inline-block';
          showStatus('文字起こし完了', 'success');
        } else {
          throw new Error(data.error || `HTTP ${res.status}`);
        }
      } else {
        // Handle file download for subtitle formats
        if (res.ok) {
          const blob = await res.blob();
          const url = window.URL.createObjectURL(blob);
          const a = document.createElement('a');
          a.style.display = 'none';
          a.href = url;
          a.download = `transcription.${currentFormat}`;
          document.body.appendChild(a);
          a.click();
          window.URL.revokeObjectURL(url);
          document.body.removeChild(a);
          
          // Also show result in textarea if possible
          const text = await blob.text();
          $('out').value = text;
          lastResult = text;
          $('copy').style.display = 'inline-block';
          $('save').style.display = 'inline-block';
          showStatus(`${currentFormat.toUpperCase()}ファイル生成完了`, 'success');
        } else {
          const errorData = await res.json();
          throw new Error(errorData.error || `HTTP ${res.status}`);
        }
      }
      
    } catch (error) {
      showStatus(`エラー: ${error.message}`, 'error');
      console.error('Transcription error:', error);
    } finally {
      $('send').disabled = false;
    }
  };
  
  // Recording functionality
  $('rec').onclick = async () => {
    // Recording implementation would go here
    showStatus('録音機能は実装中です', 'error');
  };
  
  // Copy result
  $('copy').onclick = async () => {
    if (!lastResult) return;
    
    try {
      await navigator.clipboard.writeText(lastResult);
      showStatus('結果をクリップボードにコピーしました', 'success');
    } catch (err) {
      showStatus('コピーに失敗しました', 'error');
    }
  };

  // Save result
  $('save').onclick = () => {
    if (!lastResult) return;
    
    const blob = new Blob([lastResult], { type: 'text/plain' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'transcription.txt';
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);
  };
}

// Status display helper
function showStatus(message, type = 'success') {
  const status = $('status');
  status.textContent = message;
  status.className = `status ${type}`;
  status.style.display = 'block';
  setTimeout(() => {
    status.style.display = 'none';
  }, 5000);
}

// Update model dropdown with available models
function updateModelDropdown(currentModel) {
  const modelSelect = $('model');
  modelSelect.innerHTML = '';
  
  if (Object.keys(availableModels).length === 0) {
    modelSelect.innerHTML = '<option value="">モデル情報なし</option>';
    modelSelect.disabled = true;
    return;
  }
  
  for (const [modelKey, modelRepo] of Object.entries(availableModels)) {
    const option = document.createElement('option');
    option.value = modelKey;
    option.textContent = getModelDisplayName(modelKey, modelRepo);
    if (modelKey === currentModel) {
      option.selected = true;
    }
    modelSelect.appendChild(option);
  }
  
  modelSelect.disabled = false;
}

// Get user-friendly model display name
function getModelDisplayName(modelKey, modelRepo) {
  const displayNames = {
    'large-v3': '🎯 Large-v3 (高精度)',
    'large-v3-turbo': '🚀 Large-v3-Turbo (高速)',
    'medium': '⚖️ Medium (バランス)',
    'base': '⚡ Base (軽量)'
  };
  
  return displayNames[modelKey] || `${modelKey} (${modelRepo})`;
}

// Update model info display
function updateModelInfo(healthData) {
  const info = $('model-info');
  info.innerHTML = `
    <strong>現在:</strong> ${healthData.backend} | 
    <strong>モデル:</strong> ${getModelDisplayName(healthData.current_model, availableModels[healthData.current_model] || '')} | 
    <strong>利用可能:</strong> ${Object.keys(availableModels).length}個
  `;
}

// Get GPU type emoji
function getGpuEmoji(type) {
  const emojis = {
    'nvidia': '🟢',
    'amd': '🔴', 
    'intel': '🔵',
    'apple': '🍎',
    'unknown': '❓'
  };
  return emojis[type] || '❓';
}

// Recording functionality
let media, recorder, chunks = [];
$('rec').onclick = async () => {
  if (!recorder) {
    try {
      media = await navigator.mediaDevices.getUserMedia({ audio: true });
      recorder = new MediaRecorder(media, { mimeType: 'audio/webm' });
      chunks = [];
      recorder.ondataavailable = e => chunks.push(e.data);
      recorder.onstop = async () => {
        const blob = new Blob(chunks, { type: 'audio/webm' });
        const fd = new FormData();
        fd.append('file', blob, 'recording.webm');
        const lang = $('lang').value.trim();
        if (lang) fd.append('language', lang);
        fd.append('format', currentFormat);

        try {
          showStatus('録音を処理中...', 'success');
          const res = await fetch(`${API}/transcribe`, { method: 'POST', body: fd });
          
          if (!res.ok) {
            const errorData = await res.json();
            throw new Error(errorData.error || `HTTP ${res.status}`);
          }

          if (currentFormat === 'text') {
            const json = await res.json();
            $('out').value = json.text || '';
            lastResult = json.text;
            showStatus('録音の文字起こしが完了しました', 'success');
          } else {
            const blob = await res.blob();
            const text = await blob.text();
            $('out').value = text;
            lastResult = text;
            showStatus(`録音の${currentFormat.toUpperCase()}変換が完了しました`, 'success');
          }
          
          $('copy').style.display = 'inline-block';
          $('save').style.display = 'inline-block';
        } catch (error) {
          showStatus(`録音処理エラー: ${error.message}`, 'error');
        }

        $('rec').textContent = '● 録音開始';
        $('recstate').textContent = '';
        media.getTracks().forEach(t => t.stop());
        recorder = null; 
        chunks = []; 
        media = null;
      };
      recorder.start();
      $('rec').textContent = '■ 録音停止（送信）';
      $('rec').className = 'btn-danger';
      $('recstate').textContent = '録音中...';
      showStatus('録音を開始しました', 'success');
    } catch (error) {
      showStatus(`録音開始エラー: ${error.message}`, 'error');
    }
  } else {
    recorder.stop();
    $('rec').className = 'btn-warning';
  }
};

// Copy result to clipboard
$('copy').onclick = async () => {
  if (lastResult) {
    try {
      await navigator.clipboard.writeText(lastResult);
      showStatus('クリップボードにコピーしました', 'success');
    } catch (error) {
      showStatus('コピーに失敗しました', 'error');
    }
  }
};

// Save result to file

// Streaming transcription
$('streaming-send').onclick = async () => {
  const file = $('streaming-file').files[0];
  if (!file) {
    showStatus('ストリーミング用のファイルを選択してください', 'error');
    return;
  }

  const fd = new FormData();
  fd.append('file', file, file.name);
  
  const lang = $('lang').value.trim();
  if (lang) fd.append('language', lang);
  
  fd.append('format', currentFormat);
  fd.append('chunk_duration', $('chunk-duration').value);
  fd.append('overlap_duration', $('overlap-duration').value);
  
  // Add audio enhancement parameters for streaming
  fd.append('enable_vad', $('streaming-enable-vad').checked);
  fd.append('enable_noise_reduction', $('streaming-enable-noise-reduction').checked);
  fd.append('vad_aggressiveness', $('streaming-vad-aggressiveness').value);
  fd.append('noise_reduce_strength', $('streaming-noise-strength').value);

  try {
    showStatus('ストリーミング処理を開始します...', 'success');
    
    // Disable buttons
    $('streaming-send').disabled = true;
    $('streaming-send').textContent = '処理中...';
    $('streaming-cancel').disabled = false;
    
    // Show progress bar
    $('streaming-progress').style.display = 'block';
    updateProgress(0, '処理を開始しています...');

    const res = await fetch(`${API}/transcribe/streaming`, { 
      method: 'POST', 
      body: fd 
    });

    if (!res.ok) {
      const errorData = await res.json();
      throw new Error(errorData.error || `HTTP ${res.status}`);
    }

    const result = await res.json();
    currentStreamingJob = result.job_id;
    
    showStatus(`ストリーミング処理開始 (Job ID: ${result.job_id})`, 'success');
    
    // Start polling for progress
    startStreamingPoll();

  } catch (error) {
    showStatus(`ストリーミング処理エラー: ${error.message}`, 'error');
    resetStreamingUI();
  }
};

// Start polling streaming job progress (fallback when WebSocket is not available)
function startStreamingPoll() {
  // If WebSocket is available and working, don't use polling
  if (useWebSocket && websocket && websocket.readyState === WebSocket.OPEN) {
    console.log('WebSocket is active, skipping polling');
    return;
  }
  
  console.log('Starting polling mode for streaming progress');
  
  if (streamingPollInterval) {
    clearInterval(streamingPollInterval);
  }
  
  streamingPollInterval = setInterval(async () => {
    if (!currentStreamingJob) return;
    
    try {
      const statusRes = await fetch(`${API}/transcribe/streaming/${currentStreamingJob}`);
      const status = await statusRes.json();
      
      if (status.error) {
        showStatus(`ストリーミング処理エラー: ${status.error}`, 'error');
        resetStreamingUI();
        return;
      }
      
      // Update progress
      const progress = status.progress || 0;
      const currentChunk = status.current_chunk || 0;
      const totalChunks = status.total_chunks || 0;
      
      let statusText = '';
      if (status.status === 'chunking') {
        statusText = '音声を分割中...';
      } else if (status.status === 'transcribing') {
        statusText = `チャンク ${currentChunk}/${totalChunks} を処理中`;
      } else if (status.status === 'completed') {
        statusText = '処理完了！';
      } else if (status.status === 'failed') {
        statusText = `処理失敗: ${status.error}`;
      }
      
      updateProgress(progress, statusText);
      
      // Update partial results in real-time
      if (status.full_text) {
        $('out').value = status.full_text;
        lastResult = status.full_text;
      }
      
      // Handle completion
      if (status.status === 'completed') {
        await handleStreamingCompletion();
      } else if (status.status === 'failed') {
        showStatus(`ストリーミング処理失敗: ${status.error}`, 'error');
        resetStreamingUI();
      }
      
    } catch (error) {
      console.error('Polling error:', error);
    }
  }, 1000); // Poll every second
}

// Handle streaming completion
async function handleStreamingCompletion() {
  try {
    // Get final result
    const resultRes = await fetch(`${API}/transcribe/streaming/${currentStreamingJob}/result?format=${currentFormat}`);
    
    if (currentFormat === 'text') {
      const result = await resultRes.json();
      $('out').value = result.text;
      lastResult = result.text;
      $('copy').style.display = 'inline-block';
      $('save').style.display = 'inline-block';
      showStatus(`ストリーミング処理完了 (${result.chunks_processed} チャンク処理)`, 'success');
    } else {
      // Handle file download for subtitle formats
      const blob = await resultRes.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.style.display = 'none';
      a.href = url;
      a.download = `streaming_transcription.${currentFormat}`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
      
      // Also show in textarea
      const text = await blob.text();
      $('out').value = text;
      lastResult = text;
      $('copy').style.display = 'inline-block';
      $('save').style.display = 'inline-block';
      showStatus(`ストリーミング${currentFormat.toUpperCase()}ファイル完成`, 'success');
    }
    
  } catch (error) {
    showStatus(`結果取得エラー: ${error.message}`, 'error');
  } finally {
    resetStreamingUI();
  }
}

// Cancel streaming job

// Update progress bar
function updateProgress(percent, text) {
  $('progress-fill').style.width = `${Math.min(percent, 100)}%`;
  $('progress-text').textContent = `${Math.round(percent)}%`;
  $('streaming-status').textContent = text;
}

// Reset streaming UI
function resetStreamingUI() {
  if (streamingPollInterval) {
    clearInterval(streamingPollInterval);
    streamingPollInterval = null;
  }
  
  currentStreamingJob = null;
  $('streaming-send').disabled = false;
  $('streaming-send').textContent = 'ストリーミング処理開始';
  $('streaming-cancel').disabled = true;
  $('streaming-progress').style.display = 'none';
  updateProgress(0, '');
}

// Initialize theme when page loads (remove duplicate initialization)
// This is now handled in the combined DOMContentLoaded above