import logging
import time
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..models import Attempt, AttemptStatus, Question
from ..schemas.api import AttemptOut, QuestionDetail

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
    return AttemptOut.from_model(attempt)


@router.get("/attempts/{attempt_id}", response_model=AttemptOut)
def get_attempt(attempt_id: int, db: Session = Depends(get_db)):
    return AttemptOut.from_model(_load_attempt(db, attempt_id))


@router.get("/attempts/{attempt_id}/audio")
def get_attempt_audio(attempt_id: int, db: Session = Depends(get_db)):
    a = _load_attempt(db, attempt_id)
    if not a.audio_path or not Path(a.audio_path).exists():
        raise HTTPException(404, "Audio is no longer available (deleted after the retention period).")
    path = Path(a.audio_path)
    return FileResponse(path, media_type=MEDIA_TYPES.get(path.suffix, "application/octet-stream"))
