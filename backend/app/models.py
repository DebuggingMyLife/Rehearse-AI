import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SessionStatus(str, enum.Enum):
    active = "active"
    ended = "ended"


class QuestionType(str, enum.Enum):
    behavioural = "behavioural"
    technical = "technical"
    cv_specific = "cv_specific"


class Difficulty(str, enum.Enum):
    easy = "easy"
    medium = "medium"
    hard = "hard"


class AttemptStatus(str, enum.Enum):
    uploaded = "uploaded"
    transcribing = "transcribing"
    analysing = "analysing"
    complete = "complete"
    too_short = "too_short"
    failed = "failed"


# Attempts that count as "attempted" (and so reveal the rubric). Too-short or failed
# attempts don't, so the user can't see the rubric by submitting silence.
COUNTED_ATTEMPT_STATUSES = {
    AttemptStatus.uploaded, AttemptStatus.transcribing, AttemptStatus.analysing, AttemptStatus.complete,
}


class InterviewSession(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[SessionStatus] = mapped_column(Enum(SessionStatus), default=SessionStatus.active)

    cv_filename: Mapped[str] = mapped_column(String(255))
    cv_path: Mapped[str | None] = mapped_column(String(512))
    cv_text: Mapped[str] = mapped_column(Text)  # never log this
    job_description: Mapped[str] = mapped_column(Text)
    summary_json: Mapped[dict | None] = mapped_column(JSON)

    questions: Mapped[list["Question"]] = relationship(
        back_populates="session", cascade="all, delete-orphan", order_by="Question.position"
    )

    def __repr__(self) -> str:  # keep CV/JD out of any accidental log line
        return f"<InterviewSession {self.id} status={self.status.value}>"


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer)
    batch: Mapped[int] = mapped_column(Integer, default=1)
    text: Mapped[str] = mapped_column(Text)
    type: Mapped[QuestionType] = mapped_column(Enum(QuestionType))
    difficulty: Mapped[Difficulty] = mapped_column(Enum(Difficulty))
    # JD requirement or CV item this question was steered towards (topic diversity)
    focus: Mapped[str | None] = mapped_column(Text)
    rubric: Mapped[list[str]] = mapped_column(JSON, default=list)  # hidden until attempted
    cv_evidence: Mapped[list[str]] = mapped_column(JSON, default=list)  # hidden until attempted
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    session: Mapped[InterviewSession] = relationship(back_populates="questions")
    attempts: Mapped[list["Attempt"]] = relationship(
        back_populates="question", cascade="all, delete-orphan", order_by="Attempt.attempt_number"
    )

    @property
    def best_score(self) -> int | None:
        scores = [a.score for a in self.attempts if a.score is not None]
        return max(scores) if scores else None

    @property
    def is_attempted(self) -> bool:
        return any(a.status in COUNTED_ATTEMPT_STATUSES for a in self.attempts)


class Attempt(Base):
    __tablename__ = "attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id", ondelete="CASCADE"), index=True)
    attempt_number: Mapped[int] = mapped_column(Integer)
    status: Mapped[AttemptStatus] = mapped_column(Enum(AttemptStatus), default=AttemptStatus.uploaded)

    audio_path: Mapped[str | None] = mapped_column(String(512))
    audio_duration_s: Mapped[float | None] = mapped_column(Float)

    transcript: Mapped[str | None] = mapped_column(Text)
    words: Mapped[list[dict] | None] = mapped_column(JSON)  # [{w, start, end}]

    wpm: Mapped[float | None] = mapped_column(Float)
    filler_count: Mapped[int | None] = mapped_column(Integer)
    filler_breakdown: Mapped[dict | None] = mapped_column(JSON)
    long_pause_count: Mapped[int | None] = mapped_column(Integer)
    # {word_count, speaking_time_s, longest_pause_s, pauses: [{at, duration}]}
    delivery: Mapped[dict | None] = mapped_column(JSON)

    score: Mapped[int | None] = mapped_column(Integer)  # copied from scoring_json
    scoring_json: Mapped[dict | None] = mapped_column(JSON)
    feedback_json: Mapped[dict | None] = mapped_column(JSON)

    # {upload_ms, transcription_ms, metrics_ms, llm_score_ms, llm_feedback_ms, total_ms,
    #  llm_model, whisper_model, whisper_device}
    timings: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    question: Mapped[Question] = relationship(back_populates="attempts")
