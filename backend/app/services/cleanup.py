"""Privacy retention: delete sessions (CV, audio, transcripts, feedback) and CV Builder builds
(profile, conversation, generated CV and PDF) older than AUDIO_RETENTION_DAYS, plus any upload
files no longer referenced by the database."""

import logging
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import select

from ..config import Settings
from ..db import SessionLocal
from ..models import Attempt, CvBuild, InterviewSession

log = logging.getLogger(__name__)

CLEANUP_INTERVAL_S = 6 * 60 * 60


def _unlink(path: str | None) -> bool:
    if not path:
        return False
    try:
        Path(path).unlink(missing_ok=True)
        return True
    except OSError as exc:
        log.warning("Could not delete %s: %s", Path(path).name, exc)
        return False


def run_cleanup(settings: Settings, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=settings.audio_retention_days)
    deleted_sessions = deleted_builds = deleted_files = 0
    with SessionLocal() as db:
        # SQLite stores naive UTC; compare against a naive cutoff.
        old = db.scalars(select(InterviewSession).where(
            InterviewSession.created_at < cutoff.replace(tzinfo=None))).all()
        for s in old:
            deleted_files += _unlink(s.cv_path)
            for q in s.questions:
                for a in q.attempts:
                    deleted_files += _unlink(a.audio_path)
            db.delete(s)  # cascades to questions and attempts
            deleted_sessions += 1
        old_builds = db.scalars(select(CvBuild).where(CvBuild.created_at < cutoff.replace(tzinfo=None))).all()
        for b in old_builds:
            deleted_files += _unlink(b.pdf_path)
            db.delete(b)  # sessions started from it keep their own CV copy (cv_build_id -> NULL)
            deleted_builds += 1
        db.commit()

        # Orphans: files on disk with no DB row (e.g. a crash between write and commit),
        # once they're past the retention window too.
        known = {Path(p).name for p in db.scalars(select(InterviewSession.cv_path)) if p}
        known |= {Path(p).name for p in db.scalars(select(Attempt.audio_path)) if p}
        known |= {Path(p).name for p in db.scalars(select(CvBuild.pdf_path)) if p}
    cutoff_ts = cutoff.timestamp()
    for folder in (settings.cv_dir, settings.audio_dir, settings.cv_build_dir):
        if not folder.exists():
            continue
        for f in folder.iterdir():
            if f.is_file() and f.name not in known and f.stat().st_mtime < cutoff_ts:
                deleted_files += _unlink(str(f))

    if deleted_sessions or deleted_builds or deleted_files:
        log.info("Retention cleanup: deleted %d session(s), %d CV build(s) and %d file(s) older than %d day(s)",
                 deleted_sessions, deleted_builds, deleted_files, settings.audio_retention_days)
    return {"sessions": deleted_sessions, "cv_builds": deleted_builds, "files": deleted_files}


async def cleanup_loop(settings: Settings) -> None:
    """Run at startup and then periodically, off the event loop."""
    import asyncio

    while True:
        start = time.perf_counter()
        try:
            await asyncio.to_thread(run_cleanup, settings)
        except Exception:
            log.exception("Retention cleanup failed")
        await asyncio.sleep(max(60.0, CLEANUP_INTERVAL_S - (time.perf_counter() - start)))
