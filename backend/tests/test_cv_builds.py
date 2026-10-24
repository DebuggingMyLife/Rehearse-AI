"""CV Builder through the API, with a fake A1 LLMClient and a stubbed job-retrieval model."""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.config import get_settings
from app.cv_builder.agent import (
    EXTRACTION_SYSTEM_PROMPT, FOLLOW_UP_SYSTEM_PROMPT, JOB_REQUIREMENT_ANSWER_SYSTEM_PROMPT,
    JOB_REQUIREMENT_GAP_SYSTEM_PROMPT, SUMMARY_SYSTEM_PROMPT, LLMClient, ProfileAgent,
)
from app.cv_builder.cv_generator import CV_GENERATION_SYSTEM_PROMPT
from app.db import SessionLocal
from app.models import CvBuild, InterviewSession, Question
from app.services import cv_builds as svc
from app.services import question_gen
from app.services.cleanup import run_cleanup
from app.services.llm import LLMResult
from app.schemas.llm import QuestionBatch

INTRO = ("Hi, I'm Jordan Ramirez, a third-year Bachelor of Computing Science student. I know Python, "
         "SQL and Flask. I built a course timetable API with Flask. I want Junior Backend Developer roles.")
JOB_IDS = ["graduate_ai_engineer", "healthcare_ml_engineer", "rag_agent_engineer"]


def _extraction(**fields) -> dict:
    base = {"name": None, "degree": None, "institution": None, "year": None, "education_start_date": None,
            "education_end_date": None, "additional_education": [], "technical_skills": [], "projects": [],
            "experience": [], "target_roles": [], "achievements": [], "summary": None, "declined_fields": [],
            "gaps": []}
    return {**base, **fields}


class FakeCvLLM(LLMClient):
    """Answers each A1 prompt with a scripted reply; extraction replies are keyed by the user's
    latest message (the review bootstrap sends an empty one)."""

    def __init__(self):
        self.calls: list[dict] = []
        self.extractions = {
            INTRO: _extraction(
                name="Jordan Ramirez", degree="Bachelor of Computing Science", year="Third year",
                technical_skills=["Python", "SQL", "Flask"], target_roles=["Junior Backend Developer"],
                projects=[{"title": "Timetable API", "description": "Built a course timetable API",
                           "technologies": ["Flask"], "start_date": None, "end_date": None}],
                gaps=[{"field": "institution", "issue": "missing", "reason": "Which university?",
                       "entry_identifier": None}],
            ),
            "I study at UTS.": _extraction(institution="UTS"),
            "": _extraction(gaps=[{"field": "project_dates", "issue": "missing", "reason": "Timetable API dates",
                                   "entry_identifier": "Timetable API"}]),
            "March to May 2024.": _extraction(projects=[{"title": "Timetable API", "description": None,
                                                         "technologies": [], "start_date": "March 2024",
                                                         "end_date": "May 2024"}]),
            "Yes, I used Docker for the timetable API.": _extraction(),
        }

    def extract_json(self, system_prompt, user_content, max_tokens=1024):
        self.calls.append({"system": system_prompt, "user": user_content})
        if system_prompt == EXTRACTION_SYSTEM_PROMPT:
            return json.loads(json.dumps(self.extractions[json.loads(user_content)["latest_message"]]))
        if system_prompt == JOB_REQUIREMENT_GAP_SYSTEM_PROMPT:
            return {"gaps": [{"requirement": "Docker", "kind": "skill", "reason": "Listed in the role"},
                             {"requirement": "Kubernetes", "kind": "skill", "reason": "Listed in the role"}],
                    "question": "This role lists Docker and Kubernetes. Have you used either?"}
        if system_prompt == JOB_REQUIREMENT_ANSWER_SYSTEM_PROMPT:
            return {"resolutions": [
                {"requirement": "Docker", "status": "confirmed", "skill_name": "Docker", "note": None},
                {"requirement": "Kubernetes", "status": "declined", "skill_name": None, "note": None}]}
        if system_prompt == CV_GENERATION_SYSTEM_PROMPT:
            return {
                "summary": "Computing Science student building backend services in Python.",
                "education": "Bachelor of Computing Science, UTS",
                "skills": ["Python", "SQL", "Flask", "Docker", "Rust"],  # Rust is ungrounded
                "skills_by_category": {},
                "experience": [],
                "projects": [{"title": "Timetable API", "description": "Built a course timetable API with Flask.",
                              "technologies": ["Flask"]}],
                "additional_education": [],
                "matched_skills": ["Python", "Docker"],
                "missing_requirements": ["Kubernetes", "Model deployment on AWS"],
            }
        raise AssertionError("unexpected extract_json prompt")

    def generate_text(self, system_prompt, user_content, max_tokens=400):
        self.calls.append({"system": system_prompt, "user": user_content})
        if system_prompt == FOLLOW_UP_SYSTEM_PROMPT:
            return "Which institution do you study at?" if "university" in user_content else "When did you build the Timetable API?"
        if system_prompt == SUMMARY_SYSTEM_PROMPT:
            return "You are Jordan Ramirez, studying Computing Science. Does this look right?"
        raise AssertionError("unexpected generate_text prompt")


class FakeJobTool:
    def __init__(self):
        self.profiles = []

    def search(self, profile, top_k=3):
        self.profiles.append(profile)
        return [{"document_id": j, "title": svc.load_jobs()[j]["title"], "score": 0.5 - i / 10,
                 "excerpt": "Build ML systems."} for i, j in enumerate(JOB_IDS[:top_k])]


@pytest.fixture
def cv_llm(monkeypatch):
    llm = FakeCvLLM()
    monkeypatch.setattr(svc, "get_cv_llm", lambda: llm)
    monkeypatch.setattr(svc, "get_job_tool", lambda: FakeJobTool())
    return llm


def _confirm_form(draft: dict, confirm: bool) -> dict:
    return {
        "name": draft["name"], "degree": draft["degree"], "institution": draft["institution"],
        "year": draft["year"], "email": "jordan@example.com", "technical_skills": draft["technical_skills"],
        "target_roles": draft["target_roles"], "summary": draft["summary"], "achievements": [],
        "experience": [], "projects": draft["projects"], "confirm": confirm,
    }


def build_through_cv(client) -> dict:
    """Intro -> follow-up -> project review -> confirm -> jobs -> requirements -> CV."""
    b = client.post("/api/cv-builds", json={"intro": INTRO}).json()
    assert b["stage"] == "followup" and b["phase"] == "intake"
    assert b["pending_question"] == "Which institution do you study at?"

    b = client.post(f"/api/cv-builds/{b['id']}/reply", json={"text": "I study at UTS."}).json()
    assert b["phase"] == "review" and b["review_checked"] is False and b["pending_question"] is None

    b = client.post(f"/api/cv-builds/{b['id']}/review/start").json()
    assert b["review_checked"] and b["pending_question"] == "When did you build the Timetable API?"

    b = client.post(f"/api/cv-builds/{b['id']}/reply", json={"text": "March to May 2024."}).json()
    assert b["stage"] == "confirm"
    assert b["draft"]["projects"][0]["start_date"] == "March 2024"
    assert [m["role"] for m in b["conversation"]] == ["user", "agent", "user", "agent", "user"]
    assert [m["phase"] for m in b["conversation"]][-2:] == ["review", "review"]

    b = client.put(f"/api/cv-builds/{b['id']}/profile", json=_confirm_form(b["draft"], confirm=True)).json()
    assert b["stage"] == "jobs" and [m["document_id"] for m in b["job_matches"]] == JOB_IDS
    assert b["job_matches"][0]["location"]  # from jobs.jsonl
    assert b["draft"]["projects"][0]["start_date"] == "March 2024"  # the form doesn't drop dates

    b = client.post(f"/api/cv-builds/{b['id']}/job", json={"job_id": JOB_IDS[0]}).json()
    assert b["stage"] == "requirements" and "Docker" in b["requirement_question"]

    b = client.post(f"/api/cv-builds/{b['id']}/requirements",
                    json={"text": "Yes, I used Docker for the timetable API."}).json()
    assert b["stage"] == "cv" and b["cv"] is None
    assert b["last_resolution"]["confirmed_skills"] == ["Docker"]
    assert b["last_resolution"]["declined"] == ["Kubernetes"]
    stored = client.get(f"/api/cv-builds/{b['id']}").json()["draft"]  # saved, not just returned
    assert "Docker" in stored["technical_skills"]
    assert stored["declined_requirements"] == ["Kubernetes"]

    b = client.post(f"/api/cv-builds/{b['id']}/cv").json()
    assert b["cv"]["target_job_document_id"] == JOB_IDS[0]
    return b


def test_full_build_flow(client, cv_llm):
    b = build_through_cv(client)
    cv = b["cv"]
    # The A1 grounding safety net still runs: Rust isn't in the profile.
    assert "Rust" not in cv["skills"] and any("Rust" in w for w in cv["grounding_warnings"])
    assert cv["matched_skills"] == ["Python", "Docker"]

    b = client.patch(f"/api/cv-builds/{b['id']}/cv",
                     json={"summary": "Edited summary.", "projects": ["Edited project line."]}).json()
    assert b["cv"]["summary"] == "Edited summary."
    assert b["cv"]["projects"][0]["description"] == "Edited project line."

    pdf = client.get(f"/api/cv-builds/{b['id']}/cv.pdf")
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    assert pdf.headers["content-disposition"].startswith("inline")
    assert "Jordan_Ramirez_cv.pdf" in client.get(f"/api/cv-builds/{b['id']}/cv.pdf?download=1").headers["content-disposition"]

    listed = {x["id"]: x for x in client.get("/api/cv-builds").json()}
    assert listed[b["id"]]["has_cv"] and listed[b["id"]]["name"] == "Jordan Ramirez"
    assert listed[b["id"]]["job_description"].startswith(svc.load_jobs()[JOB_IDS[0]]["title"])


def test_wrong_stage_and_missing_build(client, cv_llm):
    b = client.post("/api/cv-builds", json={"intro": INTRO}).json()
    assert client.post(f"/api/cv-builds/{b['id']}/cv").status_code == 409
    assert client.get("/api/cv-builds/nope").status_code == 404


def test_llm_failure_leaves_build_unchanged(client, cv_llm, monkeypatch):
    import httpx

    b = client.post("/api/cv-builds", json={"intro": INTRO}).json()

    def down(*_a, **_k):
        raise httpx.ConnectError("refused")

    monkeypatch.setattr(cv_llm, "extract_json", down)
    res = client.post(f"/api/cv-builds/{b['id']}/reply", json={"text": "I study at UTS."})
    assert res.status_code == 503 and "ollama serve" in res.json()["detail"]
    after = client.get(f"/api/cv-builds/{b['id']}").json()
    assert after["pending_question"] == b["pending_question"] and after["conversation"] == b["conversation"]


def test_agent_state_survives_rebuild(cv_llm):
    """The full ProfileAgent state round-trips through the database row."""
    agent = ProfileAgent(cv_llm, step_cap=svc.STEP_CAP, review_step_cap=svc.REVIEW_STEP_CAP)
    agent.take_turn(INTRO)
    with SessionLocal() as db:
        build = CvBuild()
        svc.save_agent(build, agent)
        db.add(build)
        db.commit()
        build_id = build.id

    with SessionLocal() as db:  # fresh session, as after a server restart
        rebuilt = svc.restore_agent(db.get(CvBuild, build_id), cv_llm)
    assert rebuilt.tool.read_profile() == agent.tool.read_profile()
    assert (rebuilt.step, rebuilt.review_step, rebuilt._last_question) == (agent.step, agent.review_step, agent._last_question)
    assert rebuilt.trace == agent.trace

    rebuilt.take_turn("I study at UTS.")
    sent = json.loads(cv_llm.calls[-2]["user"])  # the extraction call (the summary call follows it)
    assert sent["last_question_asked"] == "Which institution do you study at?"
    assert sent["current_draft"]["name"] == "Jordan Ramirez"
    assert rebuilt.tool.read_profile()["draft"]["institution"] == "UTS"


def test_step_limit_goes_to_the_confirm_form(client, cv_llm, monkeypatch):
    monkeypatch.setattr(svc, "STEP_CAP", 1)
    b = client.post("/api/cv-builds", json={"intro": INTRO}).json()
    assert b["stage"] == "confirm" and b["ended_at_step_limit"] and b["pending_question"] is None
    assert b["draft"]["name"] == "Jordan Ramirez"  # what was captured is on the form
    assert not any(c["system"] == SUMMARY_SYSTEM_PROMPT for c in cv_llm.calls)  # no extra model call


def test_answered_field_is_not_reported_missing_again():
    """Seen live: year was captured, yet the model kept flagging it until intake ran out of steps."""
    from app.cv_builder.profile_model import DraftProfile

    d = DraftProfile(name="Norapat", year="final year")
    gaps = d.compute_gaps([
        {"field": "year", "issue": "missing", "reason": "Year of study not specified"},
        {"field": "institution", "issue": "missing", "reason": "Which university?"},
        {"field": "degree", "issue": "missing", "reason": "Degree level missing"},
    ])
    assert [g["field"] for g in gaps] == ["degree", "institution"]


def test_start_practice_creates_linked_session(client, cv_llm):
    b = build_through_cv(client)
    res = client.post(f"/api/cv-builds/{b['id']}/practice", json={})
    assert res.status_code == 201, res.text
    s = res.json()
    job = svc.load_jobs()[JOB_IDS[0]]
    assert s["cv_build_id"] == b["id"]
    assert s["cv_builder_context"] == {
        "job_title": job["title"], "matched_skills": ["Python", "Docker"],
        "missing_requirements": ["Kubernetes", "Model deployment on AWS"],
        "summary": "Computing Science student building backend services in Python.",
    }
    assert s["job_description"].startswith(job["title"]) and job["description"].strip() in s["job_description"]
    assert "Jordan Ramirez" in s["cv_text"]  # parsed back from the rendered PDF
    with SessionLocal() as db:
        assert Path(db.get(InterviewSession, s["id"]).cv_path).read_bytes().startswith(b"%PDF")

    # The setup page's "Use a CV I built" path, with an edited job description
    s2 = client.post(f"/api/cv-builds/{b['id']}/practice",
                     json={"job_description": "Backend Developer. Python, SQL and Docker required."}).json()
    assert s2["job_description"] == "Backend Developer. Python, SQL and Docker required."
    assert s2["cv_builder_context"]["job_title"] == job["title"]


DISTINCT_QUESTIONS = [
    "How would you get up to speed with container orchestration in your first month?",
    "Tell me about a time you disagreed with a teammate over a design.",
    "Walk me through the hardest bug in your timetable API.",
    "How do you decide between SQL and NoSQL storage for a new service?",
    "What would you monitor after deploying a model to production?",
]


class RecordingQuestionLLM:
    def __init__(self):
        self.user = ""
        self.asked = 0

    def chat_json(self, system, user, model, **_):
        self.user = user
        n = user.count("type=")
        qs = [{"question": DISTINCT_QUESTIONS[self.asked + i], "type": "technical", "difficulty": "medium",
               "points_a_strong_answer_would_mention": ["a", "b", "c"], "cv_evidence": []} for i in range(n)]
        self.asked += n
        return LLMResult(model.model_validate({"questions": qs}), 10, 100, 50, 1)


def test_question_generation_uses_cv_builder_context(client, cv_llm):
    b = build_through_cv(client)
    session_id = client.post(f"/api/cv-builds/{b['id']}/practice", json={}).json()["id"]
    llm = RecordingQuestionLLM()
    with SessionLocal() as db:
        out = question_gen.generate_questions(db, llm, session_id, 3)
    assert "CV BUILDER NOTES" in llm.user
    assert "Skills on the CV that match this role: Python, Docker." in llm.user
    assert 'Gap question about "Kubernetes"' in llm.user
    assert "Kubernetes" in [q.focus for q in out.questions]  # stored, so the next batch moves on

    # "Generate more" moves on to the next unprobed gap
    with SessionLocal() as db:
        question_gen.generate_questions(db, llm, session_id, 2)
    assert 'Gap question about "Model deployment on AWS"' in llm.user


def test_uploaded_cv_sessions_get_the_old_prompt(client):
    with SessionLocal() as db:
        s = InterviewSession(cv_filename="cv.pdf", cv_text="- Led migration of the ledger to Kafka at PayLoop\n" * 2,
                             job_description="- Strong PostgreSQL skills and data modelling experience")
        db.add(s)
        db.commit()
        sid = s.id
    llm = RecordingQuestionLLM()
    with SessionLocal() as db:
        question_gen.generate_questions(db, llm, sid, 3)
    assert "CV BUILDER" not in llm.user and "Gap question" not in llm.user
    with SessionLocal() as db:
        assert db.get(InterviewSession, sid).cv_build_id is None


def test_prefer_matched_orders_cv_items():
    items = ["Built a Rust CLI for parsing logs quickly", "Built a Flask API used by 50 students daily"]
    assert question_gen.prefer_matched(items, ["flask"])[0].startswith("Built a Flask")
    assert not question_gen.mentions_any("Used Javascript", ["Java"])  # whole words only


def test_retention_cleanup_deletes_old_builds(client, cv_llm):
    settings = get_settings()
    b = build_through_cv(client)
    client.get(f"/api/cv-builds/{b['id']}/cv.pdf")  # render it
    session_id = client.post(f"/api/cv-builds/{b['id']}/practice", json={}).json()["id"]
    with SessionLocal() as db:
        pdf = Path(db.get(CvBuild, b["id"]).pdf_path)
        assert pdf.exists()

    later = datetime.now(timezone.utc) + timedelta(days=settings.audio_retention_days + 1)
    result = run_cleanup(settings, now=later)
    assert result["cv_builds"] >= 1
    with SessionLocal() as db:
        assert db.get(CvBuild, b["id"]) is None
        assert db.get(InterviewSession, session_id) is None
    assert not pdf.exists()
    assert client.get(f"/api/cv-builds/{b['id']}").status_code == 404


def test_profile_form_collapses_whitespace_and_drops_duplicates():
    from app.schemas.api import ProfileEdit

    title = "Australia Import and Export Data Visualization and Analysis"
    edit = ProfileEdit(
        name="Jordan",
        projects=[{"title": f"{title}\t\t\t\t\tOct. 2025", "technologies": ["Tableau"]},
                  {"title": f"{title.lower()} Oct. 2025", "technologies": ["Tableau"]},
                  {"title": "   "}],
        experience=[{"role": "Analyst", "organisation": "Accenture"},
                    {"role": "analyst", "organisation": "accenture"},
                    {"role": "Intern", "organisation": "Accenture"}],
    )
    fields = edit.fields()
    assert [p["title"] for p in fields["projects"]] == [f"{title} Oct. 2025"]
    assert [(e["role"], e["organisation"]) for e in fields["experience"]] == [("Analyst", "Accenture"), ("Intern", "Accenture")]


def test_reopen_profile_resets_job_and_cv(client, cv_llm):
    b = build_through_cv(client)
    b = client.post(f"/api/cv-builds/{b['id']}/profile/reopen").json()
    assert b["stage"] == "confirm" and b["cv"] is None and b["selected_job"] is None and b["job_matches"] == []
    assert "Docker" in b["draft"]["technical_skills"]  # confirmed facts stay
    form = _confirm_form(b["draft"], confirm=True)
    form["projects"] = form["projects"] * 2  # the duplicate from the form is dropped on save
    b = client.put(f"/api/cv-builds/{b['id']}/profile", json=form).json()
    assert b["stage"] == "jobs" and len(b["draft"]["projects"]) == 1
    assert client.post(f"/api/cv-builds/{b['id']}/profile/reopen").status_code == 200
    assert client.post(f"/api/cv-builds/{b['id']}/profile/reopen").status_code == 409  # already there


def test_cv_summary_prompt_asks_for_first_person():
    assert "FIRST PERSON" in CV_GENERATION_SYSTEM_PROMPT and "never assume one" in CV_GENERATION_SYSTEM_PROMPT
    assert "gendered word" in SUMMARY_SYSTEM_PROMPT
