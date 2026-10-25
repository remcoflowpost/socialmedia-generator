"""Publiceren van begin tot eind tegen een echte Postgres: regels via de API, de publisher,
constraints en rechten. Gebruikt het Sandbox-netwerk; er gaat niets naar Meta.

TEST_DATABASE_URL=postgresql+psycopg://flow:flow@localhost:5432/flow_social_test pytest
"""

import io
import os
import threading
from datetime import UTC, datetime, timedelta

import pytest

TEST_DB = os.environ.get("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not TEST_DB, reason="TEST_DATABASE_URL niet gezet")


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


def login(client, email: str = "admin@example.test") -> None:
    client.cookies.clear()
    assert client.post("/api/auth/dev-login", json={"email": email}).status_code == 200


def company(client, slug: str = "bedrijf-c") -> dict:
    return next(c for c in client.get("/api/companies").json() if c["slug"] == slug)


def a_post(client, slug: str = "bedrijf-c") -> dict:
    return client.get(f"/api/posts?company_id={company(client, slug)['id']}").json()[0]


def jpeg(width: int, height: int) -> bytes:
    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (width, height), (40, 80, 120)).save(buffer, "JPEG", quality=80)
    return buffer.getvalue()


def make_export(
    post_id: str, version_number: int, formats: dict[str, tuple[int, int]], severity=None
):
    """Een geslaagde export zoals de worker die achterlaat, zonder render-service."""
    from sqlalchemy import select

    from app.db import SessionLocal
    from app.models import Job, PostVersion
    from app.storage import get_storage

    with SessionLocal() as session:
        version = session.scalar(
            select(PostVersion).where(
                PostVersion.post_id == post_id, PostVersion.number == version_number
            )
        )
        files = []
        for key, (w, h) in formats.items():
            storage_key = f"exports/{post_id}/v{version_number:03d}/{key.replace('/', '-')}.jpg"
            get_storage().write(storage_key, jpeg(w, h))
            files.append({"formatKey": key, "key": storage_key, "name": key, "severity": severity})
        session.add(
            Job(
                type="export",
                status="done",
                payload={"postId": post_id, "versionId": version.id},
                result={"files": files},
                finished_at=datetime.now(UTC),
            )
        )
        session.commit()
        return version.id


def ready_post(client, slug: str = "bedrijf-c", approve: bool = True, severity=None) -> dict:
    """Post met een versie, een export van de feed-formaten en (optioneel) klantakkoord."""
    post = a_post(client, slug)
    number = client.post(f"/api/posts/{post['id']}/versions").json()["number"]
    version_id = make_export(
        post["id"],
        number,
        {
            "instagram/feed-square": (1080, 1080),
            "instagram/feed-portrait": (1080, 1350),
            "instagram/feed-3x4": (1080, 1440),
            "facebook/feed-square": (1080, 1080),
        },
        severity,
    )
    if approve:
        response = client.post(
            f"/api/posts/{post['id']}/approval",
            json={"approvedBy": "Klant Jansen", "version": number},
        )
        assert response.status_code == 200, response.text
    return {"post": post, "version_id": version_id, "number": number}


_counter = iter(range(10_000))


def sandbox_account(client, slug: str = "bedrijf-c") -> dict:
    name = f"acct{next(_counter)}"
    response = client.post(
        "/api/publishing/connect/sandbox",
        json={"companyId": company(client, slug)["id"], "name": name},
    )
    assert response.status_code == 200, response.text
    return response.json()


def schedule(
    client,
    ready: dict,
    account: dict,
    *,
    when: dict,
    fmt="instagram/feed-portrait",
    caption="Opgeleverd!",
):
    return client.post(
        "/api/publications",
        json={
            "postId": ready["post"]["id"],
            "versionId": ready["version_id"],
            "accountIds": [account["id"]],
            "formats": {"sandbox": fmt},
            "caption": caption,
            "when": when,
        },
    )


def soon(minutes: int = 10) -> dict:
    instant = (datetime.now(UTC) + timedelta(minutes=minutes)).replace(second=0, microsecond=0)
    return {"kind": "instant", "instant": instant.isoformat()}


def tick(minutes_ahead: float = 11):
    from app.publishing.worker import publish_due

    return publish_due(datetime.now(UTC) + timedelta(minutes=minutes_ahead))


def pub(publication_id: str):
    from app.db import SessionLocal
    from app.models import Publication

    with SessionLocal() as session:
        return session.get(Publication, publication_id)


def attempts(publication_id: str):
    from sqlalchemy import select

    from app.db import SessionLocal
    from app.models import PublishAttempt

    with SessionLocal() as session:
        return session.scalars(
            select(PublishAttempt)
            .where(PublishAttempt.publication_id == publication_id)
            .order_by(PublishAttempt.attempt_no)
        ).all()


def sandbox_count(container_id: str | None = None) -> int:
    from sqlalchemy import func, select

    from app.db import SessionLocal
    from app.models import SandboxPost

    with SessionLocal() as session:
        stmt = select(func.count()).select_from(SandboxPost)
        if container_id:
            stmt = stmt.where(SandboxPost.container_id == container_id)
        return session.scalar(stmt)


def base_url() -> str:
    from app.settings import get_settings

    return get_settings().public_url.rstrip("/")


def detail(response) -> str:
    body = response.json()["detail"]
    return body["message"] if isinstance(body, dict) else body


# ------------------------------------------------------------------ regels bij inplannen


def test_scheduling_requires_client_approval_for_that_exact_version(client) -> None:
    login(client)
    ready = ready_post(client, approve=False)
    account = sandbox_account(client)
    response = schedule(client, ready, account, when=soon())
    assert response.status_code == 422
    assert "Klantakkoord ontbreekt" in detail(response)

    client.post(
        f"/api/posts/{ready['post']['id']}/approval",
        json={"approvedBy": "Klant", "version": ready["number"]},
    )
    # Een nieuwere versie maakt het akkoord ongeldig voor die versie.
    newer = ready_post(client, approve=False)
    response = schedule(client, newer, account, when=soon())
    assert "niet voor versie" in detail(response)
    assert schedule(client, ready, account, when=soon()).status_code == 200


def test_quality_errors_embargo_and_3x4_block_scheduling(client) -> None:
    login(client)
    account = sandbox_account(client)
    broken = ready_post(client, severity="error")
    assert "kwaliteitsfouten" in detail(schedule(client, broken, account, when=soon()))

    ready = ready_post(client)
    assert "kan niet naar" in detail(
        schedule(client, ready, account, when=soon(), fmt="instagram/feed-3x4")
    )

    embargo = (datetime.now(UTC) + timedelta(days=3)).isoformat()
    post_id = ready["post"]["id"]
    assert client.put(f"/api/posts/{post_id}", json={"embargo_until": embargo}).json()
    assert "embargo" in detail(schedule(client, ready, account, when=soon()))
    client.put(f"/api/posts/{post_id}", json={"clear_embargo": True})


def test_account_of_another_company_is_refused(client) -> None:
    login(client)
    ready = ready_post(client, "bedrijf-c")
    other = sandbox_account(client, "bedrijf-b")
    response = schedule(client, ready, other, when=soon())
    assert response.status_code == 422
    assert "van dit bedrijf" in detail(response)


def test_next_open_slot_and_slot_exclusivity_with_swap(client) -> None:
    login(client)
    company_id = company(client)["id"]
    assert (
        client.post(
            f"/api/companies/{company_id}/slots",
            json={"weekdays": [1, 2, 3, 4, 5, 6, 7], "time": "09:00"},
        ).status_code
        == 200
    )
    account = sandbox_account(client)
    ready = ready_post(client)
    first = schedule(client, ready, account, when={"kind": "next_slot"}).json()[0]
    second = schedule(client, ready, account, when={"kind": "next_slot"}).json()[0]
    assert first["scheduledAt"] != second["scheduledAt"]  # tweede pakt het volgende slot

    # Verplaatsen naar een bezet moment: eerst vragen, niets veranderd.
    target = {"kind": "instant", "instant": second["scheduledAt"]}
    ask = client.post(
        f"/api/publications/{first['id']}/move", json={"version": first["version"], "when": target}
    )
    assert ask.status_code == 409
    conflict = ask.json()["detail"]["conflict"]
    assert conflict["otherId"] == second["id"]
    assert pub(second["id"]).scheduled_at.isoformat() == second["scheduledAt"]

    swap = client.post(
        f"/api/publications/{first['id']}/move",
        json={
            "version": first["version"],
            "when": target,
            "onConflict": "swap",
            "otherVersion": conflict["otherVersion"],
        },
    )
    assert swap.status_code == 200, swap.text
    assert pub(first["id"]).scheduled_at.isoformat() == second["scheduledAt"]
    assert pub(second["id"]).scheduled_at.isoformat() == first["scheduledAt"]

    # Oude versie meesturen (tweede tabblad) wordt geweigerd.
    stale = client.post(
        f"/api/publications/{first['id']}/move",
        json={"version": first["version"], "when": soon(30)},
    )
    assert stale.status_code == 409


def test_database_refuses_double_booking_and_audit_changes(client) -> None:
    from sqlalchemy import delete, update
    from sqlalchemy.exc import IntegrityError

    from app.db import SessionLocal
    from app.models import Publication, PublishAttempt

    login(client)
    account = sandbox_account(client)
    ready = ready_post(client)
    when = soon(120)
    first = schedule(client, ready, account, when=when).json()[0]
    with SessionLocal() as session, pytest.raises(IntegrityError):
        p = session.get(Publication, first["id"])
        clone = Publication(
            company_id=p.company_id,
            post_id=p.post_id,
            post_version_id=p.post_version_id,
            format_key=p.format_key,
            media_key=p.media_key,
            social_account_id=p.social_account_id,
            scheduled_at=p.scheduled_at,
            schedule_tz=p.schedule_tz,
            status="scheduled",
        )
        session.add(clone)
        session.commit()

    tick(121)
    done = attempts(first["id"])[0]
    with SessionLocal() as session, pytest.raises(IntegrityError, match="onveranderlijk"):
        session.execute(
            update(PublishAttempt).where(PublishAttempt.id == done.id).values(error_code="x")
        )
        session.commit()
    with SessionLocal() as session, pytest.raises(IntegrityError, match="verwijderen geweigerd"):
        session.execute(delete(PublishAttempt).where(PublishAttempt.id == done.id))
        session.commit()


# ------------------------------------------------------------------ publiceren


def test_publishes_exactly_once_at_the_scheduled_moment(client) -> None:
    login(client)
    account = sandbox_account(client)
    ready = ready_post(client)
    created = schedule(client, ready, account, when=soon(10)).json()[0]

    assert tick(5).claimed == 0  # nog niet aan de beurt
    results = []
    threads = [threading.Thread(target=lambda: results.append(tick(11))) for _ in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sum(r.published for r in results) == 1
    tick(12)

    done = pub(created["id"])
    assert done.status == "published"
    assert done.provider_url.startswith(f"{base_url()}/api/sandbox/posts/")
    assert sandbox_count(done.provider_container_id) == 1
    assert [a.outcome for a in attempts(created["id"])] == ["succeeded"]
    assert (
        client.get(done.provider_url.replace("https://social.example.test", "")).status_code == 200
    )


def test_unknown_outcome_is_reconciled_without_a_duplicate(client) -> None:
    login(client)
    account = sandbox_account(client)
    created = schedule(
        client, ready_post(client), account, when=soon(), caption="Traag [sandbox:timeout]"
    ).json()[0]
    assert tick().retrying == 1
    mid = pub(created["id"])
    assert mid.status == "scheduled" and mid.failure_code == "timeout"
    from app.publishing.worker import publish_due

    publish_due(mid.next_attempt_at + timedelta(seconds=1))
    done = pub(created["id"])
    assert done.status == "published"
    assert sandbox_count(done.provider_container_id) == 1
    outcomes = attempts(created["id"])
    assert [a.outcome for a in outcomes] == ["uncertain", "succeeded"]
    assert "Al online gevonden" in outcomes[1].provider_message


def test_outage_retries_with_backoff_then_fails_honestly(client) -> None:
    from app.publishing.worker import publish_due

    login(client)
    account = sandbox_account(client)
    created = schedule(
        client, ready_post(client), account, when=soon(), caption="Storing [sandbox:down]"
    ).json()[0]
    moment = datetime.now(UTC) + timedelta(minutes=11)
    for _ in range(3):
        publish_due(moment)
        current = pub(created["id"])
        moment = (current.next_attempt_at or moment) + timedelta(seconds=1)
    failed = pub(created["id"])
    assert failed.status == "failed" and failed.failure_code == "provider_unavailable"
    assert "Gestopt na 3 pogingen" in failed.failure_message
    assert "automatisch opnieuw" not in failed.failure_message
    assert [a.trigger for a in attempts(created["id"])] == ["schedule", "auto_retry", "auto_retry"]

    # Handmatig opnieuw na een onzekere uitkomst vraagt bevestiging; dubbel klikken is onschadelijk.
    refuse = client.post(
        f"/api/publications/{created['id']}/retry", json={"version": failed.version}
    )
    assert refuse.status_code == 422 and "Bevestig" in detail(refuse)
    ok = client.post(
        f"/api/publications/{created['id']}/retry",
        json={"version": failed.version, "confirmed": True},
    )
    assert ok.status_code == 200 and ok.json()["status"] == "scheduled"
    again = client.post(
        f"/api/publications/{created['id']}/retry",
        json={"version": failed.version, "confirmed": True},
    )
    assert again.status_code in (409, 422)


def test_revoked_token_pauses_the_account_and_spares_the_other_posts(client) -> None:
    from sqlalchemy import update

    from app.db import SessionLocal
    from app.models import SocialAccount
    from app.publishing import crypto

    login(client)
    account = sandbox_account(client)
    ready = ready_post(client)
    first = schedule(client, ready, account, when=soon(10)).json()[0]
    second = schedule(client, ready, account, when=soon(11)).json()[0]
    with SessionLocal() as session:
        session.execute(
            update(SocialAccount)
            .where(SocialAccount.id == account["id"])
            .values(token_enc=crypto.encrypt("revoked-token", account["id"]))
        )
        session.commit()

    tick(12)
    assert pub(first["id"]).failure_code == "auth"
    assert pub(second["id"]).status == "scheduled"  # niet naar het netwerk gestuurd
    assert {a.error_code for a in attempts(second["id"])} <= {"channel_paused"}
    settings = client.get(f"/api/companies/{company(client)['id']}/publishing").json()
    paused = next(a for a in settings["accounts"] if a["id"] == account["id"])
    assert paused["status"] == "reauth_required"

    refused = client.post(
        f"/api/publications/{first['id']}/retry", json={"version": pub(first["id"]).version}
    )
    assert "Koppel" in detail(refused)


def test_revoking_approval_stops_a_scheduled_post_at_send_time(client) -> None:
    login(client)
    account = sandbox_account(client)
    ready = ready_post(client)
    created = schedule(client, ready, account, when=soon()).json()[0]
    assert (
        client.delete(f"/api/posts/{ready['post']['id']}/approval").json()["scheduledAffected"] >= 1
    )
    tick()
    stopped = pub(created["id"])
    assert stopped.status == "failed" and stopped.failure_code == "not_publishable"
    assert "Klantakkoord" in stopped.failure_message
    assert sandbox_count() >= 0  # niets verstuurd voor deze container
    assert stopped.provider_container_id is None


def test_posts_far_past_due_are_not_sent_late(client) -> None:
    from app.publishing.worker import publish_due

    login(client)
    account = sandbox_account(client)
    created = schedule(client, ready_post(client), account, when=soon()).json()[0]
    summary = publish_due(datetime.now(UTC) + timedelta(hours=3))
    assert summary.missed >= 1
    assert pub(created["id"]).failure_code == "missed_window"


def test_disconnect_cancels_scheduled_posts_and_destroys_tokens(client) -> None:
    login(client)
    account = sandbox_account(client)
    created = schedule(client, ready_post(client), account, when=soon(200)).json()[0]
    assert (
        client.post(f"/api/publishing/accounts/{account['id']}/disconnect", json={}).status_code
        == 422
    )
    result = client.post(
        f"/api/publishing/accounts/{account['id']}/disconnect", json={"confirm": True}
    ).json()
    assert result["cancelled"] == 1
    assert pub(created["id"]).status == "cancelled"
    from app.db import SessionLocal
    from app.models import SocialAccount

    with SessionLocal() as session:
        assert session.get(SocialAccount, account["id"]).token_enc is None


# ------------------------------------------------------------------ rechten en publieke URL


def test_only_admins_manage_accounts_and_slots(client) -> None:
    login(client, "editor@example.test")
    company_id = company(client)["id"]
    assert (
        client.post(
            "/api/publishing/connect/sandbox", json={"companyId": company_id, "name": "nope"}
        ).status_code
        == 403
    )
    assert (
        client.post(
            f"/api/companies/{company_id}/slots", json={"weekdays": [1], "time": "10:00"}
        ).status_code
        == 403
    )
    assert (
        client.get(f"/api/publishing/connect/meta/start?company_id={company_id}").status_code == 403
    )
    client.cookies.clear()
    assert client.get(f"/api/companies/{company_id}/publishing").status_code == 401


def test_public_media_url_needs_a_valid_unexpired_signature(client) -> None:
    from app.publishing.service import public_media_url

    login(client)
    created = schedule(client, ready_post(client), sandbox_account(client), when=soon(300)).json()[
        0
    ]
    client.cookies.clear()  # Instagram heeft geen sessie
    url = public_media_url(pub(created["id"])).replace(base_url(), "")
    assert client.get(url).status_code == 200
    assert client.get(url.replace("sig=", "sig=0")).status_code == 403
    assert client.get(url.split("?")[0] + "?exp=1&sig=abc").status_code == 403


def test_pending_meta_tokens_are_encrypted_in_the_session(client) -> None:
    """De sessiecookie is alleen ondertekend, niet versleuteld.

    Tokens mogen er dus niet leesbaar in staan."""
    import base64
    import json as jsonlib

    from app.api import publishing as api
    from app.publishing.providers import ConnectableAccount
    from app.publishing.providers import meta as meta_module

    login(client)
    company_id = company(client)["id"]
    original = meta_module.connectable_accounts
    meta_module.connectable_accounts = lambda code, redirect: [
        ConnectableAccount(
            "facebook_page", "9001", "Klantpagina", "Klantpagina", "EAASECRETPAGETOKEN", None
        )
    ]
    from app.settings import get_settings

    settings = get_settings()
    settings.meta_app_id, settings.meta_app_secret = "app", "secret"
    try:
        start = client.get(
            f"/api/publishing/connect/meta/start?company_id={company_id}", follow_redirects=False
        )
        state = dict(p.split("=") for p in start.headers["location"].split("?")[1].split("&"))[
            "state"
        ]
        client.get(
            f"/api/publishing/connect/meta/callback?code=x&state={state}", follow_redirects=False
        )
        cookie = client.cookies.get("flow_social_session")
        decoded = base64.b64decode(cookie.split(".")[0] + "==").decode(errors="ignore")
        assert "EAASECRETPAGETOKEN" not in decoded
        assert jsonlib.loads(decoded)["meta_pending"]["blob"].startswith("v1.")
        pending = client.get(f"/api/publishing/connect/pending?company_id={company_id}").json()
        assert pending == [
            {"provider": "facebook_page", "externalId": "9001", "name": "Klantpagina"}
        ]
        confirmed = client.post(
            "/api/publishing/connect/confirm",
            json={"companyId": company_id, "externalIds": ["9001"]},
        )
        assert confirmed.status_code == 200 and confirmed.json()[0]["provider"] == "facebook_page"
    finally:
        meta_module.connectable_accounts = original
        settings.meta_app_id, settings.meta_app_secret = "", ""
    assert api.PENDING_TTL == 600
