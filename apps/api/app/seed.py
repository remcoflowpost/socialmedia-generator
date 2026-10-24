"""Seed-data: templates uit de repo, drie placeholderbedrijven met brand kits en een paar
placeholderbeelden. Geen echte klantbeelden, logo's of merkfonts.

    python -m app.seed

Idempotent: templates worden bijgewerkt, bestaande bedrijven worden overgeslagen.
"""

import io
import logging
import uuid
from dataclasses import dataclass

from PIL import Image, ImageColor, ImageDraw, ImageFilter
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.domain.config_loader import load_templates
from app.domain.images import ingest_image
from app.models import Asset, BrandKit, Company, Post, Template
from app.schema import BrandKitData, PostDocument
from app.settings import get_settings
from app.storage import get_storage

log = logging.getLogger("seed")


@dataclass
class SeedCompany:
    slug: str
    name: str
    colors: dict[str, str]
    heading_font: tuple[str, str, int]
    body_font: tuple[str, str, int]
    mark: str


COMPANIES = [
    SeedCompany(
        "flow-postproduction",
        "Flow Postproduction",
        {
            "primary": "#0f1720",
            "secondary": "#9ad0ff",
            "accent": "#ffb000",
            "textOnDark": "#ffffff",
            "textOnLight": "#0f1720",
        },
        ("Space Grotesk", "space-grotesk-latin-700-normal.woff2", 700),
        ("Inter", "inter-latin-400-normal.woff2", 400),
        "square",
    ),
    SeedCompany(
        "bedrijf-b",
        "Bedrijf B (placeholder)",
        {
            "primary": "#1d1a2f",
            "secondary": "#f4a6c1",
            "accent": "#39d0b4",
            "textOnDark": "#fdf6ec",
            "textOnLight": "#1d1a2f",
        },
        ("DM Serif Display", "dm-serif-display-latin-400-normal.woff2", 400),
        ("Work Sans", "work-sans-latin-400-normal.woff2", 400),
        "circle",
    ),
    SeedCompany(
        "bedrijf-c",
        "Bedrijf C (placeholder)",
        {
            "primary": "#1f3a2e",
            "secondary": "#e9c46a",
            "accent": "#f4845f",
            "textOnDark": "#fffdf7",
            "textOnLight": "#1f3a2e",
        },
        ("Archivo Black", "archivo-black-latin-400-normal.woff2", 400),
        ("IBM Plex Sans", "ibm-plex-sans-latin-400-normal.woff2", 400),
        "triangle",
    ),
]


def logo_svg(mark: str, color: str) -> bytes:
    """Abstract placeholderlogo zonder tekst, zodat er geen systeemfont nodig is."""
    shapes = {
        "square": f'<rect x="0" y="10" width="100" height="100" fill="{color}"/>',
        "circle": f'<circle cx="50" cy="60" r="50" fill="{color}"/>',
        "triangle": f'<polygon points="0,110 50,10 100,110" fill="{color}"/>',
    }
    bars = (
        f'<rect x="125" y="30" width="270" height="26" fill="{color}"/>'
        f'<rect x="125" y="70" width="170" height="20" fill="{color}" opacity="0.7"/>'
    )
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 120" width="400" height="120">'
        f"{shapes[mark]}{bars}</svg>"
    ).encode()


def placeholder_photo(
    width: int, height: int, palette: tuple[str, str, str], subject: str
) -> bytes:
    """Abstracte "still": verloop met een onderwerp, zodat crops en focuspunten zichtbaar zijn."""
    gradient = Image.new("RGB", (1, 2))
    gradient.putpixel((0, 0), ImageColor.getrgb(palette[0]))
    gradient.putpixel((0, 1), ImageColor.getrgb(palette[1]))
    image = gradient.resize((width, height), Image.Resampling.BILINEAR)
    draw = ImageDraw.Draw(image)
    if subject == "portrait":
        cx, cy, r = width * 0.5, height * 0.36, min(width, height) * 0.16
        draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=palette[2])
        draw.rounded_rectangle(
            (cx - r * 1.9, cy + r * 1.2, cx + r * 1.9, height * 1.1), radius=int(r), fill=palette[2]
        )
    else:
        cx, cy, r = width * 0.68, height * 0.42, min(width, height) * 0.28
        draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=palette[2])
        draw.rectangle((0, height * 0.78, width, height), fill=palette[0])
    image = image.filter(ImageFilter.GaussianBlur(radius=max(2, width // 800)))
    buffer = io.BytesIO()
    image.save(buffer, "JPEG", quality=88)
    return buffer.getvalue()


def _store_asset(
    session: Session,
    company: Company,
    kind: str,
    filename: str,
    data: bytes,
    tags: list[str],
    mime: str | None = None,
) -> Asset:
    storage = get_storage()
    asset = Asset(
        id=str(uuid.uuid4()),
        company_id=company.id,
        kind=kind,
        filename=filename,
        tags=tags,
        origin="upload",
        provenance={"source": "seed"},
    )
    base = f"companies/{company.slug}/assets/{asset.id}"
    if mime:
        asset.mime = mime
        asset.storage_key = f"{base}{filename[filename.rfind('.') :]}"
        storage.write(asset.storage_key, data)
    else:
        image = ingest_image(data, filename)
        asset.mime, asset.width, asset.height, asset.color_profile = (
            image.mime,
            image.width,
            image.height,
            image.color_profile,
        )
        asset.storage_key = f"{base}{image.extension}"
        storage.write(asset.storage_key, image.data)
    session.add(asset)
    session.flush()
    return asset


def seed_templates(session: Session) -> dict[str, Template]:
    rows: dict[str, Template] = {}
    for definition in load_templates():
        row = session.scalar(select(Template).where(Template.key == definition.key))
        if not row:
            row = Template(key=definition.key)
            session.add(row)
        row.name, row.type, row.version = definition.name, definition.type, definition.version
        row.definition = definition.model_dump(by_alias=True)
        rows[definition.key] = row
    session.flush()
    return rows


def seed_company(session: Session, spec: SeedCompany, templates: dict[str, Template]) -> None:
    if session.scalar(select(Company).where(Company.slug == spec.slug)):
        log.info("bedrijf %s bestaat al, overgeslagen", spec.slug)
        return
    company = Company(name=spec.name, slug=spec.slug)
    session.add(company)
    session.flush()

    fonts_dir = get_settings().seed_dir / "fonts"
    heading = _store_asset(
        session,
        company,
        "font",
        spec.heading_font[1],
        (fonts_dir / spec.heading_font[1]).read_bytes(),
        ["font"],
        "font/woff2",
    )
    body = _store_asset(
        session,
        company,
        "font",
        spec.body_font[1],
        (fonts_dir / spec.body_font[1]).read_bytes(),
        ["font"],
        "font/woff2",
    )
    logo_light = _store_asset(
        session, company, "logo", "logo-licht.svg", logo_svg(spec.mark, "#ffffff"), ["logo"]
    )
    logo_dark = _store_asset(
        session,
        company,
        "logo",
        "logo-donker.svg",
        logo_svg(spec.mark, spec.colors["primary"]),
        ["logo"],
    )

    brand = BrandKitData.model_validate(
        {
            "colors": spec.colors,
            "fonts": {
                "heading": {
                    "family": spec.heading_font[0],
                    "files": [{"assetId": heading.id, "weight": spec.heading_font[2]}],
                    "fallback": "Arial, sans-serif",
                },
                "body": {
                    "family": spec.body_font[0],
                    "files": [{"assetId": body.id, "weight": spec.body_font[2]}],
                    "fallback": "Arial, sans-serif",
                },
            },
            "logos": {"logoLight": logo_light.id, "logoDark": logo_dark.id},
            "styleAnchor": {"description": "Placeholder: donker, filmisch, veel negatieve ruimte."},
            "negativePrompt": "no text, no letters, no logos, no watermarks",
        }
    )
    session.add(BrandKit(company_id=company.id, data=brand.model_dump(by_alias=True), version=1))

    palette = (spec.colors["primary"], spec.colors["secondary"], spec.colors["accent"])
    still = _store_asset(
        session,
        company,
        "image",
        "placeholder-still.jpg",
        placeholder_photo(4000, 2250, palette, "still"),
        ["placeholder", "still"],
    )
    _store_asset(
        session,
        company,
        "image",
        "placeholder-te-klein.jpg",
        placeholder_photo(800, 450, palette, "still"),
        ["placeholder", "te-klein"],
    )
    portrait = _store_asset(
        session,
        company,
        "image",
        "placeholder-portret.jpg",
        placeholder_photo(2400, 3000, palette, "portrait"),
        ["placeholder", "portret"],
    )

    samples = [
        (
            "project_announcement",
            "Voorbeeld projectaankondiging",
            {
                "background_image": still.id,
                "label": "Nieuw project",
                "headline": "Een nieuwe serie vol vakmanschap",
                "client_or_project_name": "Placeholder Studio",
                "note": "Kleurcorrectie en VFX door het hele team.",
            },
        ),
        (
            "team_member",
            "Voorbeeld teamlid",
            {
                "portrait": portrait.id,
                "label": "Nieuw in het team",
                "person_name": "Sam Voorbeeld",
                "person_role": "Compositor",
                "quote": "Elke shot is een puzzel.",
            },
        ),
    ]
    for template_key, title, content in samples:
        session.add(
            Post(
                company_id=company.id,
                template_id=templates[template_key].id,
                title=title,
                slug=template_key.replace("_", "-"),
                document=PostDocument.model_validate({"content": content}).model_dump(
                    by_alias=True
                ),
            )
        )
    log.info("bedrijf %s aangemaakt", spec.slug)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    with SessionLocal() as session:
        templates = seed_templates(session)
        for spec in COMPANIES:
            seed_company(session, spec, templates)
        session.commit()


if __name__ == "__main__":
    main()
