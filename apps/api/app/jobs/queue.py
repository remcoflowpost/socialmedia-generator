"""Job-tabel als wachtrij. Geen Redis nodig voor vier gebruikers."""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Job

MAX_ATTEMPTS = 3


def enqueue(session: Session, job_type: str, payload: dict[str, Any], user_id: str | None) -> Job:
    job = Job(type=job_type, payload=payload, created_by=user_id)
    session.add(job)
    session.flush()
    return job


def claim_next(session: Session, types: list[str]) -> Job | None:
    """Pakt de oudste wachtende job en markeert hem als running. SKIP LOCKED zorgt dat
    meerdere workers elkaar niet in de weg zitten."""
    stmt = (
        select(Job)
        .where(Job.status == "queued", Job.type.in_(types))
        .order_by(Job.created_at)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    job = session.scalars(stmt).first()
    if not job:
        return None
    job.status = "running"
    job.attempts += 1
    job.started_at = datetime.now(UTC)
    session.commit()
    return job


def finish(session: Session, job: Job, result: dict[str, Any]) -> None:
    job.status = "done"
    job.result = result
    job.progress = 1
    job.finished_at = datetime.now(UTC)
    session.commit()


def fail(session: Session, job: Job, error: str) -> None:
    job.error = error
    job.finished_at = datetime.now(UTC)
    job.status = "queued" if job.attempts < MAX_ATTEMPTS and _retryable(error) else "failed"
    session.commit()


def _retryable(error: str) -> bool:
    return "ConnectError" in error or "timed out" in error


def set_progress(session: Session, job: Job, progress: float) -> None:
    job.progress = progress
    session.commit()
