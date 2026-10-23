from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field

from ..models import Attempt, AttemptStatus, Difficulty, InterviewSession, Question, QuestionType, SessionStatus


def as_utc(dt: datetime) -> datetime:
    """SQLite drops tzinfo; stored values are UTC, so re-attach it so the browser
    doesn't read them as local time."""
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


class QuestionOut(BaseModel):
    id: int
    position: int
    batch: int
    text: str
    type: QuestionType
    difficulty: Difficulty
    status: Literal["not_attempted", "attempted"]
    attempt_count: int
    best_score: int | None
    scores: list[int]  # scored attempts, oldest first
    # Only revealed once the question has a completed attempt.
    rubric: list[str] | None = None
    cv_evidence: list[str] | None = None

    @classmethod
    def from_model(cls, q: Question) -> "QuestionOut":
        attempted = q.is_attempted
        return cls(
            id=q.id, position=q.position, batch=q.batch, text=q.text, type=q.type,
            difficulty=q.difficulty,
            status="attempted" if attempted else "not_attempted",
            attempt_count=len(q.attempts), best_score=q.best_score,
            scores=[a.score for a in q.attempts if a.score is not None],
            rubric=q.rubric if attempted else None,
            cv_evidence=q.cv_evidence if attempted else None,
        )


class SessionOut(BaseModel):
    id: str
    created_at: datetime
    status: SessionStatus
    cv_filename: str
    cv_text: str
    job_description: str
    questions: list[QuestionOut]

    @classmethod
    def from_model(cls, s: InterviewSession) -> "SessionOut":
        return cls(
            id=s.id, created_at=as_utc(s.created_at), status=s.status, cv_filename=s.cv_filename,
            cv_text=s.cv_text, job_description=s.job_description,
            questions=[QuestionOut.from_model(q) for q in s.questions],
        )


class SessionUpdate(BaseModel):
    cv_text: str | None = Field(None, min_length=50)
    job_description: str | None = Field(None, min_length=20)


class GenerateRequest(BaseModel):
    count: int = Field(5, ge=1, le=10)
    type: QuestionType | None = None
    difficulty: Difficulty | None = None


class GenerateResponse(BaseModel):
    questions: list[QuestionOut]
    requested: int
    duplicates_removed: int
    duration_ms: int


class AttemptOut(BaseModel):
    id: int
    question_id: int
    attempt_number: int
    status: AttemptStatus
    audio_url: str | None
    audio_duration_s: float | None
    transcript: str | None
    wpm: float | None
    filler_count: int | None
    filler_breakdown: dict | None
    long_pause_count: int | None
    delivery: dict | None
    score: int | None
    scoring: dict | None
    feedback: dict | None
    timings: dict
    error: str | None
    created_at: datetime

    @classmethod
    def from_model(cls, a: Attempt) -> "AttemptOut":
        return cls(
            id=a.id, question_id=a.question_id, attempt_number=a.attempt_number, status=a.status,
            audio_url=f"/api/attempts/{a.id}/audio" if a.audio_path else None,
            audio_duration_s=a.audio_duration_s, transcript=a.transcript, wpm=a.wpm,
            filler_count=a.filler_count, filler_breakdown=a.filler_breakdown,
            long_pause_count=a.long_pause_count, delivery=a.delivery, score=a.score, scoring=a.scoring_json,
            feedback=a.feedback_json, timings=a.timings or {}, error=a.error, created_at=as_utc(a.created_at),
        )


class QuestionDetail(QuestionOut):
    session_id: str
    attempts: list[AttemptOut]

    @classmethod
    def from_model(cls, q: Question) -> "QuestionDetail":
        return cls(
            **QuestionOut.from_model(q).model_dump(),
            session_id=q.session_id,
            attempts=[AttemptOut.from_model(a) for a in q.attempts],
        )
