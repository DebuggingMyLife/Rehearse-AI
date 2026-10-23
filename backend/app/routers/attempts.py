import asyncio
import json
import logging
import time
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import SessionLocal, get_db
from ..events import bus
from ..models import Attempt, AttemptStatus, Question
from ..schemas.api import AttemptOut, QuestionDetail
from ..services.pipeline import process_attempt
from ..worker import run_job

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["attempts"])

MAX_AUDIO_BYTES = 25 * 1024 * 1024
MIN_AUDIO_BYTES = 1024
# Browser MediaRecorder formats: Chrome/Firefox give webm or ogg (Opus), Safari gives mp4.
AUDIO_EXTENSIONS = {
    "audio/webm": ".webm",
    "audio/ogg": ".ogg",
    "audio/mp4": ".m4a",
    "audio/x-m4a": ".m4a",
    "audio/mpeg": ".mp3",
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
}
MEDIA_TYPES = {ext: mt for mt, ext in reversed(AUDIO_EXTENSIONS.items())}
TERMINAL_STATUSES = {AttemptStatus.complete, AttemptStatus.too_short, AttemptStatus.failed}
SSE_KEEPALIVE_S = 15

_background: set[asyncio.Task] = set()


def schedule_processing(attempt_id: int) -> None:
    """Queue the attempt on the worker; keep a reference so the task isn't GC'd."""
    task = asyncio.get_running_loop().create_task(run_job(process_attempt, attempt_id))
    _background.add(task)
    task.add_done_callback(_background.discard)


def _load_question(db: Session, question_id: int) -> Question:
    q = db.get(Question, question_id)
    if q is None:
        raise HTTPException(404, "Question not found.")
    return q


def _load_attempt(db: Session, attempt_id: int) -> Attempt:
    a = db.get(Attempt, attempt_id)
    if a is None:
        raise HTTPException(404, "Attempt not found.")
    return a


@router.get("/questions/{question_id}", response_model=QuestionDetail)
def get_question(question_id: int, db: Session = Depends(get_db)):
    return QuestionDetail.from_model(_load_question(db, question_id))


@router.post("/questions/{question_id}/attempts", response_model=AttemptOut, status_code=201)
async def create_attempt(
    question_id: int,
    audio: UploadFile = File(...),
    duration_s: float = Form(..., gt=0, le=60 * 30),
    db: Session = Depends(get_db),
):
    start = time.perf_counter()
    question = _load_question(db, question_id)

    mime = (audio.content_type or "").split(";")[0].strip().lower()
    ext = AUDIO_EXTENSIONS.get(mime)
    if ext is None:
        raise HTTPException(415, f"Unsupported audio format '{mime or 'unknown'}'.")
    data = await audio.read()
    if len(data) > MAX_AUDIO_BYTES:
        raise HTTPException(413, "Recording is larger than 25 MB.")
    if len(data) < MIN_AUDIO_BYTES:
        raise HTTPException(422, "The recording is empty. Check your microphone and record again.")

    attempt = Attempt(
        question_id=question.id,
        attempt_number=len(question.attempts) + 1,
        status=AttemptStatus.uploaded,
        audio_duration_s=round(duration_s, 2),
    )
    db.add(attempt)
    db.flush()  # assigns id
    path = get_settings().audio_dir / f"{attempt.id}{ext}"
    path.write_bytes(data)
    attempt.audio_path = str(path)
    attempt.timings = {"upload_ms": int((time.perf_counter() - start) * 1000)}
    db.commit()
    db.refresh(attempt)
    log.info(
        "Attempt %d saved for question %d (#%d, %.1fs audio, %d KB, %s) upload_ms=%d",
        attempt.id, question.id, attempt.attempt_number, duration_s, len(data) // 1024, mime,
        attempt.timings["upload_ms"],
    )
    schedule_processing(attempt.id)
    return AttemptOut.from_model(attempt)


@router.get("/attempts/{attempt_id}", response_model=AttemptOut)
def get_attempt(attempt_id: int, db: Session = Depends(get_db)):
    return AttemptOut.from_model(_load_attempt(db, attempt_id))


@router.get("/attempts/{attempt_id}/events")
async def attempt_events(attempt_id: int, request: Request):
    """Server-sent events: a snapshot of the attempt, then progress until `done`."""
    queue = bus.subscribe(attempt_id)  # subscribe before reading state so no event is missed
    try:
        with SessionLocal() as db:
            snapshot = AttemptOut.from_model(_load_attempt(db, attempt_id))
    except HTTPException:
        bus.unsubscribe(attempt_id, queue)
        raise

    def sse(event: str, data: dict) -> str:
        return f"event: {event}\ndata: {json.dumps(data)}\n\n"

    async def stream():
        try:
            if snapshot.status in TERMINAL_STATUSES:
                yield sse("done", {"type": "done", "attempt": snapshot.model_dump(mode="json")})
                return
            yield sse("status", {"type": "status", "status": snapshot.status.value})
            while not await request.is_disconnected():
                try:
                    event = await asyncio.wait_for(queue.get(), SSE_KEEPALIVE_S)
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
                    continue
                yield sse(event["type"], event)
                if event["type"] == "done":
                    return
        finally:
            bus.unsubscribe(attempt_id, queue)

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.get("/attempts/{attempt_id}/audio")
def get_attempt_audio(attempt_id: int, db: Session = Depends(get_db)):
    a = _load_attempt(db, attempt_id)
    if not a.audio_path or not Path(a.audio_path).exists():
        raise HTTPException(404, "Audio is no longer available (deleted after the retention period).")
    path = Path(a.audio_path)
    return FileResponse(path, media_type=MEDIA_TYPES.get(path.suffix, "application/octet-stream"))
