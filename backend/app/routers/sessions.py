import logging
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from ..config import get_settings
from ..db import get_db
from ..models import InterviewSession
from ..schemas.api import SessionOut, SessionUpdate
from ..services.cv_parser import CVParseError, parse_cv

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/sessions", tags=["sessions"])

MAX_CV_BYTES = 10 * 1024 * 1024
MIN_JD_CHARS = 20


def load_session(db: Session, session_id: str) -> InterviewSession:
    s = db.get(InterviewSession, session_id)
    if s is None:
        raise HTTPException(404, "Session not found (it may have been deleted after the retention period).")
    return s


@router.post("", response_model=SessionOut, status_code=201)
async def create_session(
    cv: UploadFile = File(...),
    job_description: str = Form(...),
    db: Session = Depends(get_db),
):
    job_description = job_description.strip()
    if len(job_description) < MIN_JD_CHARS:
        raise HTTPException(422, "Paste the full job description.")
    data = await cv.read()
    if len(data) > MAX_CV_BYTES:
        raise HTTPException(413, "CV file is larger than 10 MB.")
    filename = cv.filename or "cv"
    try:
        cv_text = await run_in_threadpool(parse_cv, data, filename)
    except CVParseError as exc:
        raise HTTPException(422, str(exc)) from exc

    session = InterviewSession(cv_filename=filename, cv_text=cv_text, job_description=job_description)
    db.add(session)
    db.flush()  # assigns id
    settings = get_settings()
    path = settings.cv_dir / f"{session.id}{Path(filename).suffix.lower()}"
    path.write_bytes(data)
    session.cv_path = str(path)
    db.commit()
    db.refresh(session)
    log.info("Created session %s (CV %d chars, JD %d chars)", session.id[:8], len(cv_text), len(job_description))
    return SessionOut.from_model(session)


@router.get("/{session_id}", response_model=SessionOut)
def get_session(session_id: str, db: Session = Depends(get_db)):
    return SessionOut.from_model(load_session(db, session_id))


@router.patch("/{session_id}", response_model=SessionOut)
def update_session(session_id: str, body: SessionUpdate, db: Session = Depends(get_db)):
    """Lets the user correct CV text that parsed badly, or edit the job description."""
    s = load_session(db, session_id)
    if body.cv_text is not None:
        s.cv_text = body.cv_text.strip()
    if body.job_description is not None:
        s.job_description = body.job_description.strip()
    db.commit()
    db.refresh(s)
    return SessionOut.from_model(s)
