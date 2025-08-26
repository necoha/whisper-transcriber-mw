# 🎤 Whisper Transcriber - Full-Stack Speech-to-Text Suite

高精度な音声文字起こしアプリケーション（MLX Whisper対応）

Cross-platform speech-to-text application with **SRT/WebVTT subtitle export**, **dynamic model switching**, **DirectML GPU support**, **streaming processing** and **real-time progress tracking**.

## ✨ Features

- **🎙️ 音声文字起こし**: ファイルアップロード + リアルタイム録音
- **🎬 字幕出力**: SRT, WebVTT, タイムスタンプ付きテキスト形式
- **⚡ GPU加速**: macOS(MLX) / Windows(CUDA) / DirectML(AMD/Intel) 自動選択
- **🔄 モデル切替**: Large-v3 ⇔ Large-v3-Turbo を動的に切替
- **🎮 GPU検出**: リアルタイム GPU 情報表示と最適バックエンド推奨
- **📺 ストリーミング処理**: 長時間音声の分割処理＋リアルタイム進捗表示
- **📱 モダンUI**: Electron + FastAPI アーキテクチャ

## 🚀 クイックスタート（3ステップ）

### 1. 依存関係のセットアップ

**macOS:**
```bash
bash scripts/setup_venv_mac.sh
```

**Windows (NVIDIA GPU):**
```powershell
./scripts/setup_venv_win.ps1
```

**Windows (AMD/Intel GPU - DirectML):**
```powershell
./scripts/setup_venv_win_directml.ps1
```

### 2. 開発サーバー起動

```bash
cd electron
npm i
npm run dev
```

### 3. テスト

1. **接続確認** ボタンをクリック → `{"status": "ok"}` が表示されればOK
2. **🎮 GPU情報** ボタンで現在のGPU構成を確認
   - 🟢 NVIDIA GPU: CUDA推奨
   - 🔴 AMD GPU: DirectML推奨  
   - 🔵 Intel GPU: DirectML推奨
   - 🍎 Apple Silicon: MLX推奨
3. **モデル選択**: ドロップダウンから希望のモデルを選択
   - 🎯 **Large-v3 (高精度)**: 精度重視
   - 🚀 **Large-v3-Turbo (高速)**: 速度重視
   - ⚖️ **Medium (バランス)**: 中程度
   - ⚡ **Base (軽量)**: 軽量・高速
4. **モデル切替** ボタンで即座に変更可能
5. 音声/動画ファイルを選択
6. **出力形式を選択**:
   - 📄 **テキスト**: 普通の文字起こし
   - 🎬 **SRT字幕**: 映像編集ソフト用字幕ファイル
   - 🌐 **WebVTT**: ウェブ動画用字幕ファイル
   - ⏱️ **タイムスタンプ付きテキスト**: 時刻情報付きテキスト
7. **送信**をクリック
8. 字幕形式の場合、自動ダウンロードが開始されます

### ストリーミング処理（長時間音声）
1. **📺 ストリーミング文字起こし**セクションでファイル選択
2. **チャンク設定**:
   - チャンク長: 30秒（推奨）
   - 重複時間: 3秒（推奨）
3. **ストリーミング処理開始**をクリック
4. **リアルタイム進捗**:
   - 🔄 音声分割 → 📝 チャンク処理 → ✅ 完了
   - 処理中も部分結果をリアルタイム表示
5. **❌ キャンセル**で処理中断可能

## 📁 ファイル構成

```
whisper-transcriber/
├─ electron/                   # Electron フロントエンド
│  ├─ src/renderer/index.html  # SRT出力UI付きメイン画面
│  └─ src/renderer/renderer.js # 字幕フォーマット選択ロジック
├─ backend/                    # FastAPI バックエンド
│  ├─ server.py               # /transcribe エンドポイント (format対応)
│  ├─ engine.py               # MLX/faster-whisper 抽象化 (segments対応)
│  └─ subtitles.py            # SRT/VTT/TXT フォーマット生成
└─ scripts/                    # セットアップスクリプト
```

## 🔧 詳細機能

### 字幕フォーマット

| 形式 | 説明 | 用途 |
|------|------|------|
| **SRT** | `1\n00:00:00,000 --> 00:00:05,000\nテキスト\n` | 動画編集ソフト (Premiere, DaVinci) |
| **WebVTT** | `WEBVTT\n\n00:00:00.000 --> 00:00:05.000\nテキスト` | ウェブ動画 (HTML5 video) |
| **タイムスタンプ付きテキスト** | `[00:00:00,000 --> 00:00:05,000] テキスト` | ログ・記録用 |

### API エンドポイント

```bash
# 健康チェック + モデル情報
GET http://127.0.0.1:8765/health
# レスポンス: {"status", "backend", "current_model", "available_models"}

# 文字起こし（字幕対応）
POST http://127.0.0.1:8765/transcribe
- file: 音声ファイル
- language: ja|en|auto (オプション)
- format: text|srt|vtt|txt (デフォルト: text)

# モデル情報取得
GET http://127.0.0.1:8765/models
# レスポンス: {"backend", "current_model", "available_models"}

# モデル切替
POST http://127.0.0.1:8765/models/switch
- model_name: large-v3|large-v3-turbo|medium|base

# GPU情報取得
GET http://127.0.0.1:8765/gpu
# レスポンス: {"platform", "gpus", "recommended_backend", "directml_available", "cuda_available"}

# ストリーミング文字起こし開始
POST http://127.0.0.1:8765/transcribe/streaming
- file: 音声ファイル
- language: ja|en|auto (オプション)
- format: text|srt|vtt|txt (デフォルト: text)
- chunk_duration: チャンク長（秒、デフォルト: 30）
- overlap_duration: 重複時間（秒、デフォルト: 3）

# ストリーミング処理状況取得
GET http://127.0.0.1:8765/transcribe/streaming/{job_id}
# レスポンス: {"status", "progress", "current_chunk", "total_chunks", "full_text"}

# ストリーミング結果取得
GET http://127.0.0.1:8765/transcribe/streaming/{job_id}/result?format=text
# ファイルダウンロード or JSON

# ストリーミング処理キャンセル
DELETE http://127.0.0.1:8765/transcribe/streaming/{job_id}

# サポート形式一覧
GET http://127.0.0.1:8765/formats
```

### 環境変数

```bash
ASR_BACKEND=auto|mlx|ctranslate2|directml  # バックエンド選択
MODEL_ID=large-v3                          # モデル指定
ASR_LANG=ja                                # 言語指定
PORT=8765                                  # ポート番号
```

## 🛠️ 手動テスト

### バックエンドのみ起動

```bash
cd backend
source .venv/bin/activate  # Windows: .venv\Scripts\activate
python server.py
```

### cURLでSRT出力テスト

```bash
curl -X POST http://127.0.0.1:8765/transcribe \
  -F "file=@sample.wav" \
  -F "format=srt" \
  -F "language=ja" \
  -o output.srt
```

## 🔍 トラブルシューティング

| 問題 | 解決方法 |
|------|----------|
| MLX import error | `requirements-mac.txt` がvenvに入っているか確認 |
| CUDA not detected | NVIDIAドライバ更新、`COMPUTE_TYPE=int8_float16` 試行 |
| WebM再生失敗 | FFmpegをシステムにインストール |
| segments not available | モデルが segments を返すか確認 |

## 📦 ビルド

```bash
cd electron
npm run build
```

バックエンドの`.venv`ディレクトリも`extraResources`で同梱されます。

---

## ✅ 実装済み機能

- ✅ **SRT/字幕出力**: 複数字幕形式の自動ダウンロード
- ✅ **Large-v3/Turbo切替UI**: モデル選択ドロップダウン + 動的切替
- ✅ **DirectML対応**: AMD/Intel GPU サポート + GPU情報表示
- ✅ **ストリーミング処理**: 長時間音声の分割処理 + リアルタイム進捗

## 次の実装予定

- 🎨 **テーマ切替**: ダーク/ライトモード
- 🔊 **音声品質向上**: VAD + ノイズリダクション
- 🌐 **WebSocket接続**: よりスムーズなリアルタイム通信