import glob
import logging
import os
import sys
import time
from pathlib import Path

import numpy as np

from ...config import Settings
from .base import FILLER_PRESERVING_PROMPT, TranscriberInfo, Transcript, Word

log = logging.getLogger(__name__)


def _add_nvidia_dll_dirs() -> None:
    """On Windows, CTranslate2 loads cuBLAS/cuDNN by name; the pip `nvidia-*` wheels put
    them in site-packages/nvidia/*/bin, which isn't on the DLL search path."""
    if sys.platform != "win32":
        return
    for d in glob.glob(os.path.join(sys.prefix, "Lib", "site-packages", "nvidia", "*", "bin")):
        os.add_dll_directory(d)
        os.environ["PATH"] = d + os.pathsep + os.environ.get("PATH", "")


class FasterWhisperTranscriber:
    def __init__(self, settings: Settings):
        _add_nvidia_dll_dirs()
        from faster_whisper import WhisperModel

        self._WhisperModel = WhisperModel
        self.settings = settings
        self.info = TranscriberInfo("faster-whisper", settings.whisper_model_size,
                                    settings.whisper_device, settings.whisper_compute_type)
        try:
            self._load(settings.whisper_device, settings.whisper_compute_type)
            self._warm_up()
        except Exception as exc:
            if settings.whisper_device != "cuda":
                raise
            msg = (f"CUDA initialisation failed for faster-whisper ({type(exc).__name__}: {exc}). "
                   "Falling back to WHISPER_DEVICE=cpu, WHISPER_COMPUTE_TYPE=int8; transcription will be slower.")
            log.warning(msg)
            self.info.warnings.append(msg)
            self._load("cpu", "int8")
            self._warm_up()

    def _load(self, device: str, compute_type: str) -> None:
        t = time.perf_counter()
        self.model = self._WhisperModel(self.settings.whisper_model_size, device=device, compute_type=compute_type)
        self.info.device, self.info.compute_type = device, compute_type
        log.info("Loaded Whisper %s on %s/%s in %.1fs", self.settings.whisper_model_size, device, compute_type,
                 time.perf_counter() - t)

    def _warm_up(self) -> None:
        # The first CUDA inference compiles kernels (~25 s on a fresh Blackwell setup) and
        # surfaces missing-DLL errors. Do it now, not on the user's first answer.
        t = time.perf_counter()
        noise = (np.random.default_rng(0).standard_normal(16000 * 2) * 0.01).astype(np.float32)
        segments, _ = self.model.transcribe(noise, language="en", word_timestamps=True)
        list(segments)
        log.info("Whisper warm-up done in %.1fs", time.perf_counter() - t)

    def transcribe(self, audio_path: Path) -> Transcript:
        segments, info = self.model.transcribe(
            str(audio_path),
            language=self.settings.whisper_language,
            word_timestamps=True,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 500},
            initial_prompt=FILLER_PRESERVING_PROMPT,
            condition_on_previous_text=False,  # reduces repetition loops on long answers
        )
        words: list[Word] = []
        texts: list[str] = []
        for seg in segments:
            texts.append(seg.text.strip())
            for w in seg.words or []:
                words.append(Word(w.word.strip(), round(float(w.start), 3), round(float(w.end), 3)))
        return Transcript(" ".join(t for t in texts if t), [w for w in words if w.w], float(info.duration))
