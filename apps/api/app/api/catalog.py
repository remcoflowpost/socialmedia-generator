"""Formaten, templates, companies en brand kits."""

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException
from pydantic import ValidationError
from sqlalchemy import select

from app.api.deps import AdminUser, CurrentUser, DbSession
from app.api.serializers import company_out
from app.domain.config_loader import load_formats
from app.models import BrandKit, Company, Template
from app.schema import BrandKitData

router = APIRouter(prefix="/api", tags=["catalog"])


@router.get("/formats")
def formats(_: CurrentUser) -> list[dict]:
    return [f.model_dump(by_alias=True) | {"key": f.key} for f in load_formats().formats]


@router.get("/templates")
def templates(_: CurrentUser, session: DbSession) -> list[dict]:
    rows = session.scalars(select(Template).where(Template.active).order_by(Template.name))
    return [row.definition for row in rows]


@router.get("/companies")
def companies(_: CurrentUser, session: DbSession) -> list[dict]:
    rows = session.scalars(select(Company).where(Company.active).order_by(Company.name))
    return [company_out(c) for c in rows]


@router.get("/companies/{company_id}/brand-kit")
def brand_kit(company_id: str, _: CurrentUser, session: DbSession) -> dict:
    kit = session.scalar(select(BrandKit).where(BrandKit.company_id == company_id))
    if not kit:
        raise HTTPException(404, "Geen brand kit.")
    return {"data": kit.data, "version": kit.version}


@router.put("/companies/{company_id}/brand-kit")
def update_brand_kit(company_id: str, body: dict, _: AdminUser, session: DbSession) -> dict:
    try:
        data = BrandKitData.model_validate(body)
    except ValidationError as error:
        raise HTTPException(422, error.errors(include_url=False)) from error
    kit = session.scalar(select(BrandKit).where(BrandKit.company_id == company_id))
    if not kit:
        kit = BrandKit(company_id=company_id, data={}, version=0)
        session.add(kit)
    kit.data = data.model_dump(by_alias=True)
    kit.version += 1
    kit.updated_at = datetime.now(UTC)
    session.commit()
    return {"data": kit.data, "version": kit.version}
