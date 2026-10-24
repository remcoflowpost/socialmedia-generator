from app.models import Asset, Company, Job, Post


def asset_out(asset: Asset) -> dict:
    return {
        "id": asset.id,
        "companyId": asset.company_id,
        "kind": asset.kind,
        "filename": asset.filename,
        "mime": asset.mime,
        "width": asset.width,
        "height": asset.height,
        "colorProfile": asset.color_profile,
        "tags": asset.tags,
        "origin": asset.origin,
        "provenance": asset.provenance,
        "parentAssetId": asset.parent_asset_id,
        "url": f"/api/assets/{asset.id}/file",
        "createdAt": asset.created_at.isoformat(),
    }


def company_out(company: Company) -> dict:
    return {"id": company.id, "name": company.name, "slug": company.slug, "active": company.active}


def post_out(post: Post) -> dict:
    return {
        "id": post.id,
        "companyId": post.company_id,
        "templateKey": post.template.key,
        "title": post.title,
        "slug": post.slug,
        "document": post.document,
        "status": post.status,
        "embargoUntil": post.embargo_until.isoformat() if post.embargo_until else None,
        "clientApproved": post.client_approved,
        "currentVersion": post.current_version,
        "updatedAt": post.updated_at.isoformat(),
    }


def job_out(job: Job) -> dict:
    return {
        "id": job.id,
        "type": job.type,
        "status": job.status,
        "progress": job.progress,
        "result": job.result,
        "error": job.error.splitlines()[0] if job.error else None,
        "createdAt": job.created_at.isoformat(),
    }
