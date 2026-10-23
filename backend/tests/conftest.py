import os
import shutil
import tempfile

# Must run before any `app` import: point the DB and uploads at a throwaway directory
# so tests never touch backend/data. Env vars take priority over .env.
_TMP = tempfile.mkdtemp(prefix="retake-test-")
os.environ["DATA_DIR"] = _TMP

import pytest  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _cleanup_tmp():
    yield
    from app.db import engine

    engine.dispose()
    shutil.rmtree(_TMP, ignore_errors=True)


@pytest.fixture(scope="session")
def client():
    from fastapi.testclient import TestClient

    from app.config import get_settings
    from app.db import init_db
    from app.main import app
    from app.routers import attempts

    # Uploads normally queue transcription; tests drive the pipeline directly instead.
    attempts.schedule_processing = lambda attempt_id: None

    settings = get_settings()
    settings.cv_dir.mkdir(parents=True, exist_ok=True)
    settings.audio_dir.mkdir(parents=True, exist_ok=True)
    init_db()
    # No `with`: skip lifespan so tests don't depend on a running Ollama.
    return TestClient(app)


@pytest.fixture
def question_id(client):
    """A session with one stored question (no LLM call)."""
    from app.db import SessionLocal
    from app.models import Difficulty, InterviewSession, Question, QuestionType

    with SessionLocal() as db:
        s = InterviewSession(cv_filename="cv.pdf", cv_text="x" * 100, job_description="y" * 50)
        db.add(s)
        db.flush()
        q = Question(
            session_id=s.id, position=1, text="Tell me about a time you led a migration.",
            type=QuestionType.cv_specific, difficulty=Difficulty.medium,
            rubric=["Names the migration", "States the latency result"], cv_evidence=["Led migration"],
        )
        db.add(q)
        db.commit()
        return q.id
