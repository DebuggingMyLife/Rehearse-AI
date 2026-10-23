"""whisper.cpp backend via pywhispercpp (CPU, or Metal on Apple Silicon)."""

import logging
import time
from pathlib import Path

from ...config import Settings
from .audio import to_wav16k
from .base import FILLER_PRESERVING_PROMPT, TranscriberInfo, Transcript, Word

log = logging.getLogger(__name__)


class WhisperCppTranscriber:
    def __init__(self, settings: Settings):
        from pywhispercpp.model import Model

        self.settings = settings
        t = time.perf_counter()
        # max_len=1 + split_on_word gives one segment per word, i.e. word-level timestamps.
        self.model = Model(
            settings.whisper_model_size,
            print_progress=False,
            print_realtime=False,
            language=settings.whisper_language,
            initial_prompt=FILLER_PRESERVING_PROMPT,
            token_timestamps=True,
            max_len=1,
            split_on_word=True,
        )
        self.info = TranscriberInfo("whisper-cpp", settings.whisper_model_size, "cpu/metal", "ggml")
        log.info("Loaded whisper.cpp %s in %.1fs", settings.whisper_model_size, time.perf_counter() - t)

    def transcribe(self, audio_path: Path) -> Transcript:
        wav = to_wav16k(audio_path)
        try:
            segments = self.model.transcribe(str(wav))
        finally:
            wav.unlink(missing_ok=True)
        # pywhispercpp times are in centiseconds
        words = [Word(s.text.strip(), s.t0 / 100, s.t1 / 100) for s in segments if s.text.strip()]
        text = " ".join(w.w for w in words)
        duration = words[-1].end if words else 0.0
        return Transcript(text, words, duration)
