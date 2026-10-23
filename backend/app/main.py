import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .config import get_settings
from .db import init_db
from . import worker
from .routers import attempts, health, questions, sessions
from .services.llm import check_ollama

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
    yield
    worker.shutdown()


app = FastAPI(title="Retake", lifespan=lifespan)
app.include_router(health.router)
app.include_router(sessions.router)
app.include_router(questions.router)
app.include_router(attempts.router)
