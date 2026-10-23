# Retake

AI mock interview practice that runs fully locally. Upload your CV, paste a job
description, answer generated questions out loud, and get feedback on each attempt.
No external APIs; nothing leaves your machine after setup.

- Backend: Python 3.10+ / FastAPI / SQLite
- Frontend: React + Vite (TypeScript)
- LLM: [Ollama](https://ollama.com) (`qwen2.5:7b` by default)
- Transcription: faster-whisper (NVIDIA/CPU), mlx-whisper or whisper.cpp (Apple Silicon)

## Requirements

| | Windows / Linux (NVIDIA) | macOS (Apple Silicon) | CPU only |
|---|---|---|---|
| Python | 3.10–3.12 | 3.10–3.12 | 3.10–3.12 |
| Node.js | 20+ | 20+ | 20+ |
| Ollama | latest | latest | latest |
| GPU | NVIDIA driver (see below) | built-in | – |

**NVIDIA Blackwell GPUs (RTX 50-series, e.g. 5060 Ti):** you need a recent NVIDIA
driver that supports **CUDA 12.8 or newer** (`nvidia-smi` shows the supported CUDA
version in its header). Older drivers do not support Blackwell (compute capability
12.0). You don't need to install the CUDA toolkit separately, because the cuBLAS and
cuDNN runtime libraries are installed as pip wheels from `requirements-cuda.txt`. If
CUDA fails to initialise at runtime, the server falls back to CPU (`int8`) and logs a
warning.

## Setup

### 1. Install Ollama and pull the model

```
ollama pull qwen2.5:7b
```

Ollama must be running (`ollama serve`, or the desktop app). To use Ollama on another
machine on your network, set `OLLAMA_HOST` in `.env`.

### 2. Configure

```
cp .env.example .env          # Windows PowerShell: Copy-Item .env.example .env
python scripts/setup_check.py
```

`setup_check.py` reports your GPU, VRAM, RAM, Ollama status and whether CUDA works,
then prints recommended `.env` values for your machine. Run it again after installing
the backend to confirm that CUDA initialises.

### 3. Backend

**Windows (PowerShell)**
```
cd backend
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements-cuda.txt
```

**Linux**
```
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements-cuda.txt
```
On Linux, if CUDA libraries aren't found at runtime, add the pip wheel library
directories to `LD_LIBRARY_PATH`:
```
export LD_LIBRARY_PATH=$(.venv/bin/python -c 'import nvidia.cublas.lib, nvidia.cudnn.lib, os; print(os.path.dirname(nvidia.cublas.lib.__file__) + ":" + os.path.dirname(nvidia.cudnn.lib.__file__))')
```

**macOS (Apple Silicon)**
```
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements-mac.txt
```
Then set `WHISPER_BACKEND=mlx` in `.env` (or `whisper-cpp`).

**CPU only:** install `requirements-cuda.txt` (faster-whisper also runs on CPU) and set
`WHISPER_DEVICE=cpu`, `WHISPER_COMPUTE_TYPE=int8`, `WHISPER_MODEL_SIZE=small`.

### 4. Frontend

```
cd frontend
npm install
```

## Run

```
.\start.ps1        # Windows
./start.sh         # macOS / Linux
```

This starts the backend on http://127.0.0.1:8000 and the UI on http://localhost:5173.
Add `-Reload` / `--reload` for backend auto-reload during development. Press Ctrl+C to
stop both.

## Configuration (`.env`)

| Variable | Default | Notes |
|---|---|---|
| `LLM_MODEL` | `qwen2.5:7b` | any Ollama model that supports JSON schema output |
| `LLM_NUM_CTX` | `8192` | sent on every Ollama call; a warning is logged above 80% use |
| `OLLAMA_HOST` | `http://localhost:11434` | |
| `LLM_KEEP_ALIVE` | `30m` | keeps the model loaded between requests |
| `LLM_TEMPERATURE` | `0.2` | |
| `WHISPER_BACKEND` | `faster-whisper` | `faster-whisper` \| `whisper-cpp` \| `mlx` |
| `WHISPER_MODEL_SIZE` | `large-v3-turbo` | `small` \| `medium` \| `large-v3-turbo` |
| `WHISPER_DEVICE` | `cuda` | `cuda` \| `cpu` |
| `WHISPER_COMPUTE_TYPE` | `float16` | `float16` \| `int8` |
| `AUDIO_RETENTION_DAYS` | `7` | sessions (CV, audio, transcripts) older than this are deleted |

## Privacy

All data stays in `backend/data/` (SQLite database and uploads). CV contents are never
logged. Sessions older than `AUDIO_RETENTION_DAYS` are deleted automatically.

## Tests

```
cd backend
.venv/Scripts/python -m pytest      # Windows
.venv/bin/python -m pytest          # macOS / Linux
```
