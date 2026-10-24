from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "backend"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env", env_file_encoding="utf-8", extra="ignore"
    )

    llm_model: str = "qwen2.5:7b"
    llm_num_ctx: int = 8192
    ollama_host: str = "http://localhost:11434"
    llm_keep_alive: str = "30m"
    llm_temperature: float = 0.2

    # CV Builder (the Assignment 1 core in app/cv_builder). Its prompts and token budgets were
    # tuned for gpt-oss:20b, so it keeps its own model rather than sharing LLM_MODEL.
    cv_builder_llm_backend: Literal["local", "groq"] = "local"
    cv_builder_llm_model: str = "gpt-oss:20b"
    # Ollama's 4096 default is too small for the CV Builder's ~4k-token system prompts.
    local_llm_num_ctx: int = 16384
    groq_api_key: str | None = None  # only for CV_BUILDER_LLM_BACKEND=groq; never log it
    groq_model: str = "openai/gpt-oss-20b"

    whisper_backend: Literal["faster-whisper", "whisper-cpp", "mlx"] = "faster-whisper"
    whisper_model_size: Literal["small", "medium", "large-v3-turbo"] = "large-v3-turbo"
    whisper_device: Literal["cuda", "cpu"] = "cuda"
    whisper_compute_type: Literal["float16", "int8"] = "float16"
    whisper_language: str = "en"

    audio_retention_days: int = 7

    data_dir: Path = BACKEND_ROOT / "data"

    @property
    def db_url(self) -> str:
        return f"sqlite:///{(self.data_dir / 'rehearseai.db').as_posix()}"

    @property
    def cv_dir(self) -> Path:
        return self.data_dir / "uploads" / "cv"

    @property
    def audio_dir(self) -> Path:
        return self.data_dir / "uploads" / "audio"

    @property
    def cv_build_dir(self) -> Path:
        return self.data_dir / "uploads" / "cv_builds"


@lru_cache
def get_settings() -> Settings:
    return Settings()
