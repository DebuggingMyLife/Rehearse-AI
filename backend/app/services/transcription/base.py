from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Protocol

# Whisper tends to clean up disfluencies ("um", "uh") unless the prompt contains them.
# Delivery metrics depend on keeping them, so every backend uses this initial prompt.
FILLER_PRESERVING_PROMPT = "Umm, let me think like, hmm... Okay, here's what I'm, like, thinking. Uh, so, you know,"


@dataclass
class Word:
    w: str
    start: float
    end: float


@dataclass
class Transcript:
    text: str
    words: list[Word]
    duration_s: float

    def words_json(self) -> list[dict]:
        return [asdict(w) for w in self.words]


@dataclass
class TranscriberInfo:
    backend: str
    model_size: str
    device: str
    compute_type: str
    warnings: list[str] = field(default_factory=list)


class TranscriptionService(Protocol):
    info: TranscriberInfo

    def transcribe(self, audio_path: Path) -> Transcript: ...
