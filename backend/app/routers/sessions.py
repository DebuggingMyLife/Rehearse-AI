import logging
import re
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from ..config import get_settings
from ..db import SessionLocal, get_db
from ..models import InterviewSession
from ..schemas.api import SessionOut, SessionUpdate
from ..services.cv_parser import CVParseError, parse_cv
from ..services.export_pdf import build_session_pdf
from ..services.llm import LLMUnavailable, get_llm
from ..services.summary import NothingToSummarise, session_stats, summarise_session
from ..worker import run_job

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


@router.get("/{session_id}/stats")
def get_stats(session_id: str, db: Session = Depends(get_db)):
    """Score and delivery statistics, computed without the LLM."""
    return session_stats(load_session(db, session_id))


def _summarise_job(session_id: str) -> SessionOut:
    with SessionLocal() as db:
        return SessionOut.from_model(summarise_session(db, get_llm(), session_id))


@router.post("/{session_id}/end", response_model=SessionOut)
async def end_session(session_id: str, db: Session = Depends(get_db)):
    """End the session and generate the summary (can be called again to regenerate)."""
    load_session(db, session_id)
    try:
        return await run_job(_summarise_job, session_id)
    except NothingToSummarise as exc:
        raise HTTPException(422, str(exc)) from exc
    except LLMUnavailable as exc:
        raise HTTPException(503, f"Summary unavailable, please try again. {exc}") from exc


@router.get("/{session_id}/export.pdf")
async def export_pdf(session_id: str):
    def build() -> tuple[bytes, str]:
        with SessionLocal() as db:
            s = load_session(db, session_id)
            return build_session_pdf(s), s.created_at.strftime("%Y-%m-%d")

    pdf, date = await run_in_threadpool(build)
    name = re.sub(r"[^A-Za-z0-9-]", "", f"rehearseai-session-{date}") + ".pdf"
    return Response(pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})
