"""mlx-whisper backend for Apple Silicon (runs on the Metal GPU via MLX)."""

import logging
import time
from pathlib import Path

from ...config import Settings
from .audio import decode_to_float32
from .base import FILLER_PRESERVING_PROMPT, TranscriberInfo, Transcript, Word

log = logging.getLogger(__name__)

MLX_REPOS = {
    "small": "mlx-community/whisper-small-mlx",
    "medium": "mlx-community/whisper-medium-mlx",
    "large-v3-turbo": "mlx-community/whisper-large-v3-turbo",
}


class MlxTranscriber:
    def __init__(self, settings: Settings):
        import mlx_whisper

        self._mlx = mlx_whisper
        self.settings = settings
        self.repo = MLX_REPOS[settings.whisper_model_size]
        self.info = TranscriberInfo("mlx", settings.whisper_model_size, "metal", "float16")
        t = time.perf_counter()
        # mlx_whisper loads (and caches) the model on first call, so warm it up now.
        self._mlx.transcribe(decode_silence(), path_or_hf_repo=self.repo, language="en")
        log.info("Loaded mlx-whisper %s in %.1fs", self.repo, time.perf_counter() - t)

    def transcribe(self, audio_path: Path) -> Transcript:
        samples = decode_to_float32(audio_path)
        result = self._mlx.transcribe(
            samples,
            path_or_hf_repo=self.repo,
            language=self.settings.whisper_language,
            word_timestamps=True,
            initial_prompt=FILLER_PRESERVING_PROMPT,
            condition_on_previous_text=False,
        )
        words = [
            Word(w["word"].strip(), round(float(w["start"]), 3), round(float(w["end"]), 3))
            for seg in result.get("segments", [])
            for w in seg.get("words", [])
            if w["word"].strip()
        ]
        return Transcript(result.get("text", "").strip(), words, len(samples) / 16000)


def decode_silence():
    import numpy as np

    return np.zeros(16000, dtype=np.float32)
