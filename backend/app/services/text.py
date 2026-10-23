"""Shared text normalisation for fuzzy matching (duplicate questions, CV grounding, quotes)."""

import re

STOPWORDS = frozenset(
    "a an and the of to in on for with by at from as is are was were be been it its this that "
    "their your my our i we you they he she them me using used use via "
    # question scaffolding, so "Tell me about..." vs "Describe..." doesn't hide a duplicate
    "what how why when where which who did do does can could would should will have has had "
    "tell describe explain walk through give example time situation about any some".split()
)


def norm(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", "", text.lower()).strip()


def stem(word: str) -> str:
    """Crude stemmer: challenges/challenge -> challeng, faced/face -> fac."""
    for suffix in ("ing", "ed", "s"):
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            word = word[: -len(suffix)]
            break
    return word[:-1] if word.endswith("e") and len(word) > 3 else word


def content_words(text: str) -> set[str]:
    return {stem(w) for w in norm(text).split() if w not in STOPWORDS and len(w) > 1}


def overlap(part: str, whole: str) -> float:
    """Share of `part`'s content words that also appear in `whole`."""
    words = content_words(part)
    if not words:
        return 0.0
    return len(words & content_words(whole)) / len(words)
