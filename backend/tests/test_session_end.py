from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.config import get_settings
from app.db import SessionLocal
from app.models import Attempt, InterviewSession
from app.routers import sessions as sessions_router
from app.services.cleanup import run_cleanup
from app.services.llm import LLMResult
from tests.test_evaluation import fake_llm  # noqa: F401  (fixture)
from tests.test_pipeline import run

SUMMARY = {
    "recurring_strengths": ["You name concrete projects."],
    "recurring_weaknesses": ["You rarely state measurable results."],
    "top_priorities": [
        {"title": "Quantify outcomes", "why": "Q1 lacked results.", "how_to_practise": "Add one number per answer."},
        {"title": "Explain decisions", "why": "Q1.", "how_to_practise": "Say why, not just what."},
    ],
    "overall": "Solid base; make results explicit.",
}


class SummaryLLM:
    def __init__(self):
        self.user = ""

    def chat_json(self, system, user, model, **_):
        self.user = user
        return LLMResult(model.model_validate(SUMMARY), 10, 100, 50, 1)


def session_of(question_id: int) -> str:
    from app.models import Question

    with SessionLocal() as db:
        return db.get(Question, question_id).session_id


def test_end_session_requires_a_scored_answer(client, question_id):
    res = client.post(f"/api/sessions/{session_of(question_id)}/end")
    assert res.status_code == 422 and "Answer at least one question" in res.json()["detail"]


def test_end_session_summary_and_stats(client, question_id, fake_llm, monkeypatch):  # noqa: F811
    fake_llm()
    run(client, question_id)
    run(client, question_id)
    llm = SummaryLLM()
    monkeypatch.setattr(sessions_router, "get_llm", lambda: llm)
    sid = session_of(question_id)

    s = client.post(f"/api/sessions/{sid}/end").json()
    assert s["status"] == "ended" and s["ended_at"]
    summary = s["summary"]
    assert summary["top_priorities"][0]["title"] == "Quantify outcomes"
    stats = summary["stats"]
    assert stats["questions_answered"] == 1 and stats["attempts_scored"] == 2
    assert stats["avg_best_score"] == 4.0
    assert stats["delivery"]["avg_wpm"] > 0
    # The prompt gets per-question results and measured delivery, not transcripts.
    assert "scores in order: 4, 4" in llm.user and "Average pace:" in llm.user
    assert "PayLoop I led" not in llm.user


def test_pdf_export(client, question_id, fake_llm):  # noqa: F811
    fake_llm()
    run(client, question_id)
    res = client.get(f"/api/sessions/{session_of(question_id)}/export.pdf")
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/pdf"
    assert res.content.startswith(b"%PDF") and len(res.content) > 2000
    assert "attachment" in res.headers["content-disposition"]


def test_pdf_export_with_no_answers(client, question_id):
    res = client.get(f"/api/sessions/{session_of(question_id)}/export.pdf")
    assert res.status_code == 200 and res.content.startswith(b"%PDF")


@pytest.fixture
def old_and_new_sessions(client, question_id):
    """Two sessions with CV + audio files; one backdated past the retention window."""
    from tests.test_attempts import upload

    settings = get_settings()
    ids = {}
    for label, age_days in (("old", settings.audio_retention_days + 1), ("new", 0)):
        sid = session_of(question_id) if label == "new" else None
        with SessionLocal() as db:
            if sid is None:
                s = InterviewSession(cv_filename="cv.pdf", cv_text="x" * 100, job_description="y" * 50)
                db.add(s)
                db.flush()
                sid = s.id
            s = db.get(InterviewSession, sid)
            cv = settings.cv_dir / f"{sid}.pdf"
            cv.write_bytes(b"%PDF cv")
            s.cv_path = str(cv)
            s.created_at = datetime.now(timezone.utc) - timedelta(days=age_days)
            db.commit()
        ids[label] = sid
    upload(client, question_id)  # audio for the "new" session
    return ids


def test_cleanup_deletes_only_expired_sessions_and_their_files(old_and_new_sessions):
    settings = get_settings()
    old, new = old_and_new_sessions["old"], old_and_new_sessions["new"]
    with SessionLocal() as db:
        new_audio = [a.audio_path for q in db.get(InterviewSession, new).questions for a in q.attempts]
    orphan = settings.audio_dir / "99999.webm"
    orphan.write_bytes(b"x")

    result = run_cleanup(settings)
    assert result["sessions"] >= 1
    with SessionLocal() as db:
        assert db.get(InterviewSession, old) is None
        assert db.get(InterviewSession, new) is not None
    assert not (settings.cv_dir / f"{old}.pdf").exists()
    assert (settings.cv_dir / f"{new}.pdf").exists()
    assert all(Path(p).exists() for p in new_audio)
    assert orphan.exists()  # recent orphan files are kept until they're past retention too

    # A week later, everything (including the orphan) is past retention.
    later = datetime.now(timezone.utc) + timedelta(days=settings.audio_retention_days + 2)
    import os
    os.utime(orphan, (later.timestamp() - 10**7, later.timestamp() - 10**7))
    run_cleanup(settings, now=later)
    with SessionLocal() as db:
        assert db.get(InterviewSession, new) is None
        assert db.query(Attempt).filter(Attempt.audio_path.in_(new_audio)).count() == 0
    assert not orphan.exists()
    assert not any(Path(p).exists() for p in new_audio)
