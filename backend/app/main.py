import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

import asyncio

from sqlalchemy import select

from . import worker
from .config import get_settings
from .db import SessionLocal, init_db
from .events import bus
from .models import Attempt, AttemptStatus
from .routers import attempts, health, questions, sessions
from .services.llm import check_ollama
from .services.pipeline import process_attempt
from .services.transcription import load_transcriber

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger("retake")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    settings.cv_dir.mkdir(parents=True, exist_ok=True)
    settings.audio_dir.mkdir(parents=True, exist_ok=True)
    init_db()

    status = check_ollama(settings)
    if status.ok:
        log.info("Ollama OK at %s, model %s available", status.host, status.model)
    else:
        # Don't refuse to start: the UI shows the error and fix command via /api/health.
        log.error("Ollama check failed: %s Fix: %s", status.error, status.fix)

    bus.bind(asyncio.get_running_loop())
    # Load Whisper on the worker so startup isn't blocked; jobs queue behind it.
    background = {asyncio.create_task(worker.run_job(load_transcriber, settings))}
    # Resume attempts interrupted by a restart.
    with SessionLocal() as db:
        pending = db.scalars(select(Attempt).where(Attempt.status.in_(
            [AttemptStatus.uploaded, AttemptStatus.transcribing, AttemptStatus.analysing]))).all()
        for attempt in pending:
            attempt.status = AttemptStatus.uploaded
        db.commit()
        pending_ids = [a.id for a in pending]
    for attempt_id in pending_ids:
        background.add(asyncio.create_task(worker.run_job(process_attempt, attempt_id)))
    if pending_ids:
        log.info("Re-queued %d unfinished attempt(s)", len(pending_ids))
    yield
    worker.shutdown()


app = FastAPI(title="Retake", lifespan=lifespan)
app.include_router(health.router)
app.include_router(sessions.router)
app.include_router(questions.router)
app.include_router(attempts.router)
