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


def test_upload_video_and_publish_via_mock(client) -> None:
    import io

    from PIL import Image

    from app.worker import run_once

    login(client, "editor@example.test")
    company = client.get("/api/companies").json()[0]
    buffer = io.BytesIO()
    Image.new("RGB", (1080, 1080), "#224488").save(buffer, "JPEG")
    image = client.post(
        "/api/assets",
        data={"company_id": company["id"], "kind": "image"},
        files={"file": ("post.jpg", buffer.getvalue(), "image/jpeg")},
    ).json()
    video = client.post(
        "/api/assets",
        data={"company_id": company["id"], "kind": "video"},
        files={"file": ("clip.mp4", b"\x00\x00\x00\x18ftypmp42", "video/mp4")},
    )
    assert video.status_code == 200, video.text
    assert video.json()["mime"] == "video/mp4"
    bad = client.post(
        "/api/assets",
        data={"company_id": company["id"], "kind": "video"},
        files={"file": ("clip.avi", b"x", "video/x-msvideo")},
    )
    assert bad.status_code == 415

    channels = client.get(f"/api/publish/channels?company_id={company['id']}").json()
    assert channels["provider"] == "mock"
    ids = [c["id"] for c in channels["channels"]]
    job = client.post(
        "/api/publish",
        json={
            "company_id": company["id"],
            "caption": "Nieuwe post",
            "mode": "now",
            "channels": [
                {"channel_id": ids[0], "media": [{"asset_id": image["id"]}]},
                {"channel_id": ids[1], "media": [{"asset_id": video.json()["id"]}]},
            ],
        },
    )
    assert job.status_code == 200, job.text
    while run_once():
        pass
    done = client.get(f"/api/jobs/{job.json()['id']}").json()
    assert done["status"] == "done", done
    assert len(done["result"]["posts"]) == 2
    history = client.get(f"/api/publish/history?company_id={company['id']}").json()
    assert history[0]["files"] == ["clip.mp4", "post.jpg"]


def test_publish_rejects_unknown_channel_past_date_and_embargo(client) -> None:
    from datetime import UTC, datetime, timedelta

    from app.db import SessionLocal
    from app.models import Job, Post

    login(client, "editor@example.test")
    post = first_post(client, "bedrijf-c", "project_announcement")
    base = {"company_id": post["companyId"], "caption": "x"}
    unknown = client.post("/api/publish", json=base | {"channels": [{"channel_id": "nope"}]})
    assert unknown.status_code == 404
    past = client.post(
        "/api/publish",
        json=base
        | {
            "mode": "schedule",
            "scheduled_at": "2020-01-01T10:00:00Z",
            "channels": [{"channel_id": "mock-instagram"}],
        },
    )
    assert past.status_code == 422

    with SessionLocal() as session:
        row = session.get(Post, post["id"])
        row.embargo_until = datetime.now(UTC) + timedelta(days=2)
        export = Job(
            type="export",
            status="done",
            payload={"postId": post["id"]},
            result={
                "files": [
                    {"formatKey": "instagram/feed-square", "key": "x.jpg", "name": "EMBARGO_x.jpg"}
                ]
            },
        )
        session.add(export)
        session.commit()
        export_id = export.id
    media = [{"export_job_id": export_id, "file": "EMBARGO_x.jpg"}]
    channel = [{"channel_id": "mock-instagram", "media": media}]
    blocked = client.post("/api/publish", json=base | {"channels": channel})
    assert blocked.status_code == 409
    draft = client.post("/api/publish", json=base | {"mode": "draft", "channels": channel})
    assert draft.status_code == 200, draft.text
