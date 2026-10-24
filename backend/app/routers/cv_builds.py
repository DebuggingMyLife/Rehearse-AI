"""CV Builder API: the A1 GUI's stages as REST steps over a stored CvBuild.

intro -> follow-ups (intake, then one-at-a-time project review) -> confirm -> jobs ->
requirement gaps (if any) -> CV (edit, PDF) -> start practice.
"""

from collections.abc import Callable

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from ..db import SessionLocal, get_db
from ..models import CvBuild
from ..schemas.api import (
    CvBuildCreate, CvBuildOut, CvBuildReply, CvBuildSummary, CvEdit, JobSelect, PracticeRequest, ProfileEdit,
    RequirementAnswer, SessionOut,
)
from ..services import cv_builds as svc
from ..services.cv_parser import CVParseError
from ..worker import run_job

router = APIRouter(prefix="/api/cv-builds", tags=["cv-builds"])


def _raise_http(exc: Exception) -> None:
    if isinstance(exc, svc.CvBuildNotFound):
        raise HTTPException(404, "CV build not found (it may have been deleted after the retention period).") from exc
    if isinstance(exc, svc.CvBuildStateError):
        raise HTTPException(409, str(exc)) from exc
    if isinstance(exc, svc.CvBuilderUnavailable):
        raise HTTPException(503, str(exc)) from exc
    if isinstance(exc, CVParseError):
        raise HTTPException(422, f"Could not read the generated CV back: {exc}") from exc
    raise exc


def _step(fn: Callable[..., CvBuild], *args) -> CvBuildOut:
    """Run one flow step with its own DB session and return the updated build."""
    with SessionLocal() as db:
        return CvBuildOut.from_model(fn(db, *args))


async def _on_worker(fn: Callable[..., CvBuild], *args) -> CvBuildOut:
    # LLM and embedding steps go through the single GPU worker, so they don't compete with
    # Whisper/Ollama for VRAM and two requests on the same build can't interleave.
    try:
        return await run_job(_step, fn, *args)
    except (svc.CvBuildNotFound, svc.CvBuildStateError, svc.CvBuilderUnavailable) as exc:
        _raise_http(exc)


async def _in_threadpool(fn: Callable[..., CvBuild], *args) -> CvBuildOut:
    try:
        return await run_in_threadpool(_step, fn, *args)
    except (svc.CvBuildNotFound, svc.CvBuildStateError) as exc:
        _raise_http(exc)


@router.get("", response_model=list[CvBuildSummary])
def list_builds(db: Session = Depends(get_db)):
    builds = db.scalars(select(CvBuild).order_by(CvBuild.updated_at.desc())).all()
    return [CvBuildSummary.from_model(b) for b in builds]


@router.post("", response_model=CvBuildOut, status_code=201)
async def create_build(body: CvBuildCreate):
    """Start from the free-text introduction; runs the first intake turn."""
    return await _on_worker(svc.create_build, body.intro.strip())


@router.get("/{build_id}", response_model=CvBuildOut)
def get_build(build_id: str, db: Session = Depends(get_db)):
    try:
        return CvBuildOut.from_model(svc.load_build(db, build_id))
    except svc.CvBuildNotFound as exc:
        _raise_http(exc)


@router.post("/{build_id}/reply", response_model=CvBuildOut)
async def reply(build_id: str, body: CvBuildReply):
    """Answer the open follow-up question (intake or project review)."""
    return await _on_worker(svc.reply, build_id, body.text.strip())


@router.post("/{build_id}/review/start", response_model=CvBuildOut)
async def start_review(build_id: str):
    """Once intake is done: check the projects for a missing date or outcome."""
    return await _on_worker(svc.start_review, build_id)


@router.put("/{build_id}/profile", response_model=CvBuildOut)
async def save_profile(build_id: str, body: ProfileEdit):
    """Save the confirm form (regenerates the summary), or confirm it and find the top 3 jobs."""
    return await _on_worker(svc.save_profile, build_id, body.fields(), body.confirm)


@router.post("/{build_id}/profile/reopen", response_model=CvBuildOut)
async def reopen_profile(build_id: str):
    """Go back to the confirm form after confirming (resets the job and CV)."""
    return await _in_threadpool(svc.reopen_profile, build_id)


@router.post("/{build_id}/job", response_model=CvBuildOut)
async def select_job(build_id: str, body: JobSelect):
    """Pick a matched job and check its stated requirements against the profile."""
    return await _on_worker(svc.select_job, build_id, body.job_id)


@router.post("/{build_id}/requirements", response_model=CvBuildOut)
async def answer_requirements(build_id: str, body: RequirementAnswer):
    text = None if body.skip else (body.text or "").strip()
    if text == "":
        raise HTTPException(422, "Write an answer, or skip.")
    return await _on_worker(svc.answer_requirements, build_id, text)


@router.post("/{build_id}/cv", response_model=CvBuildOut)
async def generate_cv(build_id: str):
    """Generate (or regenerate) the tailored CV for the selected job."""
    return await _on_worker(svc.generate_cv, build_id)


@router.patch("/{build_id}/cv", response_model=CvBuildOut)
async def update_cv(build_id: str, body: CvEdit):
    return await _in_threadpool(svc.update_cv, build_id, body.model_dump())


@router.get("/{build_id}/cv.pdf")
async def get_pdf(build_id: str, download: bool = False):
    def build() -> tuple[bytes, str]:
        with SessionLocal() as db:
            path = svc.ensure_pdf(db, build_id)
            return path.read_bytes(), svc.pdf_filename(svc.load_build(db, build_id))

    try:
        pdf, name = await run_in_threadpool(build)
    except (svc.CvBuildNotFound, svc.CvBuildStateError) as exc:
        _raise_http(exc)
    disposition = "attachment" if download else "inline"
    return Response(pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'{disposition}; filename="{name}"', "Cache-Control": "no-store"})


@router.post("/{build_id}/practice", response_model=SessionOut, status_code=201)
async def start_practice(build_id: str, body: PracticeRequest | None = None):
    """Create an interview session from the built CV and the selected job."""
    job_description = body.job_description if body else None
    if job_description is not None and 0 < len(job_description.strip()) < 20:
        raise HTTPException(422, "Paste the full job description.")

    def create() -> SessionOut:
        with SessionLocal() as db:
            return SessionOut.from_model(svc.start_practice(db, build_id, job_description))

    try:
        return await run_in_threadpool(create)
    except (svc.CvBuildNotFound, svc.CvBuildStateError, CVParseError) as exc:
        _raise_http(exc)
