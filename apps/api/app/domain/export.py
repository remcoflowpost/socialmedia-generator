"""Export van een postversie naar alle (of gekozen) formaten, uitgevoerd door de worker."""

import io
import zipfile
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import httpx
from sqlalchemy.orm import Session

from app.domain.config_loader import load_formats
from app.domain.naming import embargo_active, export_filename, zip_filename
from app.domain.posts import assets_for
from app.domain.quality import max_severity, with_embargo
from app.domain.render_input import AssetInfo, build_render_input
from app.models import Post, PostVersion, QualityReport
from app.schema import BrandKitData, LayoutReport, PostDocument, TemplateDefinition
from app.settings import get_settings
from app.storage import get_storage

RENDER_TIMEOUT = httpx.Timeout(180.0, connect=10.0)
# Gelijk aan RENDER_CONCURRENCY van de render-service.
RENDER_PARALLEL = 2


def _render_url_for(asset: AssetInfo) -> str:
    return f"{get_settings().render_asset_base_url}/{asset.storage_key}"


def export_version(
    session: Session,
    post: Post,
    version: PostVersion,
    format_keys: list[str] | None,
    image_type: str,
    on_progress: Callable[[float], None],
) -> dict:
    snapshot = version.snapshot
    template = TemplateDefinition.model_validate(snapshot["template"])
    brand = BrandKitData.model_validate(snapshot["brand"])
    document = PostDocument.model_validate(snapshot["document"])
    embargo_until = (
        datetime.fromisoformat(snapshot["embargoUntil"]) if snapshot.get("embargoUntil") else None
    )
    embargo = embargo_active(embargo_until)

    formats = [f for f in load_formats().formats if not format_keys or f.key in format_keys]
    if template.formats:
        formats = [f for f in formats if f.key in template.formats]
    if not formats:
        raise ValueError("Geen formaten om te exporteren.")

    assets = assets_for(session, template, brand, document)
    storage = get_storage()
    extension = "jpg" if image_type == "jpeg" else "png"
    folder = f"exports/{post.id}/v{version.number:03d}"
    files: list[dict] = []

    jobs = []
    for fmt in formats:
        name = export_filename(
            post.company.slug,
            snapshot["slug"],
            fmt.platform,
            fmt.id,
            version.number,
            extension,
            embargo,
        )
        render_input = build_render_input(fmt, template, brand, document, assets, _render_url_for)
        jobs.append(
            (fmt, name, f"{folder}/{name}", render_input.model_dump(by_alias=True, mode="json"))
        )

    def render(client: httpx.Client, job: tuple) -> dict:
        _, _, key, payload = job
        response = client.post(
            "/render", json={"input": payload, "type": image_type, "output": key}
        )
        response.raise_for_status()
        return response.json()

    # HTTP parallel, database alleen in deze thread.
    with (
        httpx.Client(base_url=get_settings().render_url, timeout=RENDER_TIMEOUT) as client,
        ThreadPoolExecutor(RENDER_PARALLEL) as pool,
    ):
        results = pool.map(lambda job: render(client, job), jobs)
        for index, ((fmt, name, key, _), body) in enumerate(zip(jobs, results, strict=True)):
            report = with_embargo(LayoutReport.model_validate(body["report"]), embargo_until)
            severity = max_severity(report.issues)
            session.add(
                QualityReport(
                    post_id=post.id,
                    version=version.number,
                    format_key=fmt.key,
                    report=report.model_dump(by_alias=True, mode="json"),
                    max_severity=severity,
                )
            )
            files.append({"formatKey": fmt.key, "key": key, "name": name, "severity": severity})
            on_progress((index + 1) / (len(formats) + 1))

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_STORED) as archive:
        for entry in files:
            archive.write(storage.local_path(entry["key"]), arcname=entry["name"])
    zip_name = zip_filename(post.company.slug, snapshot["slug"], version.number, embargo)
    zip_key = f"{folder}/{zip_name}"
    storage.write(zip_key, buffer.getvalue())

    return {
        "zipKey": zip_key,
        "zipName": zip_name,
        "files": files,
        "version": version.number,
        "embargo": embargo,
        "maxSeverity": max_severity_of(files),
    }


def max_severity_of(files: list[dict]) -> str | None:
    severities = {f["severity"] for f in files}
    if "error" in severities:
        return "error"
    if "warning" in severities:
        return "warning"
    return None
