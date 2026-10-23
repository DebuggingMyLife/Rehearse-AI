from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import SessionLocal, get_db
from ..schemas.api import GenerateRequest, GenerateResponse, QuestionOut
from ..services.llm import LLMUnavailable, get_llm
from ..services.question_gen import generate_questions
from ..worker import run_job
from .sessions import load_session

router = APIRouter(prefix="/api/sessions/{session_id}/questions", tags=["questions"])


@router.get("", response_model=list[QuestionOut])
def list_questions(session_id: str, db: Session = Depends(get_db)):
    return [QuestionOut.from_model(q) for q in load_session(db, session_id).questions]


def _generate_job(session_id: str, req: GenerateRequest) -> GenerateResponse:
    # Own DB session: this runs on the worker thread.
    with SessionLocal() as db:
        outcome = generate_questions(db, get_llm(), session_id, req.count, req.type, req.difficulty)
        return GenerateResponse(
            questions=[QuestionOut.from_model(q) for q in outcome.questions],
            requested=req.count,
            duplicates_removed=outcome.duplicates_removed,
            duration_ms=outcome.duration_ms,
        )


@router.post("", response_model=GenerateResponse)
async def generate(session_id: str, req: GenerateRequest, db: Session = Depends(get_db)):
    load_session(db, session_id)  # 404 early
    try:
        return await run_job(_generate_job, session_id, req)
    except LLMUnavailable as exc:
        raise HTTPException(503, f"Question generation unavailable, please try again. {exc}") from exc
