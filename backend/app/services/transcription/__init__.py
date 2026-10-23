"""Transcription service. The model is loaded once at startup via `load_transcriber()`."""

import logging
import threading

from ...config import Settings
from .base import Transcript, TranscriberInfo, TranscriptionService, Word

__all__ = ["Transcript", "TranscriberInfo", "TranscriptionService", "Word", "load_transcriber",
           "get_transcriber", "transcriber_status", "TranscriberUnavailable"]

log = logging.getLogger(__name__)


class TranscriberUnavailable(RuntimeError):
    pass


_transcriber: TranscriptionService | None = None
_load_error: str | None = None
_loading = threading.Event()


def _create(settings: Settings) -> TranscriptionService:
    if settings.whisper_backend == "faster-whisper":
        from .faster_whisper_backend import FasterWhisperTranscriber
        return FasterWhisperTranscriber(settings)
    if settings.whisper_backend == "mlx":
        from .mlx_backend import MlxTranscriber
        return MlxTranscriber(settings)
    from .whisper_cpp_backend import WhisperCppTranscriber
    return WhisperCppTranscriber(settings)


def load_transcriber(settings: Settings) -> None:
    global _transcriber, _load_error
    _loading.set()
    try:
        _transcriber = _create(settings)
        _load_error = None
    except ImportError as exc:
        req = "requirements-mac.txt" if settings.whisper_backend in ("mlx", "whisper-cpp") else "requirements-cuda.txt"
        _load_error = (f"WHISPER_BACKEND={settings.whisper_backend} is not installed ({exc.name}). "
                       f"Run: pip install -r backend/{req}")
        log.error(_load_error)
    except Exception as exc:
        _load_error = f"Could not load Whisper ({type(exc).__name__}: {exc})"
        log.exception("Whisper load failed")
    finally:
        _loading.clear()


def get_transcriber() -> TranscriptionService:
    if _transcriber is None:
        raise TranscriberUnavailable(_load_error or "Whisper is still loading. Try again in a moment.")
    return _transcriber


def transcriber_status() -> dict:
    if _transcriber is not None:
        i = _transcriber.info
        return {"loaded": True, "loading": False, "backend": i.backend, "model_size": i.model_size,
                "device": i.device, "compute_type": i.compute_type, "warnings": i.warnings, "error": None}
    return {"loaded": False, "loading": _loading.is_set(), "error": _load_error}
