from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import or_, select

from app.api.deps import CurrentUser, DbSession
from app.api.serializers import asset_out
from app.domain.fonts import FontRejected, inspect_font
from app.domain.images import UnsupportedFile, ingest_image
from app.models import Asset, Company
from app.storage import get_storage

router = APIRouter(prefix="/api/assets", tags=["assets"])

MAX_UPLOAD_BYTES = 200 * 1024 * 1024
ASSET_KINDS = ("image", "logo", "font", "background", "element")
# Merkmateriaal: alleen admins, zodat de brand library consistent blijft.
ADMIN_KINDS = ("logo", "font", "background", "element")
ELEMENT_MIMES = ("image/png", "image/svg+xml")


@router.get("")
def list_assets(
    _: CurrentUser,
    session: DbSession,
    company_id: str,
    q: str | None = None,
    origin: str | None = None,
    kind: Annotated[list[str] | None, Query()] = None,
    tag: Annotated[list[str] | None, Query()] = None,
) -> list[dict]:
    stmt = select(Asset).where(Asset.company_id == company_id).order_by(Asset.created_at.desc())
    if origin:
        stmt = stmt.where(Asset.origin == origin)
    if kind:
        stmt = stmt.where(Asset.kind.in_(kind))
    if tag:
        stmt = stmt.where(Asset.tags.contains(tag))
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(or_(Asset.filename.ilike(like), Asset.tags.any(q.lower())))
    return [asset_out(a) for a in session.scalars(stmt.limit(500))]


@router.post("")
async def upload_asset(
    user: CurrentUser,
    session: DbSession,
    company_id: Annotated[str, Form()],
    file: Annotated[UploadFile, File()],
    kind: Annotated[str, Form()] = "image",
    tags: Annotated[str, Form()] = "",
) -> dict:
    company = session.get(Company, company_id)
    if not company:
        raise HTTPException(404, "Onbekend bedrijf.")
    if kind not in ASSET_KINDS:
        raise HTTPException(422, f"Onbekende soort {kind!r}.")
    if kind in ADMIN_KINDS and user.role != "admin":
        raise HTTPException(
            403, "Alleen admins uploaden logo's, fonts, achtergronden en elementen."
        )
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "Bestand is groter dan 200 MB.")

    asset = Asset(
        company_id=company.id,
        kind=kind,
        filename=file.filename or "upload",
        owner_id=user.id,
        tags=sorted({t.strip().lower() for t in tags.split(",") if t.strip()}),
        origin="upload",
        provenance={"source": "upload", "originalFilename": file.filename},
    )
    storage = get_storage()
    base = f"companies/{company.slug}/assets/{asset.id}"
    try:
        if kind == "font":
            try:
                font = inspect_font(data)
            except FontRejected as error:
                raise HTTPException(415, str(error)) from error
            asset.mime = font.mime
            asset.storage_key = f"{base}{font.extension}"
            asset.provenance = {
                **asset.provenance,
                "fontFamily": font.family,
                "fontSubfamily": font.subfamily,
                "embedding": font.embedding,
            }
            storage.write(asset.storage_key, data)
        else:
            image = ingest_image(data, asset.filename)
            if kind == "element" and image.mime not in ELEMENT_MIMES:
                raise HTTPException(
                    415,
                    "Elementen moeten transparant zijn: "
                    "upload een PNG met transparantie of een SVG.",
                )
            if image.mime == "image/svg+xml" and image.converted:
                asset.provenance = {**asset.provenance, "sanitized": True}
            asset.mime, asset.width, asset.height = image.mime, image.width, image.height
            asset.color_profile = image.color_profile
            asset.storage_key = f"{base}{image.extension}"
            storage.write(asset.storage_key, image.data)
            if image.converted:
                suffix = (
                    asset.filename[asset.filename.rfind(".") :].lower()
                    if "." in asset.filename
                    else ""
                )
                asset.original_key = f"{base}.original{suffix}"
                storage.write(asset.original_key, data)
    except UnsupportedFile as error:
        raise HTTPException(415, str(error)) from error

    session.add(asset)
    session.commit()
    return asset_out(asset)


@router.patch("/{asset_id}")
def update_tags(asset_id: str, body: dict, _: CurrentUser, session: DbSession) -> dict:
    asset = session.get(Asset, asset_id)
    if not asset:
        raise HTTPException(404)
    asset.tags = sorted({str(t).strip().lower() for t in body.get("tags", []) if str(t).strip()})
    session.commit()
    return asset_out(asset)


@router.get("/{asset_id}/file")
def asset_file(asset_id: str, _: CurrentUser, session: DbSession) -> FileResponse:
    asset = session.get(Asset, asset_id)
    if not asset:
        raise HTTPException(404)
    headers = {"X-Content-Type-Options": "nosniff"}
    if asset.mime == "image/svg+xml":
        # Extra slot: ook als er ooit iets door de opschoning glipt, voert de browser het
        # bij direct openen niet uit.
        headers["Content-Security-Policy"] = (
            "default-src 'none'; style-src 'unsafe-inline'; img-src data:"
        )
    return FileResponse(
        get_storage().local_path(asset.storage_key), media_type=asset.mime, headers=headers
    )
