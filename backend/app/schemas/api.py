from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from ..models import Difficulty, InterviewSession, Question, QuestionType, SessionStatus


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
            id=s.id, created_at=s.created_at, status=s.status, cv_filename=s.cv_filename,
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
