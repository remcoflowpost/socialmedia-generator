"""Publicatie: controleert een publicatieverzoek en zet het om naar een job-payload.
De worker voert de job uit via de ingestelde provider (zie app.publishing)."""

from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.models import Asset, Company, Job, Post
from app.publishing import (
    Channel,
    ChannelPost,
    MediaFile,
    PublishProvider,
    PublishRequest,
)
from app.storage import get_storage

PUBLISHABLE_KINDS = ("image", "video")
# Klokverschil tussen browser en server opvangen bij "inplannen".
SCHEDULE_GRACE = timedelta(minutes=1)


class MediaRef(BaseModel):
    """Een bestand uit de bibliotheek (asset_id) of uit een afgeronde export (job + file)."""

    asset_id: str | None = None
    export_job_id: str | None = None
    file: str | None = None


class ChannelItem(BaseModel):
    channel_id: str
    media: list[MediaRef] = Field(default_factory=list)


class PublishBody(BaseModel):
    company_id: str
    caption: str = ""
    mode: Literal["now", "schedule", "draft"] = "now"
    scheduled_at: datetime | None = None
    channels: list[ChannelItem] = Field(min_length=1)


class PublishRejected(ValueError):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


def channels_for_company(channels: list[Channel], company: Company) -> tuple[list[Channel], bool]:
    """Kanalen van dit bedrijf. In Postiz groepeer je kanalen per bedrijf met een
    "customer" met dezelfde naam of slug. Zonder overeenkomst: alle kanalen (False)."""
    names = {company.name.strip().lower(), company.slug.lower()}
    matched = [c for c in channels if c.group and c.group.strip().lower() in names]
    if matched:
        return matched, True
    return channels, False


def _resolve_date(body: PublishBody, now: datetime) -> datetime:
    if body.mode != "schedule":
        return now
    if not body.scheduled_at:
        raise PublishRejected(422, "Kies een datum en tijd om in te plannen.")
    date = body.scheduled_at if body.scheduled_at.tzinfo else body.scheduled_at.replace(tzinfo=UTC)
    if date < now - SCHEDULE_GRACE:
        raise PublishRejected(422, "De geplande datum ligt in het verleden.")
    return date


def _resolve_media(
    session: Session, ref: MediaRef, company: Company, date: datetime, mode: str, posts: set[str]
) -> MediaFile:
    if ref.asset_id:
        asset = session.get(Asset, ref.asset_id)
        if not asset or asset.company_id != company.id:
            raise PublishRejected(404, "Bestand niet gevonden bij dit bedrijf.")
        if asset.kind not in PUBLISHABLE_KINDS:
            raise PublishRejected(422, f"{asset.filename} is geen beeld of video.")
        return MediaFile(key=asset.storage_key, filename=asset.filename)

    job = session.get(Job, ref.export_job_id) if ref.export_job_id else None
    if not job or job.type != "export" or job.status != "done" or not job.result:
        raise PublishRejected(404, "Export niet gevonden of nog niet klaar.")
    post = session.get(Post, job.payload.get("postId"))
    if not post or post.company_id != company.id:
        raise PublishRejected(404, "Export hoort niet bij dit bedrijf.")
    entry = next((f for f in job.result["files"] if f["name"] == ref.file), None)
    if not entry:
        raise PublishRejected(404, f"Bestand {ref.file} zit niet in deze export.")
    if entry.get("severity") == "error":
        raise PublishRejected(
            422, f"{entry['name']} heeft kwaliteitsfouten. Los die op en exporteer opnieuw."
        )
    if mode != "draft" and post.embargo_until and post.embargo_until > date:
        raise PublishRejected(
            409,
            f"'{post.title}' heeft een embargo tot {post.embargo_until:%d-%m-%Y %H:%M} (UTC). "
            "Plan later in of maak een concept.",
        )
    posts.add(post.id)
    return MediaFile(key=entry["key"], filename=entry["name"], format_key=entry["formatKey"])


def prepare_publication(
    session: Session, body: PublishBody, provider: PublishProvider, now: datetime | None = None
) -> dict:
    """Controleert alles wat vooraf te controleren is en geeft de job-payload terug."""
    now = now or datetime.now(UTC)
    company = session.get(Company, body.company_id)
    if not company:
        raise PublishRejected(404, "Onbekend bedrijf.")
    date = _resolve_date(body, now)

    available = {c.id: c for c in provider.list_channels()}
    post_ids: set[str] = set()
    items = []
    seen: set[str] = set()
    for item in body.channels:
        channel = available.get(item.channel_id)
        if not channel:
            raise PublishRejected(404, "Kanaal niet gevonden in de publicatietool.")
        if channel.disabled:
            raise PublishRejected(422, f"Kanaal {channel.name} staat uit.")
        if channel.id in seen:
            continue
        seen.add(channel.id)
        media = [
            _resolve_media(session, ref, company, date, body.mode, post_ids) for ref in item.media
        ]
        if not media and not body.caption.strip():
            raise PublishRejected(422, f"Geen tekst en geen beeld voor {channel.name}.")
        items.append(
            {
                "channel": asdict(channel),
                "media": [
                    {"key": m.key, "filename": m.filename, "formatKey": m.format_key} for m in media
                ],
            }
        )

    return {
        "companyId": company.id,
        "postIds": sorted(post_ids),
        "caption": body.caption,
        "mode": body.mode,
        "date": date.isoformat(),
        "items": items,
    }


def request_from_payload(payload: dict) -> PublishRequest:
    storage = get_storage()
    return PublishRequest(
        caption=payload["caption"],
        mode=payload["mode"],
        date=datetime.fromisoformat(payload["date"]),
        posts=[
            ChannelPost(
                channel=Channel(**item["channel"]),
                media=[
                    MediaFile(
                        key=m["key"],
                        path=storage.local_path(m["key"]),
                        filename=m["filename"],
                        format_key=m.get("formatKey"),
                    )
                    for m in item["media"]
                ],
            )
            for item in payload["items"]
        ],
    )


def run_publication(payload: dict, provider: PublishProvider) -> dict:
    result = provider.publish(request_from_payload(payload))
    return asdict(result) | {"mode": payload["mode"], "date": payload["date"]}
