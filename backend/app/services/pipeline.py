"""Attempt processing: transcribe -> check length -> delivery metrics -> two-call evaluation.

Runs on the worker thread. Each step's duration is stored in Attempt.timings and logged
in one line per attempt, so latency bottlenecks are visible and hardware can be compared.
Never log transcript text: it is the candidate's own words.
"""

import logging
import time
from datetime import datetime, timezone
from pathlib import Path

from ..config import get_settings
from ..db import SessionLocal
from ..events import bus
from ..models import Attempt, AttemptStatus
from ..schemas.api import AttemptOut, as_utc
from .evaluation import build_context, previous_feedback, score_answer, write_feedback
from .llm import LLMUnavailable, get_llm
from .metrics import compute_metrics
from .transcription import TranscriberUnavailable, get_transcriber

log = logging.getLogger(__name__)

MIN_WORDS = 10
TIMING_KEYS = ["upload_ms", "queue_ms", "transcription_ms", "metrics_ms", "llm_score_ms", "llm_feedback_ms",
               "score_ready_ms", "first_feedback_ms", "total_ms"]


def _ms(start: float) -> int:
    return int((time.perf_counter() - start) * 1000)


def _set_status(db, attempt: Attempt, status: AttemptStatus) -> None:
    attempt.status = status
    db.commit()
    bus.publish(attempt.id, {"type": "status", "status": status.value})


def _finish(db, attempt: Attempt, timings: dict) -> None:
    timings["total_ms"] = int((datetime.now(timezone.utc) - as_utc(attempt.created_at)).total_seconds() * 1000)
    attempt.timings = timings
    db.commit()
    db.refresh(attempt)
    log_timings(attempt)
    bus.publish(attempt.id, {"type": "done", "attempt": AttemptOut.from_model(attempt).model_dump(mode="json")})


def log_timings(attempt: Attempt) -> None:
    t = attempt.timings or {}
    steps = " | ".join(f"{k.removesuffix('_ms')} {t[k]}ms" if k in t else f"{k.removesuffix('_ms')} -"
                       for k in TIMING_KEYS)
    log.info("Attempt %d [%s] timings | %s | whisper %s %s | llm %s", attempt.id, attempt.status.value, steps,
             t.get("whisper_model", "?"), t.get("whisper_device", "?"), t.get("llm_model", "?"))


def _since_submit_ms(attempt: Attempt) -> int:
    return int((datetime.now(timezone.utc) - as_utc(attempt.created_at)).total_seconds() * 1000)


def _evaluate(db, attempt: Attempt, timings: dict) -> None:
    """Call 1 (score) then call 2 (feedback, streamed field by field). An LLM failure leaves
    the transcript and metrics intact and records a "feedback unavailable" message."""
    llm = get_llm()
    question = attempt.question
    ctx = build_context(question, attempt.transcript or "")
    label = str(attempt.id)

    start = time.perf_counter()
    try:
        scoring, _ = score_answer(llm, ctx, label)
    except LLMUnavailable as exc:
        timings["llm_score_ms"] = _ms(start)
        log.error("Attempt %d scoring unavailable: %s", attempt.id, exc)
        attempt.error = "Feedback unavailable: the local model didn't return a valid evaluation. Please try again."
        return
    timings["llm_score_ms"] = _ms(start)
    timings["score_ready_ms"] = _since_submit_ms(attempt)
    attempt.scoring_json = scoring
    attempt.score = scoring["score"]
    db.commit()
    bus.publish(attempt.id, {"type": "score", "scoring": scoring})

    def on_field(name: str, value) -> None:
        timings.setdefault("first_feedback_ms", _since_submit_ms(attempt))
        bus.publish(attempt.id, {"type": "feedback_field", "field": name, "value": value})

    start = time.perf_counter()
    try:
        feedback, _ = write_feedback(llm, ctx, scoring, previous_feedback(db, attempt), label, on_field)
        attempt.feedback_json = feedback
    except LLMUnavailable as exc:
        log.error("Attempt %d feedback unavailable: %s", attempt.id, exc)
        attempt.error = "Detailed feedback unavailable: the local model didn't return valid feedback. Please try again."
    timings["llm_feedback_ms"] = _ms(start)


def process_attempt(attempt_id: int) -> None:
    with SessionLocal() as db:
        attempt = db.get(Attempt, attempt_id)
        if attempt is None or attempt.status not in (AttemptStatus.uploaded, AttemptStatus.transcribing):
            return
        timings = dict(attempt.timings or {})
        timings["queue_ms"] = int((datetime.now(timezone.utc) - as_utc(attempt.created_at)).total_seconds() * 1000) \
            - timings.get("upload_ms", 0)
        try:
            transcriber = get_transcriber()
            info = transcriber.info
            timings.update(whisper_model=info.model_size, whisper_device=f"{info.device}/{info.compute_type}",
                           llm_model=get_settings().llm_model)

            _set_status(db, attempt, AttemptStatus.transcribing)
            start = time.perf_counter()
            transcript = transcriber.transcribe(Path(attempt.audio_path))
            timings["transcription_ms"] = _ms(start)
            attempt.transcript = transcript.text
            attempt.words = transcript.words_json()
            db.commit()
            bus.publish(attempt.id, {"type": "transcript", "transcript": transcript.text})

            start = time.perf_counter()
            metrics = compute_metrics(transcript)
            timings["metrics_ms"] = _ms(start)

            if metrics.word_count < MIN_WORDS:
                attempt.status = AttemptStatus.too_short
                attempt.error = (
                    f"We only caught {metrics.word_count} word{'s' if metrics.word_count != 1 else ''}. "
                    "Please re-record a fuller answer; it won't be scored."
                    if metrics.word_count else
                    "We couldn't hear any speech. Check your microphone and re-record."
                )
                _finish(db, attempt, timings)
                return

            attempt.wpm = metrics.wpm
            attempt.filler_count = metrics.filler_count
            attempt.filler_breakdown = metrics.filler_breakdown
            attempt.long_pause_count = metrics.long_pause_count
            attempt.delivery = metrics.delivery_json()
            db.commit()
            bus.publish(attempt.id, {"type": "metrics", "metrics": {
                "wpm": metrics.wpm, "filler_count": metrics.filler_count,
                "filler_breakdown": metrics.filler_breakdown, "long_pause_count": metrics.long_pause_count,
                **metrics.delivery_json()}})

            _set_status(db, attempt, AttemptStatus.analysing)
            _evaluate(db, attempt, timings)
            attempt.status = AttemptStatus.complete
            _finish(db, attempt, timings)
        except Exception as exc:
            db.rollback()
            attempt = db.get(Attempt, attempt_id)
            attempt.status = AttemptStatus.failed
            if isinstance(exc, TranscriberUnavailable):
                log.error("Attempt %d: %s", attempt_id, exc)
                attempt.error = str(exc)
            else:
                log.exception("Attempt %d failed", attempt_id)
                attempt.error = f"Processing failed ({type(exc).__name__}). Please try again."
            _finish(db, attempt, timings)
