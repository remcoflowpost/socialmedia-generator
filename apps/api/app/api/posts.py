from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, ValidationError
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.api.serializers import asset_out, job_out, post_out
from app.domain.config_loader import load_formats
from app.domain.locks import LockViolation, validate_document
from app.domain.naming import slugify
from app.domain.posts import PostError, brand_of, create_version, template_of
from app.domain.quality import can_mark_ready
from app.domain.render_input import referenced_asset_ids
from app.jobs.queue import enqueue
from app.models import Asset, Company, Job, Post, PostVersion, QualityReport, Template
from app.schema import LayoutReport, PostDocument
from app.storage import get_storage

router = APIRouter(prefix="/api", tags=["posts"])


class PostCreate(BaseModel):
    company_id: str
    template_key: str
    title: str


class PostUpdate(BaseModel):
    title: str | None = None
    document: dict | None = None
    embargo_until: datetime | None = None
    clear_embargo: bool = False


class ExportRequest(BaseModel):
    format_keys: list[str] | None = None
    type: str = "jpeg"


def _get_post(session, post_id: str) -> Post:
    post = session.get(Post, post_id)
    if not post:
        raise HTTPException(404, "Post niet gevonden.")
    return post


@router.get("/posts")
def list_posts(_: CurrentUser, session: DbSession, company_id: str | None = None) -> list[dict]:
    stmt = select(Post).order_by(Post.updated_at.desc())
    if company_id:
        stmt = stmt.where(Post.company_id == company_id)
    return [post_out(p) for p in session.scalars(stmt.limit(200))]


@router.post("/posts")
def create_post(body: PostCreate, user: CurrentUser, session: DbSession) -> dict:
    company = session.get(Company, body.company_id)
    template = session.scalar(select(Template).where(Template.key == body.template_key))
    if not company or not template:
        raise HTTPException(404, "Onbekend bedrijf of template.")
    post = Post(
        company_id=company.id,
        template_id=template.id,
        title=body.title.strip() or template.name,
        slug=slugify(body.title or template.name),
        document=PostDocument().model_dump(by_alias=True),
        author_id=user.id,
    )
    session.add(post)
    session.commit()
    return post_out(post)


@router.get("/posts/{post_id}")
def get_post(post_id: str, _: CurrentUser, session: DbSession) -> dict:
    return post_out(_get_post(session, post_id))


@router.put("/posts/{post_id}")
def update_post(post_id: str, body: PostUpdate, user: CurrentUser, session: DbSession) -> dict:
    """Autosave: overschrijft de werkkopie, maakt geen versie."""
    post = _get_post(session, post_id)
    if body.document is not None:
        try:
            document = PostDocument.model_validate(body.document)
            validate_document(document, template_of(post), brand_of(post), user.role)
        except (ValidationError, LockViolation, PostError) as error:
            raise HTTPException(422, str(error)) from error
        post.document = document.model_dump(by_alias=True)
    if body.title is not None and body.title.strip():
        post.title = body.title.strip()
        post.slug = slugify(post.title)
    if body.clear_embargo:
        post.embargo_until = None
    elif body.embargo_until is not None:
        post.embargo_until = (
            body.embargo_until
            if body.embargo_until.tzinfo
            else body.embargo_until.replace(tzinfo=UTC)
        )
    post.updated_at = datetime.now(UTC)
    session.commit()
    return post_out(post)


@router.get("/posts/{post_id}/render-context")
def render_context(post_id: str, _: CurrentUser, session: DbSession) -> dict:
    """Alles wat de browser-preview nodig heeft. De preview stelt hieruit zelf RenderInput
    samen, zodat typen geen netwerkverkeer kost."""
    post = _get_post(session, post_id)
    try:
        template, brand = template_of(post), brand_of(post)
    except PostError as error:
        raise HTTPException(409, str(error)) from error
    document = PostDocument.model_validate(post.document)
    ids = referenced_asset_ids(template, brand, document)
    assets = session.scalars(select(Asset).where(Asset.id.in_(ids))).all() if ids else []
    return {
        "post": post_out(post),
        "template": template.model_dump(by_alias=True),
        "brand": brand.model_dump(by_alias=True),
        "assets": {a.id: asset_out(a) for a in assets},
        "formats": [f.model_dump(by_alias=True) for f in load_formats().formats],
    }


@router.post("/posts/{post_id}/versions")
def save_version(post_id: str, user: CurrentUser, session: DbSession) -> dict:
    post = _get_post(session, post_id)
    version = create_version(session, post, "opgeslagen", user.id)
    session.commit()
    return {"number": version.number}


@router.get("/posts/{post_id}/versions")
def list_versions(post_id: str, _: CurrentUser, session: DbSession) -> list[dict]:
    rows = session.scalars(
        select(PostVersion)
        .where(PostVersion.post_id == post_id)
        .order_by(PostVersion.number.desc())
    )
    return [
        {
            "number": v.number,
            "reason": v.reason,
            "createdAt": v.created_at.isoformat(),
            "snapshot": v.snapshot,
        }
        for v in rows
    ]


@router.post("/posts/{post_id}/export")
def export_post(post_id: str, body: ExportRequest, user: CurrentUser, session: DbSession) -> dict:
    if body.type not in ("jpeg", "png"):
        raise HTTPException(422, "Type moet jpeg of png zijn.")
    post = _get_post(session, post_id)
    version = create_version(session, post, "export", user.id)
    job = enqueue(
        session,
        "export",
        {
            "postId": post.id,
            "versionId": version.id,
            "formatKeys": body.format_keys,
            "type": body.type,
        },
        user.id,
    )
    session.commit()
    return job_out(job)


@router.get("/posts/{post_id}/quality")
def quality(post_id: str, _: CurrentUser, session: DbSession) -> dict:
    post = _get_post(session, post_id)
    rows = session.scalars(
        select(QualityReport).where(
            QualityReport.post_id == post.id, QualityReport.version == post.current_version
        )
    ).all()
    reports = [LayoutReport.model_validate(r.report) for r in rows]
    ready, reasons = can_mark_ready(reports, post.client_approved)
    return {
        "version": post.current_version,
        "reports": [r.report for r in rows],
        "canApprove": ready,
        "reasons": reasons,
    }


@router.get("/jobs/{job_id}")
def get_job(job_id: str, _: CurrentUser, session: DbSession) -> dict:
    job = session.get(Job, job_id)
    if not job:
        raise HTTPException(404)
    return job_out(job)


@router.get("/jobs/{job_id}/download")
def download(
    job_id: str, _: CurrentUser, session: DbSession, file: str | None = None
) -> FileResponse:
    job = session.get(Job, job_id)
    if not job or job.status != "done" or not job.result:
        raise HTTPException(404, "Export is nog niet klaar.")
    if file:
        entry = next((f for f in job.result["files"] if f["name"] == file), None)
        if not entry:
            raise HTTPException(404)
        return FileResponse(get_storage().local_path(entry["key"]), filename=entry["name"])
    return FileResponse(
        get_storage().local_path(job.result["zipKey"]),
        filename=job.result["zipName"],
        media_type="application/zip",
    )
