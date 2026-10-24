# RehearseAI

Build a CV for a job, then rehearse the interview for it, all on your own machine. One app,
with two ways in from the landing page:

1. **Build a CV**: describe yourself in your own words. The CV Builder asks follow-up
   questions, matches you to jobs, checks the chosen job's requirements against your
   profile, and writes a tailored CV (with a PDF) using only facts you've confirmed. From
   there, **Practise the interview for this job** goes straight to a mock interview.
2. **Start practising**: upload a CV (or pick one you built), add the job description,
   answer generated questions out loud, and get feedback on each attempt.

The CV Builder is the Assignment 1 system (`CV_Builder/` holds its original report and
evidence); RehearseAI extends it with the spoken mock interview. Sessions started from a
built CV know which skills matched the job and which requirements the CV doesn't show, and
the interview asks about those gaps.

No external APIs by default; nothing leaves your machine after setup.

- Backend: Python 3.10+ / FastAPI / SQLite
- Frontend: React + Vite (TypeScript)
- LLMs: [Ollama](https://ollama.com): `qwen2.5:7b` for the interview, `gpt-oss:20b` for the
  CV Builder (Groq is an optional cloud fallback for the CV Builder)
- Job matching: sentence-transformers (`all-MiniLM-L6-v2`)
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

### 1. Install Ollama and pull the models

```
ollama pull qwen2.5:7b      # interview questions and feedback
ollama pull gpt-oss:20b     # CV Builder
```

Ollama must be running (`ollama serve`, or the desktop app). To use Ollama on another
machine on your network, set `OLLAMA_HOST` in `.env`.

The CV Builder keeps `gpt-oss:20b` because its prompts and token budgets were tuned for
that model. It's a reasoning model, so each CV Builder step takes roughly 10 to 60 seconds.

**VRAM:** `gpt-oss:20b` (about 13 GB) and `qwen2.5:7b` (about 5 GB) don't both fit on most
GPUs, so they take turns: Ollama unloads one to load the other. `LLM_KEEP_ALIVE` keeps the
interview model loaded between requests, so the first CV Builder step after practising (and
the first question generation after building a CV) is slower while the models swap. With
enough VRAM for both, they stay loaded side by side. If `gpt-oss:20b` doesn't fit at all,
set `CV_BUILDER_LLM_BACKEND=groq` and add a `GROQ_API_KEY` (optional fallback; this sends
CV Builder conversations to Groq's cloud API).

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
The requirements include the CV Builder's `sentence-transformers`, which **pulls in
PyTorch** (a large install, a few hundred MB for the CPU build), and it downloads the
`all-MiniLM-L6-v2` embedding model (about 90 MB) from Hugging Face the first time you match
jobs. Both run on the CPU.

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

The header links to **Build a CV** and **Practise** from every page.

### Build a CV

1. **Introduce yourself**: education, skills, projects or experience, target roles.
2. **Follow-ups**: the CV Builder asks for anything still missing in one combined question,
   then reviews your projects one detail at a time (dates, what you built). If the
   conversation runs too long, you go straight to the form to fill in the rest.
3. **Confirm** the whole profile on one editable form.
4. **Pick a job** from your top 3 matches (title, location and the most relevant line).
5. **Requirement check**: if the job asks for things your profile doesn't show, you're asked
   about them once. Anything you don't confirm stays off the CV.
6. **Your CV**: see matched skills and missing requirements, edit the text, preview and
   download the PDF, or press **Practise the interview for this job**. That creates a
   practice session from this CV and job directly, with nothing to download or upload.

Builds are saved, so a refresh or restart loses nothing. **Edit profile** on the job and CV pages takes you back to the form (you then pick the
job again and the CV is regenerated).

### Practise

1. **Choose a CV**: upload one (PDF or DOCX) and paste the job description, or pick **Use a
   CV I built**, which fills in the job description from that build (you can still edit it).
   Check the extracted CV text and fix anything that parsed badly.
2. **Questions**: 5 are generated (behavioural, technical, CV-specific; easy to hard).
   "Generate more" adds more, optionally of one type or difficulty, without repeats. For a
   CV from the CV Builder, the page shows the job it was built for and its missing
   requirements; each batch includes a question on how you'd handle one of those gaps, and
   CV-specific questions favour projects that use your matched skills.
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
| `CV_BUILDER_LLM_BACKEND` | `local` | `local` (Ollama) \| `groq` |
| `CV_BUILDER_LLM_MODEL` | `gpt-oss:20b` | Ollama model for the CV Builder; its prompts were tuned for this one |
| `LOCAL_LLM_NUM_CTX` | `16384` | CV Builder context window; Ollama's 4096 default returns empty replies for its ~4k-token prompts |
| `GROQ_API_KEY` | (unset) | only for `CV_BUILDER_LLM_BACKEND=groq`; never commit it |
| `GROQ_MODEL` | `openai/gpt-oss-20b` | Groq model for the CV Builder |
| `WHISPER_BACKEND` | `faster-whisper` | `faster-whisper` \| `whisper-cpp` \| `mlx` |
| `WHISPER_MODEL_SIZE` | `large-v3-turbo` | `small` \| `medium` \| `large-v3-turbo` |
| `WHISPER_DEVICE` | `cuda` | `cuda` \| `cpu` |
| `WHISPER_COMPUTE_TYPE` | `float16` | `float16` \| `int8` |
| `AUDIO_RETENTION_DAYS` | `7` | sessions (CV, audio, transcripts) and CV builds older than this are deleted |

## Privacy

All data stays in `backend/data/` (SQLite database and uploads). CV contents, CV Builder
conversations and profiles, and transcripts are never logged. Sessions (CV file, audio,
transcripts, feedback) and CV builds (conversation, profile, generated CV and PDF) older than
`AUDIO_RETENTION_DAYS` are deleted automatically, at startup and every 6 hours, along with
any upload files no longer referenced by the database. Delete `backend/data/` to remove
everything immediately. With `CV_BUILDER_LLM_BACKEND=groq`, CV Builder conversations are
sent to Groq.

## Tests

```
cd backend
.venv/Scripts/python -m pytest      # Windows
.venv/bin/python -m pytest          # macOS / Linux
```

The pytest suite uses fake LLMs and a stubbed embedding model, so it needs neither Ollama
nor the embedding model download.

### CV Builder CLI and Assignment 1 scripts

The Assignment 1 command-line flow and test scripts still run, from `backend/`. They call
the real CV Builder model and use the same `.env` settings as the app:

```
cd backend
.venv/Scripts/python -m app.cv_builder.cv_builder_cli --help
.venv/Scripts/python -m app.cv_builder.tests.run_agent_tests
```

The test scripts write their evidence into `CV_Builder/03_Evidence/`, the Assignment 1
record.

## Project structure

```
backend/
  app/
    cv_builder/         Assignment 1 core: profile agent, job retrieval, CV generation, PDF
      data/             jobs.jsonl (9 postings) and the A1 synthetic profiles
      tests/            A1 test scripts (write to CV_Builder/03_Evidence/)
    routers/            API: sessions, questions, attempts, cv_builds, health
    services/           interview pipeline, question generation, cv_builds (CV Builder state)
    prompts/            interview prompt templates
    models.py, db.py    SQLite tables (sessions, questions, attempts, cv_builds)
  tests/                pytest suite
  evals/                evaluator test set
frontend/src/
  pages/                landing, CV Builder (BuildIntroPage, BuildPage), setup, questions, ...
  components/cvbuilder/ CV Builder steps: follow-up chat, profile form, jobs, CV editor
CV_Builder/             Assignment 1 report, architecture and evidence (source moved to backend/)
scripts/setup_check.py  hardware and configuration check
```
