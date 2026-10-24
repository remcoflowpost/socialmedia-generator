"""Posts, versies en het samenstellen van renderinvoer vanuit de database."""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.render_input import AssetInfo, referenced_asset_ids
from app.models import Asset, Post, PostVersion
from app.schema import BrandKitData, PostDocument, TemplateDefinition


class PostError(ValueError):
    pass


def template_of(post: Post) -> TemplateDefinition:
    return TemplateDefinition.model_validate(post.template.definition)


def brand_of(post: Post) -> BrandKitData:
    kit = post.company.brand_kit
    if not kit:
        raise PostError(f"{post.company.name} heeft nog geen brand kit.")
    return BrandKitData.model_validate(kit.data)


def snapshot_of(post: Post) -> dict[str, Any]:
    kit = post.company.brand_kit
    return {
        "document": PostDocument.model_validate(post.document).model_dump(by_alias=True),
        "template": post.template.definition,
        "brand": kit.data if kit else None,
        "brandKitVersion": kit.version if kit else None,
        "title": post.title,
        "slug": post.slug,
        "embargoUntil": post.embargo_until.isoformat() if post.embargo_until else None,
    }


def create_version(session: Session, post: Post, reason: str, user_id: str | None) -> PostVersion:
    """Bevriest de huidige stand. Gebeurt bij expliciet opslaan, export en statuswijziging,
    niet bij autosave."""
    number = (
        session.scalar(select(func.max(PostVersion.number)).where(PostVersion.post_id == post.id))
        or 0
    ) + 1
    version = PostVersion(
        post_id=post.id,
        number=number,
        snapshot=snapshot_of(post),
        reason=reason,
        created_by=user_id,
    )
    post.current_version = number
    post.updated_at = datetime.now(UTC)
    session.add(version)
    session.flush()
    return version


def load_assets(session: Session, ids: set[str]) -> list[AssetInfo]:
    if not ids:
        return []
    rows = session.scalars(select(Asset).where(Asset.id.in_(ids))).all()
    return [AssetInfo(a.id, a.storage_key, a.mime, a.width, a.height) for a in rows]


def assets_for(
    session: Session, template: TemplateDefinition, brand: BrandKitData, document: PostDocument
) -> list[AssetInfo]:
    return load_assets(session, referenced_asset_ids(template, brand, document))
