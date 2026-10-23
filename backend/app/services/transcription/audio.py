"""Decode browser audio (webm/ogg/m4a/wav) to 16 kHz mono WAV with PyAV, for backends
that only accept WAV (whisper.cpp)."""

import tempfile
import wave
from pathlib import Path

import numpy as np


def decode_to_float32(path: Path, sample_rate: int = 16000) -> np.ndarray:
    import av

    with av.open(str(path)) as container:
        resampler = av.AudioResampler(format="s16", layout="mono", rate=sample_rate)
        chunks = []
        for frame in container.decode(audio=0):
            for out in resampler.resample(frame):
                chunks.append(out.to_ndarray().reshape(-1))
        for out in resampler.resample(None):
            chunks.append(out.to_ndarray().reshape(-1))
    if not chunks:
        return np.zeros(0, dtype=np.float32)
    return (np.concatenate(chunks).astype(np.float32) / 32768.0)


def to_wav16k(path: Path) -> Path:
    samples = decode_to_float32(path)
    out = Path(tempfile.mkstemp(suffix=".wav")[1])
    with wave.open(str(out), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes((np.clip(samples, -1, 1) * 32767).astype("<i2").tobytes())
    return out
