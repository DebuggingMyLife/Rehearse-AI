"""CV Builder flow behind the API.

The A1 agent used to live in the A1 GUI's in-memory session state. Here every request rebuilds ProfileAgent
(and its ProfileTool) from a CvBuild row, runs one step of the A1 flow, and writes the state back,
so a page refresh or a server restart loses nothing. A failed LLM call raises before anything is
saved, so the build stays as it was and the step can simply be retried.

The LLM and embedding calls block: callers run these functions on the worker thread.
Never log intro text, profile contents or CV text.
"""

import copy
import json
import logging
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict
from functools import lru_cache
from pathlib import Path

import httpx
from sqlalchemy.orm import Session

from ..config import Settings, get_settings
from ..cv_builder.agent import (
    EXTRACTION_SYSTEM_PROMPT, SUMMARY_SYSTEM_PROMPT, JobRequirementAgent, LLMClient, ProfileAgent, build_llm,
)
from ..cv_builder.cv_generator import CVGenerator
from ..cv_builder.cv_pdf import render_cv_pdf
from ..cv_builder.profile_model import (
    DraftEducationEntry, DraftExperienceEntry, DraftProfile, DraftProjectEntry, Profile,
)
from ..models import CvBuild, CvBuildStage, InterviewSession
from .cv_parser import parse_cv

log = logging.getLogger(__name__)

# The old GUI's caps (see CV_Builder/01_System/architecture.md, "Step limits").
STEP_CAP = 5
REVIEW_STEP_CAP = 10
JOBS_PATH = Path(__file__).resolve().parents[1] / "cv_builder" / "data" / "jobs.jsonl"


class CvBuildNotFound(LookupError):
    pass


class CvBuildStateError(Exception):
    """The request doesn't fit the build's current stage (e.g. replying when nothing was asked)."""


class CvBuilderUnavailable(Exception):
    """The CV Builder model (or the job-matching model) could not complete the step."""


# --- shared, per-process resources (stateless per user, see architecture.md "Isolation") ---

@lru_cache
def get_cv_llm() -> LLMClient:
    # app.cv_builder maps CV_BUILDER_LLM_* onto the variable names build_llm() reads.
    return build_llm()


_job_tool = None
_job_tool_lock = threading.Lock()


def get_job_tool():
    """The sentence-transformers job index, loaded once on first use. Imported lazily so
    PyTorch isn't loaded at startup (or at all, for users who only practise)."""
    global _job_tool
    with _job_tool_lock:
        if _job_tool is None:
            from ..cv_builder.job_retrieval_tool import JobRetrievalTool

            _job_tool = JobRetrievalTool()
    return _job_tool


@lru_cache
def load_jobs() -> dict[str, dict]:
    """jobs.jsonl by document_id, for display and lookups without loading the embedding model."""
    jobs = {}
    with open(JOBS_PATH, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                job = json.loads(line)
                jobs[job["document_id"]] = job
    return jobs


def get_job(job_id: str) -> dict:
    try:
        return load_jobs()[job_id]
    except KeyError:
        raise CvBuildStateError("That job is not in the job list.") from None


def job_description_for(job: dict) -> str:
    """The job description a practice session is created with."""
    parts = [job["title"]]
    if job.get("location"):
        parts.append(f"Location: {job['location']}")
    return "\n".join(parts) + "\n\n" + job["description"].strip()


@contextmanager
def _model_errors(what: str) -> Iterator[None]:
    """Turn any failure inside the A1 code into one friendly error. Only the exception type is
    logged: Groq error bodies can echo the generated (personal) content back."""
    try:
        yield
    except (CvBuildStateError, CvBuildNotFound):
        raise
    except Exception as exc:
        log.warning("CV Builder %s failed: %s", what, type(exc).__name__)
        raise CvBuilderUnavailable(_friendly(exc)) from exc


def _friendly(exc: Exception) -> str:
    settings = get_settings()
    model = settings.cv_builder_llm_model
    if isinstance(exc, httpx.ConnectError):
        return f"Could not reach Ollama at {settings.ollama_host}. Start it with `ollama serve`."
    if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 404:
        return f"The CV Builder model isn't pulled. Run `ollama pull {model}`."
    if isinstance(exc, httpx.TimeoutException):
        return "The CV Builder model took too long to answer. Please try again."
    if isinstance(exc, RuntimeError) and "GROQ_API_KEY" in str(exc):
        return "GROQ_API_KEY is not set. Add it to .env, or set CV_BUILDER_LLM_BACKEND=local."
    if isinstance(exc, OSError):
        return "Could not load the job-matching model. The first use downloads all-MiniLM-L6-v2, so check your connection."
    return "The CV Builder model returned an unusable reply. Please try again."


# --- agent state <-> database ---

def draft_from_dict(d: dict) -> DraftProfile:
    # Deep copy: DraftProfile.merge() appends to its lists in place, and sharing them with the
    # loaded JSON column would change SQLAlchemy's "before" value too, so nothing gets saved.
    d = copy.deepcopy(d)
    d["additional_education"] = [DraftEducationEntry(**e) for e in d.get("additional_education") or []]
    d["projects"] = [DraftProjectEntry(**p) for p in d.get("projects") or []]
    d["experience"] = [DraftExperienceEntry(**e) for e in d.get("experience") or []]
    return DraftProfile(**d)


def restore_agent(build: CvBuild, llm: LLMClient) -> ProfileAgent:
    """Rebuild the agent exactly as it was after the previous request. ProfileAgent and
    ProfileTool keep this state in plain attributes (some private); restore_agent/save_agent are
    the only code outside app/cv_builder that touches them."""
    agent = ProfileAgent(llm, step_cap=STEP_CAP, review_step_cap=REVIEW_STEP_CAP)
    agent.tool._draft = draft_from_dict(build.draft) if build.draft else DraftProfile()
    agent.tool._latest_gaps = copy.deepcopy(build.latest_gaps or [])
    agent.step = build.step
    agent.review_step = build.review_step
    agent._last_question = build.last_question
    agent.trace = copy.deepcopy(build.trace or [])
    return agent


def save_agent(build: CvBuild, agent: ProfileAgent) -> None:
    build.draft = asdict(agent.tool._draft)
    build.latest_gaps = list(agent.tool._latest_gaps)
    build.step = agent.step
    build.review_step = agent.review_step
    build.last_question = agent._last_question
    build.trace = list(agent.trace)


def load_build(db: Session, build_id: str) -> CvBuild:
    build = db.get(CvBuild, build_id)
    if build is None:
        raise CvBuildNotFound(build_id)
    if build.stage == CvBuildStage.step_limit:  # saved before step limits went to the form
        _to_confirm_form(build)
    return build


def _require(build: CvBuild, *stages: CvBuildStage) -> None:
    if build.stage not in stages:
        raise CvBuildStateError(f"This CV build is at the '{build.stage.value}' step, so that isn't possible now.")


def _profile(build: CvBuild, agent: ProfileAgent | None = None) -> Profile:
    tool_draft = agent.tool._draft if agent else draft_from_dict(build.draft)
    return tool_draft.to_profile(document_id=f"build_{build.id[:8]}")


def _discard_pdf(build: CvBuild) -> None:
    if build.pdf_path:
        Path(build.pdf_path).unlink(missing_ok=True)
    build.pdf_path = None


# --- intake and project review (the old GUI's intro / followup / step_limit stages) ---

def _apply_intake_result(build: CvBuild, result: dict) -> None:
    if result["status"] == "needs_input":
        build.stage, build.pending_question = CvBuildStage.followup, result["question"]
    elif result["status"] == "confirmed":
        # Intake is done; the project review starts with its own request (start_review) so the
        # UI can show a separate progress message, as the GUI's spinner did.
        build.confirm_summary = result["summary"]
        build.stage, build.phase, build.review_checked, build.pending_question = (
            CvBuildStage.followup, "review", False, None)
    else:
        _to_confirm_form(build)


def _to_confirm_form(build: CvBuild) -> None:
    """Intake hit its step cap. Rather than a dead end (the old GUI could only start over), go
    straight to the confirm form, where the user fills in whatever is still missing."""
    build.stage, build.phase, build.review_checked, build.pending_question = (
        CvBuildStage.confirm, "review", True, None)


def _apply_review_result(build: CvBuild, result: dict) -> None:
    if result["status"] == "needs_input":
        build.pending_question = result["question"]
        return
    if result["status"] == "confirmed":
        build.confirm_summary = result["summary"]
    # As in the GUI, running out of review steps just ends the review: projects keep whatever
    # was captured and the user can fill the rest in on the confirm form.
    build.stage, build.pending_question = CvBuildStage.confirm, None


def create_build(db: Session, intro: str) -> CvBuild:
    build = CvBuild(stage=CvBuildStage.followup, phase="intake")
    with _model_errors("intake"):
        agent = ProfileAgent(get_cv_llm(), step_cap=STEP_CAP, review_step_cap=REVIEW_STEP_CAP)
        result = agent.take_turn(intro)
    save_agent(build, agent)
    _apply_intake_result(build, result)
    db.add(build)
    db.commit()
    db.refresh(build)
    log.info("Created CV build %s (stage %s)", build.id[:8], build.stage.value)
    return build


def reply(db: Session, build_id: str, text: str) -> CvBuild:
    build = load_build(db, build_id)
    _require(build, CvBuildStage.followup)
    if not build.pending_question:
        raise CvBuildStateError("There is no open question to answer.")
    with _model_errors(f"{build.phase} turn"):
        agent = restore_agent(build, get_cv_llm())
        result = agent.take_turn(text, phase=build.phase)
    save_agent(build, agent)
    (_apply_review_result if build.phase == "review" else _apply_intake_result)(build, result)
    db.commit()
    return build


def start_review(db: Session, build_id: str) -> CvBuild:
    """The one-off review bootstrap the GUI ran on entering its confirm stage."""
    build = load_build(db, build_id)
    _require(build, CvBuildStage.followup)
    if build.phase != "review" or build.review_checked:
        return build  # already done (e.g. a second tab); nothing to redo
    with _model_errors("review start"):
        agent = restore_agent(build, get_cv_llm())
        result = agent.start_review()
    save_agent(build, agent)
    build.review_checked = True
    _apply_review_result(build, result)
    db.commit()
    return build


# --- confirm (the GUI's edit form) and job matching ---

def save_profile(db: Session, build_id: str, fields: dict, confirm: bool) -> CvBuild:
    """`fields` are the GUI form's fields; ProfileTool.overwrite_profile replaces them outright.
    Save regenerates the summary (GUI "Save changes"); confirm retrieves the top-3 jobs."""
    build = load_build(db, build_id)
    _require(build, CvBuildStage.confirm)
    fields = dict(fields)
    fields["experience"] = [DraftExperienceEntry(**e) for e in fields.get("experience", [])]
    fields["projects"] = [DraftProjectEntry(**p) for p in fields.get("projects", [])]
    with _model_errors("setup"):
        agent = restore_agent(build, get_cv_llm())
    agent.tool.overwrite_profile(fields)
    if confirm:
        with _model_errors("job retrieval"):
            matches = get_job_tool().search(_profile(build, agent), top_k=3)
        build.job_matches = matches
        build.stage = CvBuildStage.jobs
    else:
        with _model_errors("summary"):
            build.confirm_summary = agent.llm.generate_text(
                SUMMARY_SYSTEM_PROMPT, json.dumps(agent.tool.read_profile()["draft"]))
    save_agent(build, agent)
    db.commit()
    return build


def reopen_profile(db: Session, build_id: str) -> CvBuild:
    """Back to the confirm form from a later step (the old GUI had no way back). The job pick, any
    open requirement question and the CV are reset, since they came from the old profile, and
    confirming again re-runs job matching. Facts already confirmed for a job stay in the profile."""
    build = load_build(db, build_id)
    _require(build, CvBuildStage.jobs, CvBuildStage.requirements, CvBuildStage.cv)
    build.stage = CvBuildStage.confirm
    build.selected_job_id, build.requirement_gaps, build.requirement_question = None, None, None
    build.cv, build.profile, build.job_matches = None, None, None
    _discard_pdf(build)
    db.commit()
    return build


def select_job(db: Session, build_id: str, job_id: str) -> CvBuild:
    """Pick one of the top 3 and run JobRequirementAgent.check(). Picking again later (the GUI's
    "Choose a different job") resets only the job-specific state, never the profile."""
    build = load_build(db, build_id)
    _require(build, CvBuildStage.jobs, CvBuildStage.requirements, CvBuildStage.cv)
    if job_id not in {m["document_id"] for m in build.job_matches or []}:
        raise CvBuildStateError("Pick one of the matched jobs.")
    job = get_job(job_id)
    with _model_errors("requirement check"):
        agent = restore_agent(build, get_cv_llm())
        checker = JobRequirementAgent(agent.llm, agent.tool)
        check = checker.check(job)
    build.job_trace = list(build.job_trace or []) + checker.trace
    build.selected_job_id = job_id
    build.cv, build.profile = None, None
    _discard_pdf(build)
    if check["status"] == "needs_input":
        build.requirement_gaps, build.requirement_question = check["gaps"], check["question"]
        build.stage = CvBuildStage.requirements
    else:
        build.requirement_gaps, build.requirement_question = None, None
        build.stage = CvBuildStage.cv  # the CV is generated by its own request
    db.commit()
    return build


def answer_requirements(db: Session, build_id: str, text: str | None) -> CvBuild:
    """Resolve the job's requirement gaps from one reply, then run the same reply through general
    extraction, exactly as cv_builder_cli.run_full_flow does. `text=None` skips: every gap is
    recorded as not held (what resolve() does for anything not clearly confirmed)."""
    build = load_build(db, build_id)
    _require(build, CvBuildStage.requirements)
    gaps = build.requirement_gaps or []
    with _model_errors("requirement answer"):
        agent = restore_agent(build, get_cv_llm())
        checker = JobRequirementAgent(agent.llm, agent.tool)
        if text is None:
            declined = [g["requirement"] for g in gaps]
            agent.tool.apply_job_requirement_facts(fields={}, declined=declined)
            checker.trace.append({"role": "agent", "action": "ResolveJobRequirements", "detail": {"skipped": True},
                                  "observation": {"confirmed_skills": [], "confirmed_notes": [], "declined": declined}})
        else:
            checker.resolve(gaps, text)
            extracted = agent.llm.extract_json(
                EXTRACTION_SYSTEM_PROMPT,
                json.dumps({
                    "current_draft": agent.tool.read_profile()["draft"],
                    "last_question_asked": build.requirement_question,
                    "latest_message": text,
                }),
                max_tokens=4000,  # see agent.take_turn()
            )
            agent.tool.update_profile(extracted)
    save_agent(build, agent)
    build.job_trace = list(build.job_trace or []) + checker.trace
    build.requirement_gaps, build.requirement_question = None, None
    build.stage = CvBuildStage.cv
    db.commit()
    return build


# --- CV ---

def generate_cv(db: Session, build_id: str) -> CvBuild:
    build = load_build(db, build_id)
    _require(build, CvBuildStage.cv)
    job = get_job(build.selected_job_id)
    profile = _profile(build)
    with _model_errors("CV generation"):
        cv = CVGenerator(llm=get_cv_llm()).generate(profile, job)
    build.profile = asdict(profile)
    build.cv = cv
    _discard_pdf(build)
    db.commit()
    return build


def update_cv(db: Session, build_id: str, edits: dict) -> CvBuild:
    """The GUI's editable CV fields: summary, education, additional qualifications, experience
    and project descriptions (by position), and the skills list."""
    build = load_build(db, build_id)
    _require(build, CvBuildStage.cv)
    if build.cv is None:
        raise CvBuildStateError("Generate the CV first.")
    cv = copy.deepcopy(build.cv)
    for key in ("summary", "education", "skills"):
        if edits.get(key) is not None:
            cv[key] = edits[key]
    for key, list_key, field in (("additional_education", "additional_education", "text"),
                                 ("experience", "experience", "description"),
                                 ("projects", "projects", "description")):
        for i, value in enumerate(edits.get(key) or []):
            entries = cv.get(list_key) or []
            if value is not None and i < len(entries):
                entries[i][field] = value
    build.cv = cv
    _discard_pdf(build)
    db.commit()
    return build


def ensure_pdf(db: Session, build_id: str, settings: Settings | None = None) -> Path:
    """Render the CV with the A1 renderer, or reuse the last render if nothing changed since."""
    settings = settings or get_settings()
    build = load_build(db, build_id)
    if build.cv is None:
        raise CvBuildStateError("Generate the CV first.")
    if build.pdf_path and Path(build.pdf_path).exists():
        return Path(build.pdf_path)
    settings.cv_build_dir.mkdir(parents=True, exist_ok=True)
    path = settings.cv_build_dir / f"{build.id}.pdf"
    render_cv_pdf(build.cv, _profile(build), path)
    build.pdf_path = str(path)
    db.commit()
    return path


def pdf_filename(build: CvBuild) -> str:
    name = (build.draft or {}).get("name") or "candidate"
    safe = "".join(c if c.isalnum() else "_" for c in name).strip("_") or "candidate"
    return f"{safe}_cv.pdf"


def start_practice(db: Session, build_id: str, job_description: str | None = None,
                   settings: Settings | None = None) -> InterviewSession:
    """Create an interview session straight from the built CV: the rendered PDF goes through the
    same parse_cv as an upload (so the CV-confirm page shows extracted text as usual), and the CV
    Builder's structured view of the job is kept to steer question generation."""
    settings = settings or get_settings()
    build = load_build(db, build_id)
    _require(build, CvBuildStage.cv)
    pdf = ensure_pdf(db, build_id, settings)
    data = pdf.read_bytes()
    cv_text = parse_cv(data, pdf.name)  # CVParseError is handled by the caller
    job = get_job(build.selected_job_id)
    cv = build.cv
    session = InterviewSession(
        cv_filename=pdf_filename(build),
        cv_text=cv_text,
        job_description=(job_description or "").strip() or job_description_for(job),
        cv_build_id=build.id,
        cv_builder_context={
            "job_title": job["title"],
            "matched_skills": list(cv.get("matched_skills") or []),
            "missing_requirements": list(cv.get("missing_requirements") or []),
            "summary": cv.get("summary") or "",
        },
    )
    db.add(session)
    db.flush()  # assigns id
    path = settings.cv_dir / f"{session.id}.pdf"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    session.cv_path = str(path)
    db.commit()
    db.refresh(session)
    log.info("Created session %s from CV build %s (CV %d chars)", session.id[:8], build.id[:8], len(cv_text))
    return session
