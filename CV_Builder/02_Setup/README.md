# Setup & Running

## 1. Install dependencies (Python 3.11+)

From the project root:
```
pip install -r 02_Setup/requirements.txt
```

## 2. Choose an LLM backend and provide credentials

The agent talks to an LLM through a single `LLMClient` interface (`agent.py`) with two
implementations, picked by `LLM_BACKEND` in `.env`:

- **`groq`** (default) — GROQ's cloud API. Requires a key.
- **`local`** — the same model (`gpt-oss:20b`) run locally via [Ollama](https://ollama.com)
  (`ollama pull gpt-oss:20b`, then `ollama serve`). No API key or internet needed, and no
  rate limit either, since it's your own hardware.

Create `02_Setup/.env` (untracked — never commit it):
```
LLM_BACKEND=groq

GROQ_API_KEY=your-real-key-here
GROQ_MODEL=openai/gpt-oss-20b

# Only read when LLM_BACKEND=local
LOCAL_LLM_MODEL=gpt-oss:20b
LOCAL_LLM_BASE_URL=http://localhost:11434
LOCAL_LLM_NUM_CTX=16384
```
`config.example` in this folder documents every setting, including why `LOCAL_LLM_NUM_CTX`
needs to be raised above Ollama's own default (4096 is too small for this project's system
prompts and silently produces empty output) — copy the values you need, but keep the real
key only in `.env`. Switching backends is just changing `LLM_BACKEND` and restarting; no
code changes are needed either way.

## 3. Run the complete profile-to-PDF flow (the main entry point)

From `01_System/source_code/`:
```
python cv_builder_cli.py
```
This prompts for a free-text introduction, extracts what it can immediately, and asks
follow-up questions in two phases: first for anything still missing among the required
fields and education (name, degree, institution, year, at least one skill, target roles),
then — once that's done — a one-at-a-time review of any project still missing dates or a
concrete outcome (measurable results are never asked for, only captured if you mention
them unprompted). A stated fact is trusted the moment you give it; the whole profile is
confirmed once, together, at the end — not after every individual answer. From there it
shows your top-3 matched jobs from `data/jobs.jsonl`, lets you pick one, checks that job's
own stated requirements against your profile, generates a tailored CV, lets you edit it
field-by-field, and exports a PDF. Run with `--help` to see the flags (`--intro`,
`--intro-file`, `--replies-json`, `--review-replies-json`, `--job`, `--edits-json`,
`--output`, `--step-cap`, `--review-step-cap`, `--llm-backend`) that make it scriptable
non-interactively instead of prompting.

## 4. Run the Streamlit GUI (browser version of the same flow)

From `01_System/source_code/`:
```
streamlit run cv_builder_gui.py
```
This opens the same introduction -> follow-ups -> project review -> job matches -> job
requirement check -> CV generation -> edit -> PDF export flow in your browser (defaults to
`http://localhost:8501`), with an inline PDF preview and a sidebar that supports multiple
independent conversations at once. Requires the same LLM backend setup as step 2.

## 5. Other scripts

- `export_cv.py` — runnable from `01_System/source_code/`. CV + PDF export starting
  from an already-confirmed profile in `data/student_profiles.jsonl`, skipping the
  conversation.
- `01_System/source_code/tests/` — the test scripts, each independently runnable
  (e.g. `python tests/run_agent_tests.py` from `01_System/source_code/`) and each
  writing its evidence into `03_Evidence/`:
  - `run_agent_tests.py`, `run_retrieval_tests.py`, `run_prompt_comparison_test.py` —
    the per-feature tests covering the agent trace, RAG retrieval and the prompt
    before/after comparison.
  - `run_five_profile_tests.py`, `run_two_job_comparison.py`, `run_cross_user_test.py` —
    the required full-system test suite (five varied profiles, one profile against two
    jobs, and a two-user isolation check), writing directly to the required
    `04_System_Tests/five_profile_results.md`, `two_job_comparison.md` and
    `cross_user_test.md` filenames.

  A number of additional feature/regression scripts written during development
  (job-requirement follow-ups, the session sidebar, the CV style spec, an
  achievement-bullet/date-alignment fix, and a final combined re-run of the three
  full-system tests) were removed from this submission: they exercised real bugs
  and extra features along the way, but weren't required deliverables and their
  evidence files fell outside the assignment's required `03_Evidence` structure.
  That work is still recorded honestly in `03_Evidence/01_Prompts/prompt_record.md`.

See `01_System/architecture.md` (and `01_System/architecture_diagram.png`) for how these
pieces fit together, and `03_Evidence/01_Prompts/prompt_record.md` for the full build
history, including every bug found and fixed along the way.
