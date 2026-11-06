"""Publiceren naar social media via de ingestelde provider (mock of Postiz)."""

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.api.serializers import job_out
from app.domain.publish import (
    PublishBody,
    PublishRejected,
    channels_for_company,
    prepare_publication,
)
from app.jobs.queue import enqueue
from app.models import Company, Job
from app.publishing import PublishError, get_provider

router = APIRouter(prefix="/api/publish", tags=["publish"])


def _provider():
    try:
        return get_provider()
    except PublishError as error:
        raise HTTPException(503, str(error)) from error


@router.get("/channels")
def channels(company_id: str, _: CurrentUser, session: DbSession) -> dict:
    company = session.get(Company, company_id)
    if not company:
        raise HTTPException(404, "Onbekend bedrijf.")
    provider = _provider()
    try:
        rows, matched = channels_for_company(provider.list_channels(), company)
    except PublishError as error:
        raise HTTPException(502, str(error)) from error
    return {
        "provider": provider.name,
        "matchedCompany": matched,
        "channels": [
            {
                "id": c.id,
                "name": c.name,
                "platform": c.platform,
                "picture": c.picture,
                "disabled": c.disabled,
                "group": c.group,
            }
            for c in rows
        ],
    }


@router.post("")
def publish(body: PublishBody, user: CurrentUser, session: DbSession) -> dict:
    provider = _provider()
    try:
        payload = prepare_publication(session, body, provider)
    except PublishRejected as error:
        raise HTTPException(error.status, str(error)) from error
    except PublishError as error:
        raise HTTPException(502, str(error)) from error
    job = enqueue(session, "publish", payload | {"provider": provider.name}, user.id)
    session.commit()
    return job_out(job)


@router.get("/history")
def history(company_id: str, _: CurrentUser, session: DbSession) -> list[dict]:
    rows = session.scalars(
        select(Job)
        .where(Job.type == "publish", Job.payload["companyId"].astext == company_id)
        .order_by(Job.created_at.desc())
        .limit(50)
    )
    return [
        job_out(job)
        | {
            "caption": job.payload.get("caption", ""),
            "mode": job.payload.get("mode"),
            "date": job.payload.get("date"),
            "provider": job.payload.get("provider"),
            "channels": [item["channel"]["name"] for item in job.payload.get("items", [])],
            "files": sorted(
                {m["filename"] for item in job.payload.get("items", []) for m in item["media"]}
            ),
        }
        for job in rows
    ]
