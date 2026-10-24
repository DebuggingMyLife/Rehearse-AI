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
from .routers import attempts, cv_builds, health, questions, sessions
from .services.cleanup import cleanup_loop
from .services.llm import check_cv_builder_llm, check_ollama
from .services.pipeline import process_attempt
from .services.transcription import load_transcriber

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger("rehearseai")


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
    cv_status = check_cv_builder_llm(settings)
    if cv_status.ok:
        log.info("CV Builder model OK (%s, %s)", cv_status.backend, cv_status.model)
    else:
        log.warning("CV Builder model check failed: %s Fix: %s", cv_status.error, cv_status.fix)

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
    # Privacy retention: delete old sessions now and every few hours.
    background.add(asyncio.create_task(cleanup_loop(settings)))
    yield
    for task in background:
        task.cancel()
    worker.shutdown()


app = FastAPI(title="RehearseAI", lifespan=lifespan)
app.include_router(health.router)
app.include_router(sessions.router)
app.include_router(questions.router)
app.include_router(attempts.router)
app.include_router(cv_builds.router)
