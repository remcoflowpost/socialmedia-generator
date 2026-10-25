"""De publisher. Elke stap is een korte eigen transactie; de netwerkcall gebeurt buiten
elke transactie. Garanties (docs/publiceren.md, "Exactly-once bij Meta"):

* een publicatie wordt door hooguit één worker tegelijk geclaimd (SKIP LOCKED + lease);
* elke netwerkcall wordt voorafgegaan door een onveranderlijke poging;
* een container-id wordt vastgelegd zodra het bestaat;
* na een onzekere uitkomst wordt eerst gezocht of de post al online staat;
* alle publicatieregels worden vlak voor verzenden opnieuw gecontroleerd.
"""

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, func, select, text, update
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import Post, PostVersion, Publication, PublishAttempt, SocialAccount
from app.publishing.providers import ProviderError, Published, get_provider
from app.publishing.retry import (
    LEASE_SECONDS,
    MAX_AUTO_ATTEMPTS,
    MISSED_WINDOW_SECONDS,
    backoff_seconds,
    classify,
    failure_message,
)
from app.publishing.rules import check_publishable
from app.publishing.service import account_creds, facts_for, mark_reauth, public_media_url

log = logging.getLogger("publisher")


@dataclass
class TickSummary:
    missed: int = 0
    reclaimed: int = 0
    claimed: int = 0
    published: int = 0
    failed: int = 0
    retrying: int = 0


def publish_due(now: datetime | None = None, limit: int = 10) -> TickSummary:
    now = now or datetime.now(UTC)
    summary = TickSummary()
    with SessionLocal() as session:
        summary.missed = _fail_missed(session, now)
        summary.reclaimed = _reclaim_expired(session, now)
        claimed = _claim(session, now, limit)
    summary.claimed = len(claimed)
    for publication_id, attempt_id in claimed:
        outcome = _publish_one(publication_id, attempt_id, now)
        setattr(summary, outcome, getattr(summary, outcome) + 1)
    return summary


def _fail_missed(session: Session, now: datetime) -> int:
    cutoff = now - timedelta(seconds=MISSED_WINDOW_SECONDS)
    result = session.execute(
        update(Publication)
        .where(
            Publication.status == "scheduled",
            func.coalesce(Publication.next_attempt_at, Publication.scheduled_at) < cutoff,
        )
        .values(
            status="failed",
            failure_code="missed_window",
            failure_message=failure_message("missed_window", None, None),
            failure_retryable=True,
            next_attempt_at=None,
            version=Publication.version + 1,
            updated_at=now,
        )
    )
    session.commit()
    return result.rowcount or 0


def _reclaim_expired(session: Session, now: datetime) -> int:
    stuck = session.scalars(
        select(Publication)
        .where(Publication.status == "publishing", Publication.lease_expires_at < now)
        .limit(20)
    ).all()
    for publication in stuck:
        session.execute(
            update(PublishAttempt)
            .where(
                PublishAttempt.publication_id == publication.id,
                PublishAttempt.outcome == "in_progress",
            )
            .values(
                outcome="uncertain",
                finished_at=now,
                error_code="timeout",
                retryable=True,
                provider_message="Worker stopte voordat het resultaat was vastgelegd.",
            )
        )
        budget_left = publication.attempt_count - publication.retry_base < MAX_AUTO_ATTEMPTS
        session.execute(
            update(Publication)
            .where(
                Publication.id == publication.id,
                Publication.status == "publishing",
                Publication.attempt_count == publication.attempt_count,
            )
            .values(
                status="scheduled" if budget_left else "failed",
                lease_expires_at=None,
                next_attempt_at=now if budget_left else None,
                failure_code="timeout" if budget_left else "uncertain",
                failure_message=failure_message(
                    "timeout" if budget_left else "uncertain", None, None
                ),
                failure_retryable=True,
                version=Publication.version + 1,
                updated_at=now,
            )
        )
        log.warning("verlopen lease teruggezet", extra={"publication": publication.id})
    session.commit()
    return len(stuck)


def _claim(session: Session, now: datetime, limit: int) -> list[tuple[str, str]]:
    rows = session.execute(
        text(
            """
            WITH due AS (
              SELECT p.id FROM publications p
              JOIN social_accounts a ON a.id = p.social_account_id
              WHERE p.status = 'scheduled'
                AND p.scheduled_at <= :now
                AND (p.next_attempt_at IS NULL OR p.next_attempt_at <= :now)
                AND a.status = 'active'
              ORDER BY coalesce(p.next_attempt_at, p.scheduled_at)
              LIMIT :limit
              FOR UPDATE OF p SKIP LOCKED
            )
            UPDATE publications SET
              status = 'publishing',
              lease_expires_at = :lease,
              attempt_count = publications.attempt_count + 1,
              first_attempt_at = coalesce(publications.first_attempt_at, :now),
              version = publications.version + 1,
              updated_at = :now
            FROM due WHERE publications.id = due.id
            RETURNING publications.id
            """
        ),
        {"now": now, "limit": limit, "lease": now + timedelta(seconds=LEASE_SECONDS)},
    ).all()
    claimed = []
    for (publication_id,) in rows:
        publication = session.get(Publication, publication_id)
        if publication.attempt_count == 1:
            trigger = "schedule"
        elif publication.attempt_count == publication.retry_base + 1:
            trigger = "manual_retry"
        else:
            trigger = "auto_retry"
        attempt = PublishAttempt(
            publication_id=publication.id,
            company_id=publication.company_id,
            social_account_id=publication.social_account_id,
            attempt_no=publication.attempt_count,
            trigger=trigger,
            idempotency_key=publication.idempotency_key,
            correlation_id=str(uuid.uuid4()),
            started_at=now,
            container_id=publication.provider_container_id,
        )
        session.add(attempt)
        session.flush()
        claimed.append((publication.id, attempt.id))
    session.commit()
    return claimed


def _publish_one(publication_id: str, attempt_id: str, now: datetime) -> str:
    with SessionLocal() as session:
        publication = session.get(Publication, publication_id)
        account = session.get(SocialAccount, publication.social_account_id)
        attempt = session.get(PublishAttempt, attempt_id)
        attempt_no = publication.attempt_count
        try:
            if account.status != "active":
                _release_paused(session, publication, attempt, now)
                return "retrying"
            _assert_still_publishable(session, publication, account, now)
            provider = get_provider(account.provider)
            creds = account_creds(account)

            if _had_uncertain(session, publication.id):
                found = provider.reconcile(
                    creds,
                    caption=publication.caption,
                    since=publication.first_attempt_at or publication.scheduled_at or now,
                    container_id=publication.provider_container_id,
                )
                if found:
                    _succeed(
                        session, publication, attempt, found, "Al online gevonden bij controle."
                    )
                    return "published"

            def remember_container(container_id: str) -> None:
                # Eigen transactie: het id moet vastliggen voordat er gepubliceerd wordt.
                with SessionLocal() as side:
                    side.execute(
                        update(Publication)
                        .where(Publication.id == publication.id)
                        .values(provider_container_id=container_id)
                    )
                    side.commit()

            result = provider.publish(
                creds,
                media_url=public_media_url(publication),
                caption=publication.caption,
                format_key=publication.format_key,
                existing_container_id=publication.provider_container_id,
                on_container=remember_container,
            )
            session.refresh(publication)
            _succeed(session, publication, attempt, result, None)
            log.info("gepubliceerd", extra={"publication": publication.id})
            return "published"
        except ProviderError as error:
            session.rollback()
            return _fail(session, publication_id, attempt_id, attempt_no, account, error, now)
        except Exception as error:  # noqa: BLE001 - elke fout hoort in de log van de poging
            session.rollback()
            log.exception("onverwachte fout bij publiceren")
            wrapped = ProviderError(
                "unknown", "Onverwachte fout.", provider_message=str(error)[:200]
            )
            return _fail(session, publication_id, attempt_id, attempt_no, account, wrapped, now)


def _assert_still_publishable(
    session: Session, publication: Publication, account: SocialAccount, now: datetime
) -> None:
    """Goedkeuring, embargo, export en account kunnen veranderd zijn sinds het inplannen."""
    post = session.get(Post, publication.post_id)
    version = session.get(PostVersion, publication.post_version_id)
    facts, _ = facts_for(
        session,
        account=account,
        post=post,
        version=version,
        format_key=publication.format_key,
        caption=publication.caption,
        scheduled_at=max(now, publication.scheduled_at or now),
        now=now,
        media_key=publication.media_key,
    )
    facts.published_last_24h = 0  # telt niet als blokkade voor iets dat al gepland stond
    issues = check_publishable(facts, at_send_time=True)
    if issues:
        raise ProviderError(
            "not_publishable",
            "Niet verstuurd.",
            provider_message="; ".join(i.message for i in issues)[:300],
        )


def _had_uncertain(session: Session, publication_id: str) -> bool:
    return bool(
        session.scalar(
            select(func.count())
            .select_from(PublishAttempt)
            .where(
                PublishAttempt.publication_id == publication_id,
                PublishAttempt.outcome == "uncertain",
            )
        )
    )


def _succeed(
    session: Session,
    publication: Publication,
    attempt: PublishAttempt,
    result: Published,
    note: str | None,
) -> None:
    now = datetime.now(UTC)
    session.execute(
        update(PublishAttempt)
        .where(PublishAttempt.id == attempt.id, PublishAttempt.outcome == "in_progress")
        .values(
            outcome="succeeded",
            finished_at=now,
            provider_post_id=result.post_id,
            provider_url=result.url,
            container_id=result.container_id or publication.provider_container_id,
            provider_message=note,
        )
    )
    session.execute(
        update(Publication)
        .where(Publication.id == publication.id, Publication.status == "publishing")
        .values(
            status="published",
            published_at=now,
            provider_post_id=result.post_id,
            provider_url=result.url,
            provider_container_id=result.container_id or publication.provider_container_id,
            lease_expires_at=None,
            next_attempt_at=None,
            failure_code=None,
            failure_message=None,
            failure_retryable=None,
            version=Publication.version + 1,
            updated_at=now,
        )
    )
    session.commit()


def _release_paused(
    session: Session, publication: Publication, attempt: PublishAttempt, now: datetime
) -> None:
    """Account werd gepauzeerd nadat deze batch was geclaimd: niets versturen, terugzetten
    zonder het retrybudget te verbruiken."""
    session.execute(
        update(PublishAttempt)
        .where(PublishAttempt.id == attempt.id, PublishAttempt.outcome == "in_progress")
        .values(
            outcome="failed",
            finished_at=now,
            error_code="channel_paused",
            retryable=False,
            provider_message="Overgeslagen: account gepauzeerd tot het opnieuw is gekoppeld.",
        )
    )
    session.execute(
        update(Publication)
        .where(Publication.id == publication.id, Publication.status == "publishing")
        .values(
            status="scheduled",
            lease_expires_at=None,
            retry_base=Publication.attempt_count,
            version=Publication.version + 1,
            updated_at=now,
        )
    )
    session.commit()


def _fail(
    session: Session,
    publication_id: str,
    attempt_id: str,
    attempt_no: int,
    account: SocialAccount,
    error: ProviderError,
    now: datetime,
) -> str:
    publication = session.get(Publication, publication_id)
    cls = classify(error.code)
    will_retry = cls.retryable and attempt_no - publication.retry_base < MAX_AUTO_ATTEMPTS
    final_after = None if will_retry else attempt_no - publication.retry_base
    message = failure_message(error.code, error.provider_message, final_after)
    session.execute(
        update(PublishAttempt)
        .where(PublishAttempt.id == attempt_id, PublishAttempt.outcome == "in_progress")
        .values(
            outcome="uncertain" if cls.uncertain else "failed",
            finished_at=now,
            error_code=error.code,
            retryable=cls.retryable,
            http_status=error.http_status,
            provider_message=(error.provider_message or error.message)[:500],
        )
    )
    if error.code == "auth":
        mark_reauth(session, account.id, error.provider_message or error.message)
    values = {
        "lease_expires_at": None,
        "failure_code": error.code,
        "failure_message": message,
        "version": Publication.version + 1,
        "updated_at": now,
    }
    if will_retry:
        values |= {
            "status": "scheduled",
            "failure_retryable": True,
            "next_attempt_at": now
            + timedelta(seconds=backoff_seconds(attempt_no + 1, error.retry_after)),
        }
    else:
        values |= {
            "status": "failed",
            "failure_retryable": cls.retryable or cls.uncertain or error.code == "auth",
            "next_attempt_at": None,
        }
    session.execute(
        update(Publication)
        .where(
            and_(
                Publication.id == publication_id,
                Publication.status == "publishing",
                Publication.attempt_count == attempt_no,
            )
        )
        .values(**values)
    )
    session.commit()
    log.info(
        "publicatiepoging mislukt",
        extra={"publication": publication_id, "code": error.code, "retry": will_retry},
    )
    return "retrying" if will_retry else "failed"
