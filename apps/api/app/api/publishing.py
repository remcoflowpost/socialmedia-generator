"""API voor publiceren: accounts koppelen, publicatietijden, klantakkoord, inplannen,
verplaatsen, opnieuw proberen en de publicatielog. Zie docs/publiceren.md.

Rechten: iedereen op de allowlist mag inplannen en akkoord vastleggen; alleen admins
koppelen of ontkoppelen accounts en beheren tijdzone en publicatietijden.
"""

import json
import secrets
import time
from datetime import UTC, datetime, timedelta
from datetime import date as Date
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from pydantic import Field
from sqlalchemy import select

from app.api.deps import AdminUser, CurrentUser, DbSession
from app.models import (
    Company,
    Post,
    PostVersion,
    Publication,
    PublishAttempt,
    PublishSlot,
    SandboxPost,
    SocialAccount,
)
from app.publishing import crypto, service
from app.publishing.providers import ConnectableAccount
from app.publishing.rules import PLATFORMS
from app.publishing.slots import next_open_slot
from app.schema.base import CamelModel
from app.settings import get_settings
from app.storage import get_storage

router = APIRouter(tags=["publiceren"])
PENDING_TTL = 600


def _company(session, company_id: str) -> Company:
    company = session.get(Company, company_id)
    if not company:
        raise HTTPException(404, "Onbekend bedrijf.")
    return company


def _publication(session, publication_id: str) -> Publication:
    publication = session.get(Publication, publication_id)
    if not publication:
        raise HTTPException(404, "Onbekende publicatie.")
    return publication


def _fail(error: service.ServiceError) -> HTTPException:
    detail: dict = {"message": error.message, "issues": error.issues}
    if error.conflict:
        detail["conflict"] = {
            "otherId": error.conflict.other_id,
            "otherVersion": error.conflict.other_version,
            "otherCaption": error.conflict.other_caption,
            "target": error.conflict.target.isoformat(),
        }
    return HTTPException(error.status, detail)


def account_out(a: SocialAccount) -> dict:
    return {
        "id": a.id,
        "companyId": a.company_id,
        "provider": a.provider,
        "providerLabel": PLATFORMS[a.provider].label if a.provider in PLATFORMS else a.provider,
        "name": a.name,
        "handle": a.handle,
        "status": a.status,
        "statusReason": a.status_reason,
        "lastCheckedAt": a.last_checked_at.isoformat() if a.last_checked_at else None,
    }


def publication_out(p: Publication) -> dict:
    return {
        "id": p.id,
        "version": p.version,
        "postId": p.post_id,
        "postTitle": p.post.title,
        "postVersionId": p.post_version_id,
        "formatKey": p.format_key,
        "account": account_out(p.account),
        "caption": p.caption,
        "status": p.status,
        "scheduledAt": p.scheduled_at.isoformat() if p.scheduled_at else None,
        "publishedAt": p.published_at.isoformat() if p.published_at else None,
        "nextAttemptAt": p.next_attempt_at.isoformat() if p.next_attempt_at else None,
        "attemptCount": p.attempt_count,
        "providerUrl": p.provider_url,
        "failureCode": p.failure_code,
        "failureMessage": p.failure_message,
        "failureRetryable": p.failure_retryable,
        "needsConfirm": p.failure_code in service.UNCERTAIN_CODES,
    }


# ----------------------------------------------------------------------------- instellingen


@router.get("/api/companies/{company_id}/publishing")
def publishing_settings(company_id: str, _: CurrentUser, session: DbSession) -> dict:
    company = _company(session, company_id)
    slots = session.scalars(
        select(PublishSlot)
        .where(PublishSlot.company_id == company.id)
        .order_by(PublishSlot.weekday, PublishSlot.local_time)
    )
    accounts = session.scalars(
        select(SocialAccount)
        .where(SocialAccount.company_id == company.id, SocialAccount.status != "disconnected")
        .order_by(SocialAccount.created_at)
    )
    return {
        "timezone": company.timezone,
        "slots": [{"id": s.id, "weekday": s.weekday, "time": s.local_time} for s in slots],
        "accounts": [account_out(a) for a in accounts],
        "sandboxEnabled": get_settings().allow_sandbox_provider,
        "metaConfigured": bool(get_settings().meta_app_id and get_settings().meta_app_secret),
    }


class TimezoneIn(CamelModel):
    timezone: str = Field(max_length=64)


@router.put("/api/companies/{company_id}/timezone")
def put_timezone(company_id: str, body: TimezoneIn, _: AdminUser, session: DbSession) -> dict:
    try:
        service.set_timezone(session, _company(session, company_id), body.timezone)
    except service.ServiceError as error:
        raise _fail(error) from error
    return {"timezone": body.timezone}


class SlotsIn(CamelModel):
    weekdays: list[int] = Field(max_length=7)
    time: str = Field(max_length=5)


@router.post("/api/companies/{company_id}/slots")
def post_slots(company_id: str, body: SlotsIn, _: AdminUser, session: DbSession) -> dict:
    try:
        added = service.add_slots(session, _company(session, company_id), body.weekdays, body.time)
    except service.ServiceError as error:
        raise _fail(error) from error
    return {"added": added}


@router.delete("/api/companies/{company_id}/slots/{slot_id}")
def delete_slot(company_id: str, slot_id: str, _: AdminUser, session: DbSession) -> dict:
    slot = session.get(PublishSlot, slot_id)
    if slot and slot.company_id == company_id:
        session.delete(slot)
        session.commit()
    return {"ok": True}


# ----------------------------------------------------------------------------- accounts


def _pending_aad(user_id: str, company_id: str) -> str:
    return f"pending-accounts:{user_id}:{company_id}"


@router.get("/api/publishing/connect/meta/start")
def meta_start(company_id: str, request: Request, user: AdminUser, session: DbSession):
    from app.publishing.providers.meta import authorize_url

    settings = get_settings()
    if not (settings.meta_app_id and settings.meta_app_secret):
        raise HTTPException(503, "Meta is nog niet geconfigureerd (META_APP_ID/META_APP_SECRET).")
    _company(session, company_id)
    state = secrets.token_urlsafe(24)
    request.session["meta_oauth"] = {
        "state": state,
        "company": company_id,
        "exp": time.time() + 600,
    }
    redirect = f"{settings.public_url.rstrip('/')}/api/publishing/connect/meta/callback"
    return RedirectResponse(authorize_url(state, redirect), status_code=303)


@router.get("/api/publishing/connect/meta/callback")
def meta_callback(request: Request, user: AdminUser, session: DbSession):
    from app.publishing.providers.meta import connectable_accounts

    oauth = request.session.pop("meta_oauth", None)
    settings = get_settings()
    back = settings.public_url.rstrip("/")
    params = request.query_params
    if not oauth or oauth["exp"] < time.time():
        return RedirectResponse(f"{back}/publiceren/accounts?melding=verlopen", status_code=303)
    company_id = oauth["company"]
    if params.get("error"):
        return RedirectResponse(
            f"{back}/publiceren/accounts?bedrijf={company_id}&melding=geannuleerd", status_code=303
        )
    if not secrets.compare_digest(oauth["state"], params.get("state", "")):
        return RedirectResponse(f"{back}/publiceren/accounts?melding=mislukt", status_code=303)
    try:
        found = connectable_accounts(
            params.get("code", ""), f"{back}/api/publishing/connect/meta/callback"
        )
    except Exception:  # noqa: BLE001 - nette melding, details in de log
        import logging

        logging.getLogger("publiceren").exception("Meta-koppeling mislukt")
        return RedirectResponse(f"{back}/publiceren/accounts?melding=mislukt", status_code=303)
    # Tokens nooit leesbaar in de (alleen ondertekende) sessiecookie: versleuteld opslaan.
    payload = json.dumps([a.__dict__ | {"token_expires_at": None} for a in found])
    request.session["meta_pending"] = {
        "company": company_id,
        "exp": time.time() + PENDING_TTL,
        "blob": crypto.encrypt(payload, _pending_aad(user.id, company_id)),
    }
    return RedirectResponse(
        f"{back}/publiceren/accounts?bedrijf={company_id}&kiezen=1", status_code=303
    )


def _pending(request: Request, user_id: str, company_id: str) -> list[ConnectableAccount]:
    pending = request.session.get("meta_pending")
    if not pending or pending["company"] != company_id or pending["exp"] < time.time():
        return []
    raw = json.loads(crypto.decrypt(pending["blob"], _pending_aad(user_id, company_id)))
    return [ConnectableAccount(**item) for item in raw]


@router.get("/api/publishing/connect/pending")
def pending_accounts(company_id: str, request: Request, user: AdminUser) -> list[dict]:
    return [
        {"provider": a.provider, "externalId": a.external_id, "name": a.name}
        for a in _pending(request, user.id, company_id)
    ]


class ConfirmIn(CamelModel):
    company_id: str
    external_ids: list[str] = Field(max_length=50)


@router.post("/api/publishing/connect/confirm")
def confirm_accounts(body: ConfirmIn, request: Request, user: AdminUser, session: DbSession):
    company = _company(session, body.company_id)
    chosen = [
        a for a in _pending(request, user.id, company.id) if a.external_id in body.external_ids
    ]
    if not chosen:
        raise HTTPException(422, {"message": "Kies minstens één account, of koppel opnieuw."})
    accounts = service.connect_accounts(session, company, user, chosen)
    request.session.pop("meta_pending", None)
    return [account_out(a) for a in accounts]


class SandboxIn(CamelModel):
    company_id: str
    name: str = Field(min_length=2, max_length=60, pattern=r"^[a-z0-9_.]+$")
    provider: Literal["sandbox"] = "sandbox"


@router.post("/api/publishing/connect/sandbox")
def connect_sandbox(body: SandboxIn, user: AdminUser, session: DbSession) -> dict:
    if not get_settings().allow_sandbox_provider:
        raise HTTPException(404)
    company = _company(session, body.company_id)
    found = ConnectableAccount(
        "sandbox", f"sbx-{body.name}", f"@{body.name}", body.name, secrets.token_urlsafe(16), None
    )
    return account_out(service.connect_accounts(session, company, user, [found])[0])


class ConfirmFlag(CamelModel):
    confirm: bool = False


@router.post("/api/publishing/accounts/{account_id}/check")
def check(account_id: str, _: CurrentUser, session: DbSession) -> dict:
    account = session.get(SocialAccount, account_id)
    if not account:
        raise HTTPException(404)
    ok, message = service.check_account(session, account)
    return {"ok": ok, "message": message, "account": account_out(account)}


@router.post("/api/publishing/accounts/{account_id}/disconnect")
def disconnect(account_id: str, body: ConfirmFlag, _: AdminUser, session: DbSession) -> dict:
    account = session.get(SocialAccount, account_id)
    if not account:
        raise HTTPException(404)
    if not body.confirm:
        raise HTTPException(422, {"message": "Bevestig het ontkoppelen."})
    return {"cancelled": service.disconnect_account(session, account)}


# ----------------------------------------------------------------------------- akkoord


class ApprovalIn(CamelModel):
    approved_by: str = Field(min_length=1, max_length=200)
    version: int


@router.post("/api/posts/{post_id}/approval")
def approve(post_id: str, body: ApprovalIn, _: CurrentUser, session: DbSession) -> dict:
    post = session.get(Post, post_id)
    if not post:
        raise HTTPException(404)
    try:
        service.approve(session, post, body.approved_by, body.version)
    except service.ServiceError as error:
        raise _fail(error) from error
    return {"approvedVersion": post.client_approved_version, "approvedBy": post.client_approved_by}


@router.delete("/api/posts/{post_id}/approval")
def revoke(post_id: str, _: CurrentUser, session: DbSession) -> dict:
    post = session.get(Post, post_id)
    if not post:
        raise HTTPException(404)
    return {"scheduledAffected": service.revoke_approval(session, post)}


# ----------------------------------------------------------------------------- inplannen


@router.get("/api/posts/{post_id}/publish-options")
def publish_options(post_id: str, _: CurrentUser, session: DbSession) -> dict:
    post = session.get(Post, post_id)
    if not post:
        raise HTTPException(404)
    company = session.get(Company, post.company_id)
    version = session.scalar(
        select(PostVersion)
        .where(PostVersion.post_id == post.id)
        .order_by(PostVersion.number.desc())
        .limit(1)
    )
    files = service.export_files(session, version) if version else {}
    accounts = session.scalars(
        select(SocialAccount).where(
            SocialAccount.company_id == company.id, SocialAccount.status != "disconnected"
        )
    ).all()
    slots = service.company_slots(session, company.id)
    now = datetime.now(UTC)
    out_accounts = []
    for a in accounts:
        spec = PLATFORMS.get(a.provider)
        occupied = service._occupied(session, a.id, now, None)  # noqa: SLF001
        slot = next_open_slot(slots, company.timezone, occupied, now)
        out_accounts.append(
            account_out(a)
            | {
                "formats": [f for f in (spec.formats if spec else ()) if f in files],
                "unsupportedFormats": sorted(set(files) - set(spec.formats if spec else ())),
                "captionLimit": spec.caption_limit if spec else None,
                "nextSlot": slot.isoformat() if slot else None,
            }
        )
    return {
        "timezone": company.timezone,
        "version": {"id": version.id, "number": version.number} if version else None,
        "exportedFormats": {k: {"severity": v.severity} for k, v in files.items()},
        "approval": {
            "approved": post.client_approved,
            "version": post.client_approved_version,
            "by": post.client_approved_by,
            "at": post.client_approved_at.isoformat() if post.client_approved_at else None,
        },
        "embargoUntil": post.embargo_until.isoformat() if post.embargo_until else None,
        "accounts": out_accounts,
    }


class WhenIn(CamelModel):
    kind: Literal["next_slot", "local", "instant"]
    date: Date | None = None
    time: str | None = Field(None, max_length=5)
    instant: datetime | None = None

    def target(self) -> service.Target:
        return service.Target(self.kind, self.date, self.time, self.instant)


class ScheduleIn(CamelModel):
    post_id: str
    version_id: str
    account_ids: list[str] = Field(min_length=1, max_length=10)
    formats: dict[str, str]
    caption: str = Field("", max_length=64000)
    when: WhenIn


@router.post("/api/publications")
def create_publications(body: ScheduleIn, user: CurrentUser, session: DbSession) -> list[dict]:
    post = session.get(Post, body.post_id)
    version = session.get(PostVersion, body.version_id)
    if not post or not version:
        raise HTTPException(404)
    try:
        created = service.schedule(
            session,
            user,
            post=post,
            version=version,
            account_ids=body.account_ids,
            format_by_provider=body.formats,
            caption=body.caption,
            target=body.when.target(),
        )
    except service.ServiceError as error:
        raise _fail(error) from error
    return [publication_out(p) for p in created]


@router.get("/api/publications")
def list_publications(
    company_id: str, start: datetime, end: datetime, _: CurrentUser, session: DbSession
) -> dict:
    company = _company(session, company_id)
    if end - start > timedelta(days=42):
        raise HTTPException(422, "Vraag maximaal zes weken tegelijk op.")
    rows = session.scalars(
        select(Publication)
        .where(
            Publication.company_id == company.id,
            Publication.status != "cancelled",
            Publication.scheduled_at >= start,
            Publication.scheduled_at < end,
        )
        .order_by(Publication.scheduled_at)
    ).all()
    failed = session.scalars(
        select(Publication)
        .where(Publication.company_id == company.id, Publication.status == "failed")
        .order_by(Publication.updated_at.desc())
        .limit(50)
    ).all()
    slots = service.company_slots(session, company.id)
    from app.publishing.slots import slot_instants_between

    return {
        "timezone": company.timezone,
        "publications": [publication_out(p) for p in rows],
        "failed": [publication_out(p) for p in failed],
        "slots": [
            s.isoformat() for s in slot_instants_between(slots, company.timezone, start, end)
        ],
    }


class MoveIn(CamelModel):
    version: int
    when: WhenIn
    on_conflict: Literal["ask", "swap"] = "ask"
    other_version: int | None = None
    caption: str | None = Field(None, max_length=64000)
    dry_run: bool = False


@router.post("/api/publications/{publication_id}/move")
def move(publication_id: str, body: MoveIn, _: CurrentUser, session: DbSession) -> dict:
    publication = _publication(session, publication_id)
    try:
        moved, swapped = service.move(
            session,
            publication,
            expected_version=body.version,
            target=body.when.target(),
            on_conflict=body.on_conflict,
            other_version=body.other_version,
            caption=body.caption,
            dry_run=body.dry_run,
        )
    except service.ServiceError as error:
        raise _fail(error) from error
    return {"publication": publication_out(moved), "swappedWith": swapped, "dryRun": body.dry_run}


class RetryIn(CamelModel):
    version: int
    confirmed: bool = False


@router.post("/api/publications/{publication_id}/retry")
def retry(publication_id: str, body: RetryIn, _: CurrentUser, session: DbSession) -> dict:
    publication = _publication(session, publication_id)
    try:
        service.retry(session, publication, body.version, body.confirmed)
    except service.ServiceError as error:
        raise _fail(error) from error
    return publication_out(publication)


class VersionIn(CamelModel):
    version: int


@router.post("/api/publications/{publication_id}/cancel")
def cancel(publication_id: str, body: VersionIn, _: CurrentUser, session: DbSession) -> dict:
    publication = _publication(session, publication_id)
    try:
        service.cancel(session, publication, body.version)
    except service.ServiceError as error:
        raise _fail(error) from error
    return publication_out(publication)


@router.get("/api/publications/log")
def publication_log(
    company_id: str, _: CurrentUser, session: DbSession, before: datetime | None = None
) -> list[dict]:
    company = _company(session, company_id)
    stmt = (
        select(PublishAttempt, Publication)
        .join(Publication, Publication.id == PublishAttempt.publication_id)
        .where(PublishAttempt.company_id == company.id)
        .order_by(PublishAttempt.started_at.desc())
        .limit(100)
    )
    if before:
        stmt = stmt.where(PublishAttempt.started_at < before)
    return [
        {
            "id": a.id,
            "publicationId": p.id,
            "postTitle": p.post.title,
            "account": account_out(p.account),
            "formatKey": p.format_key,
            "attemptNo": a.attempt_no,
            "trigger": a.trigger,
            "startedAt": a.started_at.isoformat(),
            "finishedAt": a.finished_at.isoformat() if a.finished_at else None,
            "outcome": a.outcome,
            "errorCode": a.error_code,
            "httpStatus": a.http_status,
            "providerMessage": a.provider_message,
            "providerUrl": a.provider_url,
        }
        for a, p in session.execute(stmt)
    ]


# ----------------------------------------------------------------------------- publiek


@router.get("/api/public/media/{publication_id}")
def public_media(publication_id: str, exp: str, sig: str, session: DbSession) -> FileResponse:
    """Zonder login: Instagram haalt hier het beeld op. Alleen met een geldige,
    kortlevende handtekening voor precies deze publicatie."""
    if not service.verify_media_signature(publication_id, exp, sig):
        raise HTTPException(403, "Link ongeldig of verlopen.")
    publication = session.get(Publication, publication_id)
    if not publication or publication.status not in ("scheduled", "publishing", "published"):
        raise HTTPException(404)
    path = get_storage().local_path(publication.media_key)
    media = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
    return FileResponse(
        path,
        media_type=media,
        headers={"Cache-Control": "private, max-age=300", "X-Content-Type-Options": "nosniff"},
    )


@router.get("/api/sandbox/posts/{post_id}", response_class=HTMLResponse)
def sandbox_post(post_id: str, session: DbSession) -> str:
    if not get_settings().allow_sandbox_provider:
        raise HTTPException(404)
    row = session.get(SandboxPost, post_id)
    if not row:
        raise HTTPException(404)
    from html import escape

    return (
        "<!doctype html><meta charset=utf-8><title>Sandbox-post</title>"
        "<body style='font-family:system-ui;max-width:520px;margin:3rem auto'>"
        f"<p style='color:#666'>Sandbox-netwerk &middot; {escape(row.account_id)} &middot; "
        f"{row.created_at:%d-%m-%Y %H:%M}</p>"
        f"<p style='white-space:pre-wrap'>{escape(row.caption)}</p>"
    )
