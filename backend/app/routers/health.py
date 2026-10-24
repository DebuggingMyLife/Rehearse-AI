from fastapi import APIRouter
from starlette.concurrency import run_in_threadpool

from ..config import get_settings
from ..services.llm import check_cv_builder_llm, check_ollama
from ..services.transcription import transcriber_status

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
async def health() -> dict:
    settings = get_settings()
    ollama = await run_in_threadpool(check_ollama, settings)
    cv_builder = await run_in_threadpool(check_cv_builder_llm, settings)
    return {
        # Interview practice needs only Ollama + Whisper; the CV Builder reports separately.
        "ok": ollama.ok,
        "ollama": ollama.to_dict(),
        "cv_builder": cv_builder.to_dict(),
        "whisper": {
            "backend": settings.whisper_backend,
            "model_size": settings.whisper_model_size,
            "device": settings.whisper_device,
            "compute_type": settings.whisper_compute_type,
            # Actual device/compute after any CUDA->CPU fallback, plus load state
            **transcriber_status(),
        },
        "config": {
            "llm_num_ctx": settings.llm_num_ctx,
            "local_llm_num_ctx": settings.local_llm_num_ctx,
            "audio_retention_days": settings.audio_retention_days,
        },
    }
