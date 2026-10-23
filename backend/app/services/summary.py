"""End-of-session summary: statistics computed in Python, narrative from one LLM call."""

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from .. import prompts
from ..models import Attempt, AttemptStatus, InterviewSession, Question, SessionStatus
from ..schemas.llm import SessionSummaryOut
from .llm import OllamaClient

log = logging.getLogger(__name__)

MAX_JD_CHARS = 1_500


class NothingToSummarise(ValueError):
    pass


def scored_attempts(q: Question) -> list[Attempt]:
    return [a for a in q.attempts if a.status == AttemptStatus.complete and a.score is not None]


def best_attempt(q: Question) -> Attempt | None:
    """Highest score; the latest attempt wins ties (it reflects the most recent practice)."""
    scored = scored_attempts(q)
    return max(scored, key=lambda a: (a.score, a.attempt_number)) if scored else None


def session_stats(session: InterviewSession) -> dict:
    measured = [a for q in session.questions for a in q.attempts
                if a.status == AttemptStatus.complete and a.wpm is not None]
    speaking_min = sum((a.delivery or {}).get("speaking_time_s", 0) for a in measured) / 60
    answered = [q for q in session.questions if best_attempt(q)]
    improved = []
    for q in answered:
        scores = [a.score for a in scored_attempts(q)]
        if len(scores) > 1:
            improved.append({"question_id": q.id, "first": scores[0], "best": max(scores)})
    best_scores = [best_attempt(q).score for q in answered]
    return {
        "questions_total": len(session.questions),
        "questions_answered": len(answered),
        "attempts_scored": sum(len(scored_attempts(q)) for q in session.questions),
        "avg_best_score": round(sum(best_scores) / len(best_scores), 1) if best_scores else None,
        "retried": improved,
        "delivery": {
            "avg_wpm": round(sum(a.wpm for a in measured) / len(measured)) if measured else None,
            "fillers_per_min": round(sum(a.filler_count or 0 for a in measured) / speaking_min, 1)
            if speaking_min else None,
            "avg_fillers": round(sum(a.filler_count or 0 for a in measured) / len(measured), 1) if measured else None,
            "avg_long_pauses": round(sum(a.long_pause_count or 0 for a in measured) / len(measured), 1)
            if measured else None,
        },
    }


def summarise_session(db: Session, llm: OllamaClient, session_id: str) -> InterviewSession:
    """Runs on the worker thread. Ends the session and stores the summary."""
    session = db.get(InterviewSession, session_id)
    if session is None:
        raise LookupError(session_id)
    stats = session_stats(session)
    questions = []
    for q in session.questions:
        best = best_attempt(q)
        if best is None:
            continue
        fb = best.feedback_json or {}
        questions.append({
            "position": q.position, "type": q.type.value.replace("_", "-"), "difficulty": q.difficulty.value,
            "text": q.text,
            "attempts": len(scored_attempts(q)), "scores": [a.score for a in scored_attempts(q)],
            "strengths": [s["point"] for s in fb.get("what_you_did_well", [])],
            "improvements": fb.get("what_could_be_improved", []),
        })
    if not questions:
        raise NothingToSummarise("Answer at least one question (and get feedback) before ending the session.")

    jd = session.job_description
    system, user = prompts.render(
        "session_summary", questions=questions, delivery=stats["delivery"],
        job_description=jd[:MAX_JD_CHARS] + ("\n[...]" if len(jd) > MAX_JD_CHARS else ""),
    )
    result = llm.chat_json(system, user, SessionSummaryOut, label=f"summary:{session_id[:8]}", num_predict=900)
    session.summary_json = {
        **result.data.model_dump(),
        "stats": stats,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    session.status = SessionStatus.ended
    session.ended_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(session)
    return session
