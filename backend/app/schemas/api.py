from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field

from ..models import (
    Attempt, AttemptStatus, CvBuild, CvBuildStage, Difficulty, InterviewSession, Question, QuestionType, SessionStatus,
)
from ..services.cv_builds import job_description_for, load_jobs


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
    ended_at: datetime | None = None
    summary: dict | None = None
    # Present when the session was started from a CV Builder build
    cv_build_id: str | None = None
    cv_builder_context: dict | None = None

    @classmethod
    def from_model(cls, s: InterviewSession) -> "SessionOut":
        return cls(
            id=s.id, created_at=as_utc(s.created_at), status=s.status, cv_filename=s.cv_filename,
            cv_text=s.cv_text, job_description=s.job_description,
            questions=[QuestionOut.from_model(q) for q in s.questions],
            ended_at=as_utc(s.ended_at) if s.ended_at else None, summary=s.summary_json,
            cv_build_id=s.cv_build_id, cv_builder_context=s.cv_builder_context,
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


# --- CV Builder ---

class CvBuildCreate(BaseModel):
    intro: str = Field(..., min_length=20, max_length=10_000)


class CvBuildReply(BaseModel):
    text: str = Field(..., min_length=1, max_length=5_000)


class RequirementAnswer(BaseModel):
    text: str | None = Field(None, max_length=5_000)
    skip: bool = False


class ExperienceEdit(BaseModel):
    role: str | None = None
    organisation: str | None = None
    description: str | None = None
    start_date: str | None = None
    end_date: str | None = None


class ProjectEdit(BaseModel):
    title: str = ""
    description: str | None = None
    technologies: list[str] = []
    start_date: str | None = None
    end_date: str | None = None
    dates_declined: bool = False
    outcome_declined: bool = False


def _clean(value: str | None) -> str | None:
    return (value or "").strip() or None


def _one_line(value: str | None) -> str | None:
    return " ".join((value or "").split()) or None


def _clean_list(items: list[str]) -> list[str]:
    return [i.strip() for i in items if i.strip()]


class ProfileEdit(BaseModel):
    """The old GUI's confirm-stage form. Every field replaces the stored value outright.
    Dates aren't on the form but are passed back unchanged, so editing doesn't drop them."""
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    github: str | None = None
    linkedin: str | None = None
    degree: str | None = None
    institution: str | None = None
    year: str | None = None
    technical_skills: list[str] = []
    target_roles: list[str] = []
    summary: str | None = None
    achievements: list[str] = []
    experience: list[ExperienceEdit] = []
    projects: list[ProjectEdit] = []
    confirm: bool = False  # False = "Save changes", True = "Confirm & find matching jobs"

    def fields(self) -> dict:
        scalars = ("name", "email", "phone", "github", "linkedin", "degree", "institution", "year", "summary")
        # Same rule as the GUI: blank experience rows and untitled projects are dropped. Titles and
        # roles also get their whitespace collapsed (text pasted from a PDF CV brings tabs along),
        # and a row repeating an earlier one is dropped: a project with the same title (ignoring
        # case, as DraftProfile.merge() matches them), or experience with the same role and
        # organisation (two roles at one employer are kept).
        experience, seen_exp = [], set()
        for e in self.experience:
            row = {**e.model_dump(), "role": _one_line(e.role), "organisation": _one_line(e.organisation)}
            key = ((row["role"] or "").lower(), (row["organisation"] or "").lower())
            if not (row["role"] or row["organisation"] or _clean(e.description)) or (any(key) and key in seen_exp):
                continue
            seen_exp.add(key)
            experience.append(row)
        projects, seen_titles = [], set()
        for p in self.projects:
            title = _one_line(p.title)
            if not title or title.lower() in seen_titles:
                continue
            seen_titles.add(title.lower())
            projects.append({**p.model_dump(), "title": title, "technologies": _clean_list(p.technologies)})
        return {
            **{k: _clean(getattr(self, k)) for k in scalars},
            "technical_skills": _clean_list(self.technical_skills),
            "target_roles": _clean_list(self.target_roles),
            "achievements": _clean_list(self.achievements),
            "experience": experience,
            "projects": projects,
        }


class JobSelect(BaseModel):
    job_id: str


class CvEdit(BaseModel):
    """The old GUI's editable CV fields. List items match by position; null leaves one as is."""
    summary: str | None = None
    education: str | None = None
    skills: list[str] | None = None
    additional_education: list[str | None] | None = None
    experience: list[str | None] | None = None
    projects: list[str | None] | None = None


class PracticeRequest(BaseModel):
    # Optional override; defaults to the selected job's title, location and description.
    job_description: str | None = Field(None, max_length=20_000)


class ChatMessage(BaseModel):
    role: Literal["user", "agent"]
    text: str
    phase: str  # intake | review


class JobMatchOut(BaseModel):
    document_id: str
    title: str
    location: str | None = None
    score: float | None = None
    excerpt: str | None = None


def _job_out(job_id: str | None, match: dict | None = None) -> JobMatchOut | None:
    job = load_jobs().get(job_id or "")
    if job is None:
        return None
    match = match or {}
    return JobMatchOut(document_id=job["document_id"], title=job["title"], location=job.get("location"),
                       score=match.get("score"), excerpt=match.get("excerpt"))


def conversation_from_trace(trace: list[dict]) -> list[ChatMessage]:
    """The agent's questions and the user's replies, from ProfileAgent.trace. A user turn takes
    the phase of the agent action logged right after it."""
    messages = []
    for i, entry in enumerate(trace):
        if entry.get("role") == "user" and entry.get("text"):
            following = next((e for e in trace[i + 1:] if e.get("role") == "agent"), {})
            messages.append(ChatMessage(role="user", text=entry["text"], phase=following.get("phase", "intake")))
        elif entry.get("action") == "AskFollowUp":
            messages.append(ChatMessage(role="agent", text=entry["observation"]["question"],
                                        phase=entry.get("phase", "intake")))
    return messages


class CvBuildSummary(BaseModel):
    id: str
    created_at: datetime
    updated_at: datetime
    stage: CvBuildStage
    name: str | None
    job_title: str | None
    has_cv: bool
    job_description: str | None  # the selected job, for prefilling the practice setup page

    @classmethod
    def from_model(cls, b: CvBuild) -> "CvBuildSummary":
        job = load_jobs().get(b.selected_job_id or "")
        return cls(
            id=b.id, created_at=as_utc(b.created_at), updated_at=as_utc(b.updated_at), stage=b.stage,
            name=(b.draft or {}).get("name"), job_title=job["title"] if job else None,
            has_cv=b.cv is not None, job_description=job_description_for(job) if job else None,
        )


class CvBuildOut(CvBuildSummary):
    phase: str
    pending_question: str | None
    review_checked: bool
    ended_at_step_limit: bool  # intake or review ran out of steps; the form shows a note
    conversation: list[ChatMessage]
    confirm_summary: str | None
    draft: dict
    job_matches: list[JobMatchOut]
    selected_job: JobMatchOut | None
    requirement_question: str | None
    requirement_gaps: list[dict] | None
    last_resolution: dict | None  # {confirmed_skills, confirmed_notes, declined}
    cv: dict | None

    @classmethod
    def from_model(cls, b: CvBuild) -> "CvBuildOut":
        trace = b.trace or []
        # Only the answer for the current job: a later job pick appends a CheckJobRequirements entry
        last_job_action = (b.job_trace or [{}])[-1]
        resolved = last_job_action.get("action") == "ResolveJobRequirements" and b.stage == CvBuildStage.cv
        matches = [_job_out(m["document_id"], m) for m in b.job_matches or []]
        return cls(
            **CvBuildSummary.from_model(b).model_dump(),
            phase=b.phase, pending_question=b.pending_question, review_checked=b.review_checked,
            ended_at_step_limit=any(e.get("action") == "StepLimitReached" for e in trace),
            conversation=conversation_from_trace(trace), confirm_summary=b.confirm_summary, draft=b.draft or {},
            job_matches=[m for m in matches if m], selected_job=_job_out(b.selected_job_id),
            requirement_question=b.requirement_question, requirement_gaps=b.requirement_gaps,
            last_resolution=last_job_action["observation"] if resolved else None,
            cv=b.cv,
        )
