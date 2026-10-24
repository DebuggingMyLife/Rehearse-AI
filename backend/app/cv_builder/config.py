"""Wires RehearseAI's .env (app.config.Settings) into the CV Builder's own LLM factory.

The A1 code (agent.build_llm, LocalLLM, GroqLLM) reads its own variable names: LLM_BACKEND,
LOCAL_LLM_MODEL, LOCAL_LLM_BASE_URL, LOCAL_LLM_NUM_CTX, GROQ_MODEL, GROQ_API_KEY. This maps the
RehearseAI names onto them, so the API, the CLI and the A1 test scripts all use the same model
without changing the A1 code. setdefault: a variable already set in the shell still wins.
"""

import os

from ..config import Settings, get_settings


def apply_settings_to_env(settings: Settings | None = None) -> None:
    s = settings or get_settings()
    os.environ.setdefault("LLM_BACKEND", s.cv_builder_llm_backend)
    os.environ.setdefault("LOCAL_LLM_MODEL", s.cv_builder_llm_model)
    os.environ.setdefault("LOCAL_LLM_BASE_URL", s.ollama_host)
    os.environ.setdefault("LOCAL_LLM_NUM_CTX", str(s.local_llm_num_ctx))
    os.environ.setdefault("GROQ_MODEL", s.groq_model)
    if s.groq_api_key:
        os.environ.setdefault("GROQ_API_KEY", s.groq_api_key)
