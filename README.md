# RehearseAI

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

**First start downloads the Whisper model** (about 1.6 GB for `large-v3-turbo`) from
Hugging Face, so it needs internet once; after that everything runs offline. Whisper
loads in the background, and the banner shows "loading…" until it's ready. On an NVIDIA
GPU the very first transcription compiles CUDA kernels (about 25 s on a Blackwell card);
the server does this during startup and the result is cached for later runs.
Add `-Reload` / `--reload` for backend auto-reload during development. Press Ctrl+C to
stop both.

## Using it

1. **Upload** your CV (PDF or DOCX) and paste the job description. Check the extracted CV
   text and fix anything that parsed badly.
2. **Questions**: 5 are generated (behavioural, technical, CV-specific; easy to hard).
   "Generate more" adds more, optionally of one type or difficulty, without repeats.
3. **Answer** a question out loud: record, replay, re-record, submit. You get the
   transcript and delivery metrics in about a second, the score in about 7 seconds, and
   written feedback streams in after that (timings on an RTX 5060 Ti with `qwen2.5:7b`).
4. **Try again** as often as you like; each retry is compared with your previous attempt.
5. **End session & summarise** for recurring strengths and weaknesses and your top
   priorities, then **Export PDF** for a report of your best attempts.

## How the evaluation works

Each answer is scored in two LLM calls: (1) rubric coverage and a 1-5 score, (2) written
feedback, streamed to the page as it's generated. A 7B model makes mistakes, so Python
checks its output: quotes are verified against the transcript (claims backed by words you
never said don't count), the score is kept consistent with the rubric coverage, and
sentences in the example answer that introduce names or numbers absent from your CV and
transcript are removed. Delivery metrics (pace, filler words, pauses over 2 s) are measured
from the word timestamps, not judged by the LLM. Prompts live in `backend/app/prompts/`.

## Evaluator test set

`backend/evals/samples.json` holds sample answers (strong, weak, off-topic, empty) with
expected score bands. Run them against your configured model to check score consistency,
or to compare models and settings:

```
cd backend
.venv/Scripts/python -m evals.run_evals            # Windows; 3 runs per sample
.venv/bin/python -m evals.run_evals --feedback     # macOS/Linux; also time call 2
.venv/bin/python -m evals.run_evals --model llama3.1:8b --runs 5
```

Each run prints the scores per sample, how often they fell in the expected band, the spread
across runs and the call timings, and saves a JSON report to `backend/evals/results/`.
Reference result for `qwen2.5:7b` (RTX 5060 Ti): 21/21 runs in band, 6 of 7 samples scored
identically on every run, scoring about 2-4.5 s per answer.

## Latency logging

Every attempt logs one line with the duration of each step, for example:

```
Attempt 42 [complete] timings | upload 4ms | queue 2ms | transcription 770ms | metrics 0ms |
llm_score 5725ms | llm_feedback 6331ms | score_ready 7272ms | first_feedback 10666ms | total 13960ms |
whisper large-v3-turbo cuda/float16 | llm qwen2.5:7b
```

The same numbers are stored on the attempt and shown under "Processing time" on the
feedback screen, so hardware setups can be compared.

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

All data stays in `backend/data/` (SQLite database and uploads). CV contents and
transcripts are never logged. Sessions older than `AUDIO_RETENTION_DAYS` (CV file, audio,
transcripts, feedback) are deleted automatically, at startup and every 6 hours, along with
any upload files no longer referenced by the database. Delete `backend/data/` to remove
everything immediately.

## Tests

```
cd backend
.venv/Scripts/python -m pytest      # Windows
.venv/bin/python -m pytest          # macOS / Linux
```
