"""Regels voor publicaties: welk formaat naar welk platform, bijschriftlimieten en de
voorwaarden waaronder een post gepubliceerd mag worden. Pure functies, server-side
afgedwongen (zie docs/publiceren.md, "Bedrijfsregels")."""

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timedelta

MAX_AHEAD = timedelta(days=366)
_CONTROL = re.compile(r"[\u0000-\u0008\u000b-\u001f\u007f‪-‮⁦-⁩]")
_HASHTAG = re.compile(r"(?<!\w)#\w+", re.UNICODE)


@dataclass(frozen=True)
class PlatformSpec:
    provider: str
    label: str
    formats: tuple[str, ...]
    caption_limit: int
    max_hashtags: int | None
    image_types: tuple[str, ...]
    max_image_bytes: int
    min_aspect: float | None  # breedte / hoogte
    max_aspect: float | None
    captions: bool = True
    daily_limit: int | None = None


PLATFORMS: dict[str, PlatformSpec] = {
    "instagram": PlatformSpec(
        provider="instagram",
        label="Instagram",
        # instagram/feed-3x4 ontbreekt bewust: Meta weigert verhoudingen smaller dan 4:5.
        formats=("instagram/feed-square", "instagram/feed-portrait", "instagram/story"),
        caption_limit=2200,
        max_hashtags=30,
        image_types=("image/jpeg",),
        max_image_bytes=8 * 1024 * 1024,
        min_aspect=4 / 5,
        max_aspect=1.91,
        daily_limit=100,
    ),
    "facebook_page": PlatformSpec(
        provider="facebook_page",
        label="Facebook-pagina",
        formats=("facebook/feed-landscape", "facebook/feed-square"),
        caption_limit=63206,
        max_hashtags=None,
        image_types=("image/jpeg", "image/png"),
        max_image_bytes=10 * 1024 * 1024,
        min_aspect=None,
        max_aspect=None,
    ),
    "sandbox": PlatformSpec(
        provider="sandbox",
        label="Sandbox",
        formats=(
            "instagram/feed-square",
            "instagram/feed-portrait",
            "facebook/feed-landscape",
            "facebook/feed-square",
        ),
        caption_limit=2200,
        max_hashtags=30,
        image_types=("image/jpeg", "image/png"),
        max_image_bytes=8 * 1024 * 1024,
        min_aspect=None,
        max_aspect=None,
    ),
}

STORY_FORMATS = {"instagram/story"}


def normalize_caption(text: str) -> str:
    text = unicodedata.normalize("NFC", text or "").replace("\r\n", "\n").replace("\r", "\n")
    text = _CONTROL.sub("", text)
    return "\n".join(line.rstrip() for line in text.split("\n")).strip()


def caption_length(text: str) -> int:
    """Instagram en Facebook tellen tekens als Unicode-codepunten."""
    return len(text)


@dataclass
class Issue:
    code: str
    field: str
    message: str


@dataclass
class PublishFacts:
    """Alles wat nodig is om te beslissen of een publicatie mag. Wordt bij inplannen en
    vlak voor verzenden opnieuw opgebouwd."""

    provider: str
    account_status: str
    account_company_id: str
    post_company_id: str
    format_key: str
    caption: str
    version_number: int
    approved_version: int | None
    embargo_until: datetime | None
    export_ok: bool
    export_severity: str | None
    media_mime: str | None
    media_bytes: int | None
    media_width: int | None
    media_height: int | None
    scheduled_at: datetime
    now: datetime
    published_last_24h: int = 0
    extra: dict = field(default_factory=dict)


def check_publishable(f: PublishFacts, *, at_send_time: bool = False) -> list[Issue]:
    issues: list[Issue] = []
    spec = PLATFORMS.get(f.provider)
    if spec is None:
        return [Issue("provider", "account", "Dit type account wordt niet ondersteund.")]
    if f.account_company_id != f.post_company_id:
        issues.append(Issue("company", "account", "Dit account hoort bij een ander bedrijf."))
    if f.account_status != "active":
        issues.append(
            Issue(
                "account",
                "account",
                "Dit account moet opnieuw gekoppeld worden."
                if f.account_status == "reauth_required"
                else "Dit account is ontkoppeld.",
            )
        )
    if f.format_key not in spec.formats:
        hint = (
            " Instagram accepteert geen 3:4 via de API; kies vierkant of portret (4:5)."
            if f.format_key == "instagram/feed-3x4"
            else ""
        )
        issues.append(
            Issue("format", "format", f"Formaat {f.format_key} kan niet naar {spec.label}.{hint}")
        )
    if f.approved_version is None:
        issues.append(Issue("approval", "post", "Klantakkoord ontbreekt."))
    elif f.approved_version != f.version_number:
        issues.append(
            Issue(
                "approval",
                "post",
                f"Klantakkoord geldt voor versie {f.approved_version}, niet voor versie "
                f"{f.version_number}.",
            )
        )
    if not f.export_ok:
        issues.append(Issue("export", "post", "Er is geen geslaagde export voor dit formaat."))
    elif f.export_severity == "error":
        issues.append(Issue("quality", "post", "De export van dit formaat heeft kwaliteitsfouten."))
    if f.media_mime and f.media_mime not in spec.image_types:
        kinds = " of ".join(t.split("/")[1].upper() for t in spec.image_types)
        issues.append(Issue("media_type", "post", f"{spec.label} accepteert alleen {kinds}."))
    if f.media_bytes and f.media_bytes > spec.max_image_bytes:
        issues.append(
            Issue(
                "media_size",
                "post",
                f"Beeld is {f.media_bytes / 1048576:.1f} MB; {spec.label} accepteert tot "
                f"{spec.max_image_bytes / 1048576:.0f} MB.",
            )
        )
    if f.media_width and f.media_height and spec.min_aspect and spec.max_aspect:
        ratio = f.media_width / f.media_height
        is_story = f.format_key in STORY_FORMATS
        if not is_story and not (spec.min_aspect - 0.005 <= ratio <= spec.max_aspect + 0.005):
            issues.append(
                Issue(
                    "aspect",
                    "post",
                    f"Verhouding {f.media_width}x{f.media_height} valt buiten 4:5 tot 1.91:1.",
                )
            )
    caption_issue = _check_caption(f.caption, spec, f.format_key)
    if caption_issue:
        issues.append(caption_issue)
    if f.embargo_until and f.scheduled_at < f.embargo_until:
        issues.append(
            Issue(
                "embargo",
                "schedule",
                f"De post staat onder embargo tot {f.embargo_until:%d-%m-%Y %H:%M} (UTC).",
            )
        )
    if not at_send_time:
        if f.scheduled_at <= f.now:
            issues.append(Issue("past", "schedule", "Dat tijdstip is al voorbij."))
        if f.scheduled_at - f.now > MAX_AHEAD:
            issues.append(Issue("too_far", "schedule", "Inplannen kan tot een jaar vooruit."))
    if spec.daily_limit and f.published_last_24h >= spec.daily_limit:
        issues.append(
            Issue(
                "daily_limit",
                "schedule",
                f"{spec.label} staat maximaal {spec.daily_limit} API-publicaties per 24 uur toe.",
            )
        )
    return issues


def _check_caption(caption: str, spec: PlatformSpec, format_key: str) -> Issue | None:
    if format_key in STORY_FORMATS and caption:
        return Issue("caption", "caption", "Instagram-stories hebben geen bijschrift.")
    length = caption_length(caption)
    if length > spec.caption_limit:
        return Issue(
            "caption",
            "caption",
            f"{length} van {spec.caption_limit} tekens: {length - spec.caption_limit} te veel "
            f"voor {spec.label}.",
        )
    if spec.max_hashtags is not None:
        tags = len(_HASHTAG.findall(caption))
        if tags > spec.max_hashtags:
            return Issue(
                "hashtags",
                "caption",
                f"{tags} hashtags; {spec.label} staat er maximaal {spec.max_hashtags} toe.",
            )
    return None
