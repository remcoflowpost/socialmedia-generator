"""Database-entiteiten. JSON-documenten (brand kit, template, post) worden gevalideerd met
de Pydantic-modellen in app.schema voordat ze hier worden opgeslagen."""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    DDL,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    event,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, ExcludeConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(UTC)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(320), unique=True)
    name: Mapped[str] = mapped_column(String(200), default="")
    role: Mapped[str] = mapped_column(String(20), default="editor")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(80), unique=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    # IANA-tijdzone voor planning en publicatietijden van dit bedrijf.
    timezone: Mapped[str] = mapped_column(String(64), default="Europe/Amsterdam")

    brand_kit: Mapped["BrandKit | None"] = relationship(back_populates="company", uselist=False)


class BrandKit(Base):
    __tablename__ = "brand_kits"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), unique=True)
    data: Mapped[dict[str, Any]] = mapped_column(JSONB)
    version: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    company: Mapped[Company] = relationship(back_populates="brand_kit")


class Template(Base):
    __tablename__ = "templates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    key: Mapped[str] = mapped_column(String(80), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    type: Mapped[str] = mapped_column(String(80))
    version: Mapped[int] = mapped_column(Integer)
    definition: Mapped[dict[str, Any]] = mapped_column(JSONB)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Asset(Base):
    __tablename__ = "assets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    company_id: Mapped[str | None] = mapped_column(ForeignKey("companies.id"), index=True)
    kind: Mapped[str] = mapped_column(String(20))  # image, logo, font, reference
    filename: Mapped[str] = mapped_column(String(300))
    storage_key: Mapped[str] = mapped_column(String(500))
    original_key: Mapped[str | None] = mapped_column(String(500))
    mime: Mapped[str] = mapped_column(String(100))
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    color_profile: Mapped[str | None] = mapped_column(String(200))
    tags: Mapped[list[str]] = mapped_column(ARRAY(String(80)), default=list)
    origin: Mapped[str] = mapped_column(String(20), default="upload")  # upload, generated
    provenance: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    parent_asset_id: Mapped[str | None] = mapped_column(ForeignKey("assets.id"))
    owner_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Post(Base):
    __tablename__ = "posts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    template_id: Mapped[str] = mapped_column(ForeignKey("templates.id"))
    title: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(120))
    document: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="draft")
    embargo_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    client_approved: Mapped[bool] = mapped_column(Boolean, default=False)
    client_approved_by: Mapped[str | None] = mapped_column(String(200))
    client_approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Goedkeuring geldt voor precies deze versie; een latere versie vraagt nieuw akkoord.
    client_approved_version: Mapped[int | None] = mapped_column(Integer)
    author_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    current_version: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    company: Mapped[Company] = relationship()
    template: Mapped[Template] = relationship()


class PostVersion(Base):
    """Bevroren stand van een post, inclusief template en brand kit, zodat een oude versie
    exact opnieuw te renderen is."""

    __tablename__ = "post_versions"
    __table_args__ = (UniqueConstraint("post_id", "number"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    post_id: Mapped[str] = mapped_column(ForeignKey("posts.id"), index=True)
    number: Mapped[int] = mapped_column(Integer)
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB)
    reason: Mapped[str] = mapped_column(String(40))
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class QualityReport(Base):
    __tablename__ = "quality_reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    post_id: Mapped[str] = mapped_column(ForeignKey("posts.id"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    format_key: Mapped[str] = mapped_column(String(80))
    report: Mapped[dict[str, Any]] = mapped_column(JSONB)
    max_severity: Mapped[str | None] = mapped_column(String(10))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Job(Base):
    """Achtergrondtaak. De worker claimt jobs met SELECT ... FOR UPDATE SKIP LOCKED."""

    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    type: Mapped[str] = mapped_column(String(30), index=True)
    status: Mapped[str] = mapped_column(String(20), default="queued", index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    error: Mapped[str | None] = mapped_column(Text)
    progress: Mapped[float] = mapped_column(Float, default=0)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    cost: Mapped[float | None] = mapped_column(Float)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


# --------------------------------------------------------------------------------------------
# Publiceren (docs/publiceren.md)
# --------------------------------------------------------------------------------------------

ACCOUNT_STATUSES = ("active", "reauth_required", "disconnected")
PUBLICATION_STATUSES = ("scheduled", "publishing", "published", "failed", "cancelled")
ATTEMPT_OUTCOMES = ("in_progress", "succeeded", "failed", "uncertain")


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


class SocialAccount(Base):
    """Gekoppelde Facebook-pagina of Instagram-account van een bedrijf."""

    __tablename__ = "social_accounts"
    __table_args__ = (
        CheckConstraint(_in("status", ACCOUNT_STATUSES), name="social_account_status_valid"),
        CheckConstraint(
            "status = 'disconnected' OR token_enc IS NOT NULL", name="social_account_token_present"
        ),
        Index(
            "social_account_live_key",
            "company_id",
            "provider",
            "external_id",
            unique=True,
            postgresql_where=text("status <> 'disconnected'"),
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    provider: Mapped[str] = mapped_column(String(30))
    external_id: Mapped[str] = mapped_column(String(100))
    name: Mapped[str] = mapped_column(String(200))
    handle: Mapped[str] = mapped_column(String(200), default="")
    token_enc: Mapped[str | None] = mapped_column(Text)
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default="active")
    status_reason: Mapped[str | None] = mapped_column(String(300))
    connected_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    company: Mapped[Company] = relationship()


class PublishSlot(Base):
    """Terugkerende publicatietijd van een bedrijf (lokale tijd in companies.timezone)."""

    __tablename__ = "publish_slots"
    __table_args__ = (
        UniqueConstraint("company_id", "weekday", "local_time", name="publish_slot_unique"),
        CheckConstraint("weekday BETWEEN 1 AND 7", name="publish_slot_weekday"),
        CheckConstraint("local_time ~ '^([01][0-9]|2[0-3]):[0-5][0-9]$'", name="publish_slot_time"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    weekday: Mapped[int] = mapped_column(Integer)
    local_time: Mapped[str] = mapped_column(String(5))


class Publication(Base):
    """Eén beeld van één bevroren postversie naar één account op één moment. Dit is ook
    de job: de publisher claimt rijen uit deze tabel."""

    __tablename__ = "publications"
    __table_args__ = (
        CheckConstraint(_in("status", PUBLICATION_STATUSES), name="publication_status_valid"),
        CheckConstraint(
            "status NOT IN ('scheduled', 'publishing') OR scheduled_at IS NOT NULL",
            name="publication_scheduled_has_time",
        ),
        CheckConstraint(
            "status <> 'published' OR (provider_post_id IS NOT NULL AND published_at IS NOT NULL)",
            name="publication_published_has_result",
        ),
        CheckConstraint(
            "status <> 'failed' OR failure_code IS NOT NULL", name="publication_failed_has_code"
        ),
        CheckConstraint("char_length(caption) <= 63206", name="publication_caption_length"),
        # Hooguit één geplande publicatie per account per moment. Deferrable, zodat twee
        # publicaties in één transactie van plek kunnen wisselen.
        ExcludeConstraint(
            ("social_account_id", "="),
            ("scheduled_at", "="),
            name="publication_one_per_account_slot",
            using="btree",
            where=text("status IN ('scheduled', 'publishing')"),
            deferrable=True,
            initially="IMMEDIATE",
        ),
        Index("publication_due_idx", "scheduled_at", postgresql_where=text("status = 'scheduled'")),
        Index("publication_company_time_idx", "company_id", "scheduled_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"))
    post_id: Mapped[str] = mapped_column(ForeignKey("posts.id"), index=True)
    post_version_id: Mapped[str] = mapped_column(ForeignKey("post_versions.id"))
    format_key: Mapped[str] = mapped_column(String(80))
    media_key: Mapped[str] = mapped_column(String(500))
    social_account_id: Mapped[str] = mapped_column(ForeignKey("social_accounts.id"))
    caption: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="scheduled")
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    schedule_tz: Mapped[str] = mapped_column(String(64))
    idempotency_key: Mapped[str] = mapped_column(String(36), unique=True, default=_uuid)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    retry_base: Mapped[int] = mapped_column(Integer, default=0)
    first_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    provider_container_id: Mapped[str | None] = mapped_column(String(100))
    provider_post_id: Mapped[str | None] = mapped_column(String(100))
    provider_url: Mapped[str | None] = mapped_column(String(500))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failure_code: Mapped[str | None] = mapped_column(String(40))
    failure_message: Mapped[str | None] = mapped_column(Text)
    failure_retryable: Mapped[bool | None] = mapped_column(Boolean)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    account: Mapped[SocialAccount] = relationship()
    post: Mapped[Post] = relationship()


class PublishAttempt(Base):
    """Onveranderlijke log van elke poging. Een trigger weigert wijzigen na afronden en
    weigert verwijderen."""

    __tablename__ = "publish_attempts"
    __table_args__ = (
        UniqueConstraint("publication_id", "attempt_no", name="publish_attempt_no_unique"),
        CheckConstraint(_in("outcome", ATTEMPT_OUTCOMES), name="publish_attempt_outcome_valid"),
        CheckConstraint(
            "(outcome = 'in_progress') = (finished_at IS NULL)",
            name="publish_attempt_finished_consistent",
        ),
        Index("publish_attempt_company_started_idx", "company_id", "started_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    publication_id: Mapped[str] = mapped_column(ForeignKey("publications.id"), index=True)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"))
    social_account_id: Mapped[str] = mapped_column(ForeignKey("social_accounts.id"))
    attempt_no: Mapped[int] = mapped_column(Integer)
    trigger: Mapped[str] = mapped_column(String(20))
    idempotency_key: Mapped[str] = mapped_column(String(36))
    correlation_id: Mapped[str] = mapped_column(String(36), default=_uuid)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    outcome: Mapped[str] = mapped_column(String(20), default="in_progress")
    error_code: Mapped[str | None] = mapped_column(String(40))
    retryable: Mapped[bool | None] = mapped_column(Boolean)
    http_status: Mapped[int | None] = mapped_column(Integer)
    provider_message: Mapped[str | None] = mapped_column(String(500))
    container_id: Mapped[str | None] = mapped_column(String(100))
    provider_post_id: Mapped[str | None] = mapped_column(String(100))
    provider_url: Mapped[str | None] = mapped_column(String(500))


class SandboxPost(Base):
    """Opslag van het Sandbox-netwerk (alleen ontwikkeling en tests)."""

    __tablename__ = "sandbox_posts"
    __table_args__ = (
        UniqueConstraint("account_id", "container_id", name="sandbox_post_container"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    account_id: Mapped[str] = mapped_column(String(100))
    container_id: Mapped[str] = mapped_column(String(100))
    caption: Mapped[str] = mapped_column(Text, default="")
    media_key: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


# Dezelfde SQL staat in de Alembic-migratie; create_all (tests) maakt hem via dit event.
PUBLISH_ATTEMPT_GUARD_SQL = """
CREATE OR REPLACE FUNCTION publish_attempt_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP = 'DELETE' THEN
    IF current_setting('flow.allow_audit_purge', true) = 'on' THEN
      RETURN OLD;
    END IF;
    RAISE EXCEPTION 'publish_attempts zijn onveranderlijk (verwijderen geweigerd)'
      USING ERRCODE = 'restrict_violation';
  END IF;
  IF OLD.outcome <> 'in_progress' THEN
    RAISE EXCEPTION 'publish_attempt % is afgerond en onveranderlijk', OLD.id
      USING ERRCODE = 'restrict_violation';
  END IF;
  IF NEW.id <> OLD.id OR NEW.publication_id <> OLD.publication_id
     OR NEW.attempt_no <> OLD.attempt_no OR NEW.started_at <> OLD.started_at THEN
    RAISE EXCEPTION 'identiteitskolommen van publish_attempt veranderen niet'
      USING ERRCODE = 'restrict_violation';
  END IF;
  RETURN NEW;
END;
$$;
DROP TRIGGER IF EXISTS publish_attempt_immutable ON publish_attempts;
CREATE TRIGGER publish_attempt_immutable BEFORE UPDATE OR DELETE ON publish_attempts
  FOR EACH ROW EXECUTE FUNCTION publish_attempt_guard();
"""

# DDL gebruikt %-opmaak; de % uit RAISE moet daarvoor verdubbeld worden.
event.listen(
    PublishAttempt.__table__,
    "after_create",
    DDL(PUBLISH_ATTEMPT_GUARD_SQL.replace("%", "%%")),
)
