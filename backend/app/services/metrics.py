"""Delivery metrics, computed in Python from the transcript and word timestamps (not by the LLM)."""

import re
from collections import Counter
from dataclasses import dataclass, field

from .transcription import Transcript

LONG_PAUSE_S = 2.0

# Always fillers, whatever the context.
HESITATIONS = {"um", "umm", "uhm", "uh", "uhh", "er", "erm", "ah", "hmm", "mm", "mhm"}
HESITATION_SPELLINGS = {"umm": "um", "uhm": "um", "uhh": "uh", "erm": "er", "mhm": "mm"}
# Fillers only when set off by commas or ending a sentence ("it was, like, slow" but not
# "I'd like to" or "looks like Kafka"). Whisper reliably punctuates spoken fillers this way.
COMMA_FILLERS = ["you know", "i mean", "sort of", "kind of", "like", "basically", "literally"]

_TOKEN_RE = re.compile(r"[a-z']+|[,.!?;:]")


@dataclass
class DeliveryMetrics:
    word_count: int
    wpm: float
    speaking_time_s: float
    filler_count: int
    filler_breakdown: dict[str, int]
    long_pause_count: int
    longest_pause_s: float
    pauses: list[dict] = field(default_factory=list)  # [{at, duration}]

    def delivery_json(self) -> dict:
        return {
            "word_count": self.word_count,
            "speaking_time_s": self.speaking_time_s,
            "longest_pause_s": self.longest_pause_s,
            "pauses": self.pauses,
        }


def count_fillers(text: str) -> Counter:
    tokens = _TOKEN_RE.findall(text.lower())
    counts: Counter = Counter()
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok in HESITATIONS:
            counts[HESITATION_SPELLINGS.get(tok, tok)] += 1
            i += 1
            continue
        matched = False
        for phrase in COMMA_FILLERS:
            parts = phrase.split()
            n = len(parts)
            if tokens[i:i + n] != parts:
                continue
            before = tokens[i - 1] if i > 0 else "."
            after = tokens[i + n] if i + n < len(tokens) else "."
            if after in {",", ".", "!", "?"} or (before == "," and after == ",") or \
                    (before in {",", ".", "?", "!"} and after in HESITATIONS):
                counts[phrase] += 1
                i += n
                matched = True
                break
        if not matched:
            i += 1
    return counts


def compute_metrics(transcript: Transcript) -> DeliveryMetrics:
    words = transcript.words
    word_count = len([w for w in words if re.search(r"[A-Za-z0-9]", w.w)])

    # Rate over the speaking span, so silence before the first and after the last word
    # (thinking time, fumbling for the stop button) doesn't drag WPM down.
    if words:
        span = max(words[-1].end - words[0].start, 0.0)
    else:
        span = 0.0
    if span < 1.0:
        span = transcript.duration_s
    wpm = round(word_count / (span / 60), 1) if span > 0 else 0.0

    pauses = []
    for prev, nxt in zip(words, words[1:]):
        gap = nxt.start - prev.end
        if gap > LONG_PAUSE_S:
            pauses.append({"at": round(prev.end, 2), "duration": round(gap, 2)})
    gaps = [nxt.start - prev.end for prev, nxt in zip(words, words[1:])]

    fillers = count_fillers(transcript.text)
    return DeliveryMetrics(
        word_count=word_count,
        wpm=wpm,
        speaking_time_s=round(span, 2),
        filler_count=sum(fillers.values()),
        filler_breakdown=dict(fillers.most_common()),
        long_pause_count=len(pauses),
        longest_pause_s=round(max(gaps), 2) if gaps else 0.0,
        pauses=pauses,
    )
