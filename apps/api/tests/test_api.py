"""Integratietest tegen een echte Postgres. Wordt overgeslagen zonder TEST_DATABASE_URL.

TEST_DATABASE_URL=postgresql+psycopg://flow:flow@localhost:5432/flow_social_test pytest
"""

import os

import pytest

TEST_DB = os.environ.get("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not TEST_DB, reason="TEST_DATABASE_URL niet gezet")


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient

    from app import seed
    from app.db import Base, engine
    from app.main import create_app

    # Vangnet: deze fixture gooit alle tabellen weg.
    if "test" not in (engine.url.database or ""):
        pytest.exit(f"Weiger tests te draaien tegen database {engine.url.database!r}", returncode=2)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    seed.main()
    return TestClient(create_app())


def login(client, email: str) -> None:
    client.cookies.clear()
    response = client.post("/api/auth/dev-login", json={"email": email})
    assert response.status_code == 200, response.text


def first_post(client, slug: str, template: str) -> dict:
    company = next(c for c in client.get("/api/companies").json() if c["slug"] == slug)
    return next(
        p
        for p in client.get(f"/api/posts?company_id={company['id']}").json()
        if p["templateKey"] == template
    )


def test_unknown_user_is_refused(client) -> None:
    client.cookies.clear()
    assert (
        client.post("/api/auth/dev-login", json={"email": "vreemde@example.test"}).status_code
        == 403
    )
    assert client.get("/api/companies").status_code == 401


def test_editor_cannot_override_logo_but_admin_can(client) -> None:
    login(client, "editor@example.test")
    post = first_post(client, "bedrijf-b", "project_announcement")
    locked = {"document": {**post["document"], "overrides": {"logo": {"hidden": True}}}}
    response = client.put(f"/api/posts/{post['id']}", json=locked)
    assert response.status_code == 422
    assert "logo" in response.json()["detail"]

    login(client, "admin@example.test")
    assert client.put(f"/api/posts/{post['id']}", json=locked).status_code == 200


def test_editor_cannot_edit_brand_kit(client) -> None:
    login(client, "editor@example.test")
    company = client.get("/api/companies").json()[0]
    kit = client.get(f"/api/companies/{company['id']}/brand-kit").json()["data"]
    assert client.put(f"/api/companies/{company['id']}/brand-kit", json=kit).status_code == 403


def test_render_context_contains_brand_of_sender(client) -> None:
    login(client, "editor@example.test")
    post = first_post(client, "bedrijf-b", "team_member")
    context = client.get(f"/api/posts/{post['id']}/render-context").json()
    assert context["brand"]["colors"]["accent"] == "#39d0b4"
    assert context["brand"]["logos"]["logoLight"] in context["assets"]
    assert len(context["formats"]) == 10


def test_upload_converts_and_lists_asset(client) -> None:
    import io

    from PIL import Image

    login(client, "editor@example.test")
    company = client.get("/api/companies").json()[0]
    buffer = io.BytesIO()
    Image.new("RGB", (640, 480), "#884422").save(buffer, "PNG")
    response = client.post(
        "/api/assets",
        data={"company_id": company["id"], "kind": "image", "tags": "Test, still"},
        files={"file": ("test.png", buffer.getvalue(), "image/png")},
    )
    assert response.status_code == 200, response.text
    asset = response.json()
    assert (asset["width"], asset["height"], asset["tags"]) == (640, 480, ["still", "test"])
    found = client.get(f"/api/assets?company_id={company['id']}&tag=test").json()
    assert [a["id"] for a in found] == [asset["id"]]
    assert client.get(asset["url"]).status_code == 200


def test_editor_cannot_upload_logo(client) -> None:
    login(client, "editor@example.test")
    company = client.get("/api/companies").json()[0]
    response = client.post(
        "/api/assets",
        data={"company_id": company["id"], "kind": "logo"},
        files={"file": ("logo.svg", b'<svg xmlns="http://www.w3.org/2000/svg"/>', "image/svg+xml")},
    )
    assert response.status_code == 403


def test_export_creates_version_and_job(client) -> None:
    login(client, "editor@example.test")
    post = first_post(client, "bedrijf-c", "project_announcement")
    job = client.post(f"/api/posts/{post['id']}/export", json={}).json()
    assert job["status"] == "queued"
    assert client.get(f"/api/posts/{post['id']}").json()["currentVersion"] == 1
