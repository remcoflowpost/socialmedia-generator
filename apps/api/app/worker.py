"""Achtergrondworker: python -m app.worker

Claimt jobs uit de job-tabel en voert ze uit. Render-jobs gaan via HTTP naar de
render-service; de worker is de enige eigenaar van de wachtrij.
"""

import logging
import signal
import time
import traceback

from app.db import SessionLocal
from app.domain.export import export_version
from app.jobs.queue import claim_next, fail, finish, set_progress
from app.models import Job, Post, PostVersion

log = logging.getLogger("worker")
POLL_SECONDS = 1.0
running = True


def _stop(*_: object) -> None:
    global running
    running = False


def handle_export(session, job: Job) -> dict:
    payload = job.payload
    post = session.get(Post, payload["postId"])
    version = session.get(PostVersion, payload["versionId"])
    if not post or not version:
        raise ValueError("Post of versie bestaat niet meer.")
    return export_version(
        session,
        post,
        version,
        payload.get("formatKeys"),
        payload.get("type", "jpeg"),
        lambda progress: set_progress(session, job, progress),
    )


HANDLERS = {"export": handle_export}


def run_once() -> bool:
    with SessionLocal() as session:
        job = claim_next(session, list(HANDLERS))
        if not job:
            return False
        log.info("job %s (%s) gestart", job.id, job.type)
        try:
            result = HANDLERS[job.type](session, job)
        except Exception as error:  # noqa: BLE001 - elke fout moet in de job terechtkomen
            session.rollback()
            log.error("job %s mislukt: %s", job.id, error)
            fail(
                session,
                session.merge(job),
                f"{type(error).__name__}: {error}\n{traceback.format_exc(limit=3)}",
            )
            return True
        finish(session, job, result)
        log.info("job %s klaar", job.id)
        return True


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    log.info("worker gestart")
    while running:
        if not run_once():
            time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
