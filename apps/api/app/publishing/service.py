"""Inplannen, verplaatsen, opnieuw proberen en accounts beheren. Alle wijzigingen die meer
dan één rij raken gebeuren hier in één transactie; regels komen uit rules.py."""

import hashlib
import hmac
import io
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import PurePosixPath

from PIL import Image
from psycopg.errors import ExclusionViolation
from sqlalchemy import func, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    Company,
    Job,
    Post,
    PostVersion,
    Publication,
    PublishSlot,
    SocialAccount,
    User,
)
from app.publishing import crypto
from app.publishing.providers import AccountCreds, ConnectableAccount, ProviderError, get_provider
from app.publishing.rules import PublishFacts, check_publishable, normalize_caption
from app.publishing.slots import (
    LocalTimeError,
    Slot,
    is_valid_timezone,
    next_open_slot,
    parse_time,
    resolve_local,
)
from app.settings import get_settings
from app.storage import get_storage

_MIME = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}


@dataclass
class Conflict:
    other_id: str
    other_version: int
    other_caption: str
    target: datetime


@dataclass
class ServiceError(Exception):
    message: str
    issues: list = field(default_factory=list)
    conflict: Conflict | None = None
    status: int = 422

    def __str__(self) -> str:
        return self.message


def _now() -> datetime:
    return datetime.now(UTC)


def _is_exclusion(error: Exception) -> bool:
    return isinstance(getattr(error, "orig", None), ExclusionViolation)


# ----------------------------------------------------------------------------- accounts


def account_creds(account: SocialAccount) -> AccountCreds:
    if not account.token_enc:
        raise ProviderError("auth", "Geen opgeslagen toegang; koppel het account opnieuw.")
    return AccountCreds(
        account.provider, account.external_id, crypto.decrypt(account.token_enc, account.id)
    )


def connect_accounts(
    session: Session, company: Company, user: User, found: list[ConnectableAccount]
) -> list[SocialAccount]:
    """Koppelt (of hernieuwt) accounts aan een bedrijf. Een bestaand actief of gepauzeerd
    account wordt bijgewerkt, niet gedupliceerd."""
    result = []
    for item in found:
        account = session.scalar(
            select(SocialAccount)
            .where(
                SocialAccount.company_id == company.id,
                SocialAccount.provider == item.provider,
                SocialAccount.external_id == item.external_id,
                SocialAccount.status != "disconnected",
            )
            .with_for_update()
        )
        if not account:
            # Id vooraf, zodat het token direct aan deze rij gebonden versleuteld kan worden.
            account = SocialAccount(
                id=str(uuid.uuid4()),
                company_id=company.id,
                provider=item.provider,
                external_id=item.external_id,
                connected_by=user.id,
            )
            session.add(account)
        account.name = item.name[:200]
        account.handle = item.handle[:200]
        account.token_enc = crypto.encrypt(item.token, account.id)
        account.token_expires_at = item.token_expires_at
        account.status = "active"
        account.status_reason = None
        account.last_checked_at = _now()
        account.updated_at = _now()
        result.append(account)
    session.commit()
    return result


def mark_reauth(session: Session, account_id: str, reason: str) -> None:
    session.execute(
        update(SocialAccount)
        .where(SocialAccount.id == account_id, SocialAccount.status == "active")
        .values(
            status="reauth_required",
            status_reason=reason[:300],
            last_checked_at=_now(),
            updated_at=_now(),
        )
    )


def check_account(session: Session, account: SocialAccount) -> tuple[bool, str]:
    if account.status == "disconnected":
        return False, "Dit account is ontkoppeld."
    try:
        get_provider(account.provider).verify(account_creds(account))
    except ProviderError as error:
        if error.code == "auth":
            mark_reauth(session, account.id, error.provider_message or error.message)
            session.commit()
            return False, "Toegang geweigerd. Koppel het account opnieuw."
        account.last_checked_at = _now()
        session.commit()
        return False, error.message
    account.status = "active"
    account.status_reason = None
    account.last_checked_at = _now()
    session.commit()
    return True, "Verbinding werkt."


def disconnect_account(session: Session, account: SocialAccount) -> int:
    """Wist tokens meteen en annuleert geplande publicaties. Geschiedenis blijft."""
    cancelled = session.execute(
        update(Publication)
        .where(
            Publication.social_account_id == account.id,
            Publication.status == "scheduled",
        )
        .values(
            status="cancelled",
            failure_message="Geannuleerd: account ontkoppeld.",
            version=Publication.version + 1,
            updated_at=_now(),
        )
    ).rowcount
    account.status = "disconnected"
    account.token_enc = None
    account.token_expires_at = None
    account.status_reason = "Ontkoppeld"
    account.updated_at = _now()
    session.commit()
    return cancelled or 0


# ----------------------------------------------------------------------------- slots & tz


def company_slots(session: Session, company_id: str) -> list[Slot]:
    rows = session.scalars(
        select(PublishSlot)
        .where(PublishSlot.company_id == company_id)
        .order_by(PublishSlot.weekday, PublishSlot.local_time)
    )
    return [Slot(r.weekday, r.local_time) for r in rows]


def set_timezone(session: Session, company: Company, zone: str) -> None:
    if not is_valid_timezone(zone):
        raise ServiceError("Kies een geldige tijdzone.")
    company.timezone = zone
    session.commit()


def add_slots(session: Session, company: Company, weekdays: list[int], local_time: str) -> int:
    parsed = parse_time(local_time)
    if not parsed:
        raise ServiceError("Vul een tijd in zoals 09:30.")
    days = sorted({d for d in weekdays if 1 <= d <= 7})
    if not days:
        raise ServiceError("Kies minstens één dag.")
    added = 0
    for day in days:
        exists = session.scalar(
            select(PublishSlot.id).where(
                PublishSlot.company_id == company.id,
                PublishSlot.weekday == day,
                PublishSlot.local_time == f"{parsed:%H:%M}",
            )
        )
        if not exists:
            session.add(
                PublishSlot(company_id=company.id, weekday=day, local_time=f"{parsed:%H:%M}")
            )
            added += 1
    session.commit()
    return added


# ----------------------------------------------------------------------------- approval


def approve(session: Session, post: Post, approved_by: str, version_number: int) -> None:
    """Legt klantakkoord vast voor één versie. Een nieuwere versie heeft opnieuw akkoord nodig."""
    exists = session.scalar(
        select(PostVersion.id).where(
            PostVersion.post_id == post.id, PostVersion.number == version_number
        )
    )
    if not exists:
        raise ServiceError("Die versie bestaat niet.")
    who = " ".join(approved_by.split())[:200]
    if not who:
        raise ServiceError("Vul in wie namens de klant akkoord gaf.")
    post.client_approved = True
    post.client_approved_by = who
    post.client_approved_at = _now()
    post.client_approved_version = version_number
    session.commit()


def revoke_approval(session: Session, post: Post) -> int:
    """Trekt akkoord in. Geplande publicaties blijven staan maar worden bij verzenden
    geweigerd (de regels worden dan opnieuw gecontroleerd)."""
    post.client_approved = False
    post.client_approved_version = None
    post.client_approved_at = None
    session.commit()
    return session.scalar(
        select(func.count())
        .select_from(Publication)
        .where(Publication.post_id == post.id, Publication.status == "scheduled")
    )


# ----------------------------------------------------------------------------- media


@dataclass
class ExportFile:
    key: str
    severity: str | None


def export_files(session: Session, version: PostVersion) -> dict[str, ExportFile]:
    """Geslaagde exportbestanden per formaat voor deze versie (laatste export wint)."""
    jobs = session.scalars(
        select(Job)
        .where(
            Job.type == "export",
            Job.status == "done",
            Job.payload["versionId"].astext == version.id,
        )
        .order_by(Job.finished_at)
    )
    files: dict[str, ExportFile] = {}
    for job in jobs:
        for entry in (job.result or {}).get("files", []):
            files[entry["formatKey"]] = ExportFile(entry["key"], entry.get("severity"))
    return files


@dataclass
class MediaFacts:
    mime: str | None
    size: int | None
    width: int | None
    height: int | None


def media_facts(key: str) -> MediaFacts:
    storage = get_storage()
    if not storage.exists(key):
        return MediaFacts(None, None, None, None)
    path = storage.local_path(key)
    mime = _MIME.get(PurePosixPath(key).suffix.lower())
    try:
        with Image.open(io.BytesIO(path.read_bytes())) as image:
            width, height = image.size
    except OSError:
        width = height = None
    return MediaFacts(mime, path.stat().st_size, width, height)


def media_signature(publication_id: str, expires: int) -> str:
    secret = get_settings().session_secret.encode()
    return hmac.new(
        secret, f"media:{publication_id}:{expires}".encode(), hashlib.sha256
    ).hexdigest()


def public_media_url(publication: Publication) -> str:
    """Kortlevende publieke URL voor dit ene bestand; Instagram haalt het beeld zelf op."""
    settings = get_settings()
    expires = int(time.time()) + settings.public_media_ttl_seconds
    sig = media_signature(publication.id, expires)
    return (
        f"{settings.public_url.rstrip('/')}/api/public/media/{publication.id}"
        f"?exp={expires}&sig={sig}"
    )


def verify_media_signature(publication_id: str, expires: str, sig: str) -> bool:
    if not expires.isdigit() or int(expires) < time.time():
        return False
    return hmac.compare_digest(sig, media_signature(publication_id, int(expires)))


# ----------------------------------------------------------------------------- facts


def published_last_24h(session: Session, account_id: str, now: datetime) -> int:
    return session.scalar(
        select(func.count())
        .select_from(Publication)
        .where(
            Publication.social_account_id == account_id,
            Publication.status == "published",
            Publication.published_at >= now - timedelta(hours=24),
        )
    )


def facts_for(
    session: Session,
    *,
    account: SocialAccount,
    post: Post,
    version: PostVersion,
    format_key: str,
    caption: str,
    scheduled_at: datetime,
    now: datetime,
    media_key: str | None = None,
) -> tuple[PublishFacts, str | None]:
    files = export_files(session, version)
    export = files.get(format_key)
    key = media_key or (export.key if export else None)
    media = media_facts(key) if key else MediaFacts(None, None, None, None)
    facts = PublishFacts(
        provider=account.provider,
        account_status=account.status,
        account_company_id=account.company_id,
        post_company_id=post.company_id,
        format_key=format_key,
        caption=caption,
        version_number=version.number,
        approved_version=post.client_approved_version if post.client_approved else None,
        embargo_until=post.embargo_until,
        export_ok=bool(export) and media.size is not None,
        export_severity=export.severity if export else None,
        media_mime=media.mime,
        media_bytes=media.size,
        media_width=media.width,
        media_height=media.height,
        scheduled_at=scheduled_at,
        now=now,
        published_last_24h=published_last_24h(session, account.id, now),
    )
    return facts, key


# ----------------------------------------------------------------------------- schedule


@dataclass
class Target:
    """Moment: volgende open slot, een lokale datum+tijd, of een exact instant."""

    kind: str  # "next_slot" | "local" | "instant"
    day: date | None = None
    at: str | None = None
    instant: datetime | None = None


def _occupied(session: Session, account_id: str, after: datetime, exclude: str | None) -> set:
    stmt = select(Publication.scheduled_at).where(
        Publication.social_account_id == account_id,
        Publication.status.in_(("scheduled", "publishing")),
        Publication.scheduled_at >= after,
    )
    if exclude:
        stmt = stmt.where(Publication.id != exclude)
    return set(session.scalars(stmt))


def resolve_target(
    session: Session, company: Company, account_id: str, target: Target, now: datetime, exclude=None
) -> datetime:
    if target.kind == "instant" and target.instant:
        instant = target.instant.astimezone(UTC)
        return instant.replace(second=0, microsecond=0)
    if target.kind == "local":
        parsed = parse_time(target.at or "")
        if not parsed or not target.day:
            raise ServiceError("Vul een datum en een tijd in.")
        try:
            return resolve_local(target.day, parsed, company.timezone, strict=True)
        except LocalTimeError as error:
            raise ServiceError(str(error)) from error
    slot = next_open_slot(
        company_slots(session, company.id),
        company.timezone,
        _occupied(session, account_id, now, exclude),
        now,
    )
    if not slot:
        raise ServiceError(
            "Geen open publicatietijd in de komende 8 weken voor dit account. Voeg tijden toe "
            "bij Planning of kies een specifiek moment."
        )
    return slot


def schedule(
    session: Session,
    user: User,
    *,
    post: Post,
    version: PostVersion,
    account_ids: list[str],
    format_by_provider: dict[str, str],
    caption: str,
    target: Target,
    now: datetime | None = None,
) -> list[Publication]:
    """Plant een postversie in op één of meer accounts. Alles of niets: als één account
    niet kan, wordt er niets ingepland en krijg je alle redenen terug."""
    now = now or _now()
    caption = normalize_caption(caption)
    company = session.get(Company, post.company_id)
    if version.post_id != post.id:
        raise ServiceError("Die versie hoort niet bij deze post.", status=404)
    accounts = session.scalars(
        select(SocialAccount).where(
            SocialAccount.id.in_(account_ids), SocialAccount.company_id == post.company_id
        )
    ).all()
    if not account_ids or len(accounts) != len(set(account_ids)):
        raise ServiceError("Kies een of meer accounts van dit bedrijf.")

    planned: list[tuple[SocialAccount, str, str, datetime]] = []
    problems = []
    for account in accounts:
        format_key = format_by_provider.get(account.provider)
        if not format_key:
            problems.append(f"{account.name}: kies een formaat.")
            continue
        try:
            when = resolve_target(session, company, account.id, target, now)
        except ServiceError as error:
            problems.append(f"{account.name}: {error.message}")
            continue
        facts, key = facts_for(
            session,
            account=account,
            post=post,
            version=version,
            format_key=format_key,
            caption=caption,
            scheduled_at=when,
            now=now,
        )
        issues = check_publishable(facts)
        if issues:
            problems.extend(f"{account.name}: {i.message}" for i in issues)
            continue
        planned.append((account, format_key, key, when))
    if problems:
        raise ServiceError(problems[0], issues=problems)

    created = []
    try:
        for account, format_key, key, when in planned:
            publication = Publication(
                company_id=post.company_id,
                post_id=post.id,
                post_version_id=version.id,
                format_key=format_key,
                media_key=key,
                social_account_id=account.id,
                caption="" if format_key == "instagram/story" else caption,
                status="scheduled",
                scheduled_at=when,
                schedule_tz=company.timezone,
                created_by=user.id,
            )
            session.add(publication)
            session.flush()
            created.append(publication)
        session.commit()
    except IntegrityError as error:
        session.rollback()
        if not _is_exclusion(error):
            raise
        raise ServiceError(
            "Op dat moment staat er al een publicatie op een van deze accounts. Kies een ander "
            "moment of wissel ze om in de planning.",
            status=409,
        ) from error
    return created


# ----------------------------------------------------------------------------- move


def _occupant(session: Session, account_id: str, at: datetime, exclude: str) -> Publication | None:
    return session.scalar(
        select(Publication).where(
            Publication.social_account_id == account_id,
            Publication.scheduled_at == at,
            Publication.status.in_(("scheduled", "publishing")),
            Publication.id != exclude,
        )
    )


def move(
    session: Session,
    publication: Publication,
    *,
    expected_version: int,
    target: Target,
    on_conflict: str = "ask",
    other_version: int | None = None,
    caption: str | None = None,
    dry_run: bool = False,
    now: datetime | None = None,
) -> tuple[Publication, str | None]:
    """Verplaatst een publicatie. Bij een bezet moment: vragen (conflict) of omwisselen.
    Het oude moment komt in dezelfde transactie vrij."""
    now = now or _now()
    if publication.status not in ("scheduled", "failed", "cancelled"):
        raise ServiceError(
            f"Een publicatie met status {publication.status} kan niet verplaatst worden."
        )
    if publication.version != expected_version:
        raise ServiceError(
            "Deze publicatie is intussen gewijzigd. Herlaad de planning.", status=409
        )
    company = session.get(Company, publication.company_id)
    when = resolve_target(
        session, company, publication.social_account_id, target, now, publication.id
    )
    new_caption = publication.caption if caption is None else normalize_caption(caption)
    version = session.get(PostVersion, publication.post_version_id)
    facts, _ = facts_for(
        session,
        account=publication.account,
        post=publication.post,
        version=version,
        format_key=publication.format_key,
        caption=new_caption,
        scheduled_at=when,
        now=now,
        media_key=publication.media_key,
    )
    issues = check_publishable(facts)
    if issues:
        raise ServiceError(issues[0].message, issues=[i.message for i in issues])
    occupant = _occupant(session, publication.social_account_id, when, publication.id)
    if occupant and on_conflict != "swap":
        raise ServiceError(
            "Dat moment is al bezet.",
            conflict=Conflict(occupant.id, occupant.version, occupant.caption[:120], when),
            status=409,
        )
    if dry_run:
        return publication, None
    old_time = publication.scheduled_at
    try:
        swapped = None
        if occupant:
            if publication.status != "scheduled" or not old_time:
                raise ServiceError(
                    "Alleen geplande publicaties kunnen wisselen. Kies een ander moment."
                )
            if occupant.status != "scheduled" or occupant.version != (other_version or -1):
                raise ServiceError(
                    "De andere publicatie is intussen gewijzigd of wordt al verstuurd.", status=409
                )
            session.execute(text("SET CONSTRAINTS publication_one_per_account_slot DEFERRED"))
            occupant.scheduled_at = old_time
            occupant.version += 1
            occupant.updated_at = now
            swapped = occupant.id
        if publication.status == "failed":
            publication.retry_base = publication.attempt_count
        publication.status = "scheduled"
        publication.scheduled_at = when
        publication.schedule_tz = company.timezone
        publication.caption = new_caption
        publication.next_attempt_at = None
        publication.failure_code = None
        publication.failure_message = None
        publication.failure_retryable = None
        publication.version += 1
        publication.updated_at = now
        session.flush()
        session.execute(text("SET CONSTRAINTS publication_one_per_account_slot IMMEDIATE"))
        session.commit()
    except IntegrityError as error:
        session.rollback()
        if not _is_exclusion(error):
            raise
        raise ServiceError("Dat moment werd net bezet. Probeer opnieuw.", status=409) from error
    except ServiceError:
        session.rollback()
        raise
    return publication, swapped


# ----------------------------------------------------------------------------- retry / cancel


UNCERTAIN_CODES = {"timeout", "provider_unavailable", "uncertain", "unknown"}


def retry(
    session: Session, publication: Publication, expected_version: int, confirmed: bool
) -> Publication:
    """Handmatig opnieuw: zet een mislukte publicatie klaar voor direct versturen.
    Twee keer klikken is onschadelijk (de tweede keer is hij niet meer 'failed')."""
    if publication.status != "failed":
        raise ServiceError("Deze publicatie is niet mislukt; er is niets opnieuw te proberen.")
    if publication.version != expected_version:
        raise ServiceError("Deze publicatie is intussen gewijzigd. Herlaad de pagina.", status=409)
    if publication.failure_code in UNCERTAIN_CODES and not confirmed:
        raise ServiceError(
            "Bevestig eerst dat je in het account hebt gecontroleerd dat de post er niet staat."
        )
    if publication.account.status != "active":
        raise ServiceError(f"Koppel {publication.account.name} eerst opnieuw.")
    now = _now()
    for offset in range(3):
        try:
            publication.status = "scheduled"
            publication.scheduled_at = now.replace(microsecond=0) - timedelta(seconds=offset)
            publication.next_attempt_at = None
            publication.retry_base = publication.attempt_count
            publication.version += 1
            publication.updated_at = now
            session.commit()
            return publication
        except IntegrityError as error:
            session.rollback()
            if not _is_exclusion(error):
                raise
            session.refresh(publication)
    raise ServiceError("Kon geen moment vinden om opnieuw te proberen. Probeer het nog eens.")


def cancel(session: Session, publication: Publication, expected_version: int) -> None:
    if publication.status not in ("scheduled", "failed"):
        raise ServiceError(
            f"Een publicatie met status {publication.status} kan niet geannuleerd worden."
        )
    if publication.version != expected_version:
        raise ServiceError("Deze publicatie is intussen gewijzigd. Herlaad de pagina.", status=409)
    publication.status = "cancelled"
    publication.version += 1
    publication.updated_at = _now()
    session.commit()
