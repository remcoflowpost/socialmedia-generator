import re
import unicodedata
from datetime import UTC, datetime

EMBARGO_PREFIX = "EMBARGO_"


def slugify(value: str, max_length: int = 60) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", normalized.lower()).strip("-")
    return slug[:max_length].strip("-") or "post"


def embargo_active(embargo_until: datetime | None, now: datetime | None = None) -> bool:
    return bool(embargo_until and embargo_until > (now or datetime.now(UTC)))


def export_filename(
    company_slug: str,
    post_slug: str,
    platform: str,
    format_id: str,
    version: int,
    extension: str,
    embargo: bool = False,
) -> str:
    """{company-slug}_{post-slug}_{platform}-{format-id}_v{version:03d}.{ext}, met EMBARGO_
    ervoor als het embargo nog loopt."""
    name = f"{company_slug}_{post_slug}_{platform}-{format_id}_v{version:03d}.{extension}"
    return f"{EMBARGO_PREFIX}{name}" if embargo else name


def zip_filename(company_slug: str, post_slug: str, version: int, embargo: bool = False) -> str:
    name = f"{company_slug}_{post_slug}_alle-formaten_v{version:03d}.zip"
    return f"{EMBARGO_PREFIX}{name}" if embargo else name
