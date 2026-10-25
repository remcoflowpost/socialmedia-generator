"""Meta-adapter tegen een gescripte Graph API (httpx.MockTransport). Geen netwerk."""

from datetime import UTC, datetime, timedelta

import httpx
import pytest

from app.publishing.providers import AccountCreds, ProviderError
from app.publishing.providers.meta import MetaClient, MetaProvider, connectable_accounts, error_from

IG = AccountCreds("instagram", "17841400000000001", "EAApagetoken")
FB = AccountCreds("facebook_page", "1100000000000001", "EAApagetoken")


class Graph:
    """Kleine scriptbare Graph API die alle verzoeken bijhoudt."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict]] = []
        self.container_status = ["IN_PROGRESS", "FINISHED"]
        self.fail_publish: Exception | dict | None = None
        self.media: list[dict] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        params = dict(request.url.params)
        if request.method == "POST":
            params |= dict(httpx.QueryParams(request.content.decode()))
        path = request.url.path.split("/", 2)[2]  # zonder /v26.0
        self.calls.append((request.method, path, params))
        if path.endswith("/media") and request.method == "POST":
            return httpx.Response(200, json={"id": "C1"})
        if path == "C1":
            status = (
                self.container_status.pop(0)
                if len(self.container_status) > 1
                else self.container_status[0]
            )
            return httpx.Response(200, json={"status_code": status, "id": "C1"})
        if path.endswith("/media_publish"):
            if isinstance(self.fail_publish, Exception):
                raise self.fail_publish
            if isinstance(self.fail_publish, dict):
                return httpx.Response(400, json={"error": self.fail_publish})
            return httpx.Response(200, json={"id": "M1"})
        if path == "M1":
            return httpx.Response(200, json={"permalink": "https://www.instagram.com/p/abc/"})
        if path.endswith("/media") and request.method == "GET":
            return httpx.Response(200, json={"data": self.media})
        if path.endswith("/photos"):
            return httpx.Response(200, json={"id": "P1", "post_id": "1100000000000001_99"})
        return httpx.Response(404, json={"error": {"message": "unknown", "code": 803}})


def provider(graph: Graph, kind: str = "instagram") -> MetaProvider:
    client = MetaClient(transport=httpx.MockTransport(graph.handler), sleep=lambda _s: None)
    return MetaProvider(kind, client)


def publish(
    p: MetaProvider,
    creds: AccountCreds,
    *,
    existing: str | None = None,
    fmt: str = "instagram/feed-portrait",
):
    saved: list[str] = []
    result = p.publish(
        creds,
        media_url="https://social.example.test/api/public/media/x?exp=1&sig=y",
        caption="Opgeleverd! #project",
        format_key=fmt,
        existing_container_id=existing,
        on_container=saved.append,
    )
    return result, saved


def test_instagram_creates_container_waits_and_publishes() -> None:
    graph = Graph()
    result, saved = publish(provider(graph), IG)
    assert saved == ["C1"]  # container-id vastgelegd voor het publiceren
    assert result.post_id == "M1" and result.url == "https://www.instagram.com/p/abc/"
    create = next(c for c in graph.calls if c[1].endswith("/media") and c[0] == "POST")
    assert create[2]["image_url"].startswith("https://social.example.test/")  # meegegeven URL
    assert create[2]["caption"] == "Opgeleverd! #project"
    assert create[2]["access_token"] == "EAApagetoken"


def test_instagram_story_has_no_caption_and_story_type() -> None:
    graph = Graph()
    publish(provider(graph), IG, fmt="instagram/story")
    create = next(c for c in graph.calls if c[1].endswith("/media") and c[0] == "POST")
    assert create[2]["media_type"] == "STORIES"
    assert "caption" not in create[2]


def test_instagram_reuses_a_finished_container_instead_of_creating_a_new_one() -> None:
    graph = Graph()
    graph.container_status = ["FINISHED"]
    result, saved = publish(provider(graph), IG, existing="C1")
    assert saved == []
    assert not any(c[1].endswith("/media") and c[0] == "POST" for c in graph.calls)
    assert result.post_id == "M1"


def test_instagram_already_published_container_is_found_not_resent() -> None:
    graph = Graph()
    graph.container_status = ["PUBLISHED"]
    graph.media = [
        {
            "id": "M9",
            "caption": "Opgeleverd!  #project",
            "timestamp": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S+0000"),
            "permalink": "https://www.instagram.com/p/m9/",
        }
    ]
    result, _ = publish(provider(graph), IG, existing="C1")
    assert result.post_id == "M9"
    assert not any(c[1].endswith("/media_publish") for c in graph.calls)


def test_timeout_on_publish_is_uncertain_but_container_was_saved() -> None:
    graph = Graph()
    graph.fail_publish = httpx.ReadTimeout("slow")
    p = provider(graph)
    saved: list[str] = []
    with pytest.raises(ProviderError) as info:
        p.publish(
            IG,
            media_url="u",
            caption="c",
            format_key="instagram/feed-square",
            existing_container_id=None,
            on_container=saved.append,
        )
    assert info.value.code == "timeout"
    assert saved == ["C1"]


def test_container_still_processing_becomes_media_not_ready() -> None:
    graph = Graph()
    graph.container_status = ["IN_PROGRESS"]
    with pytest.raises(ProviderError) as info:
        publish(provider(graph), IG)
    assert info.value.code == "media_not_ready"


@pytest.mark.parametrize(
    ("error", "status", "code"),
    [
        (
            {"code": 190, "message": "Error validating access token", "type": "OAuthException"},
            400,
            "auth",
        ),
        ({"code": 200, "message": "Permissions error"}, 403, "auth"),
        ({"code": 4, "message": "Application request limit reached"}, 400, "rate_limited"),
        ({"code": 100, "error_subcode": 2207009, "message": "aspect ratio"}, 400, "validation"),
        ({"code": 368, "message": "Temporarily blocked"}, 400, "blocked"),
        (
            {"code": 2, "message": "Service temporarily unavailable", "is_transient": True},
            500,
            "provider_unavailable",
        ),
        ({"code": 9007, "message": "Media not ready"}, 400, "media_not_ready"),
    ],
)
def test_graph_errors_are_normalized(error: dict, status: int, code: str) -> None:
    assert error_from(status, {"error": error}, {}).code == code


def test_provider_messages_never_contain_tokens() -> None:
    err = error_from(
        400, {"error": {"code": 100, "message": "bad access_token=EAAsecret123456789 here"}}, {}
    )
    assert "EAAsecret" not in (err.provider_message or "")


def test_facebook_publishes_photo_with_caption() -> None:
    graph = Graph()
    result, _ = publish(provider(graph, "facebook_page"), FB, fmt="facebook/feed-square")
    assert result.post_id == "1100000000000001_99"
    photos = next(c for c in graph.calls if c[1].endswith("/photos"))
    assert photos[2]["caption"] == "Opgeleverd! #project"


def test_connection_refused_is_network_not_uncertain() -> None:
    def refuse(_request):
        raise httpx.ConnectError("refused")

    p = MetaProvider("facebook_page", MetaClient(transport=httpx.MockTransport(refuse)))
    with pytest.raises(ProviderError) as info:
        publish(p, FB, fmt="facebook/feed-square")
    assert info.value.code == "network"


def test_oauth_lists_pages_and_linked_instagram_accounts_the_user_may_post_to() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/oauth/access_token"):
            token = "LONG" if "fb_exchange_token" in request.url.params else "SHORT"
            assert "access_token" not in request.url.params
            return httpx.Response(200, json={"access_token": token})
        if path.endswith("/me/accounts"):
            assert request.url.params["access_token"] == "LONG"
            return httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "id": "1",
                            "name": "Klant A",
                            "access_token": "PAGE1",
                            "tasks": ["CREATE_CONTENT"],
                            "instagram_business_account": {"id": "17", "username": "klanta"},
                        },
                        {
                            "id": "2",
                            "name": "Alleen lezen",
                            "access_token": "PAGE2",
                            "tasks": ["ANALYZE"],
                        },
                    ]
                },
            )
        return httpx.Response(404)

    found = connectable_accounts(
        "code", "https://x/cb", MetaClient(transport=httpx.MockTransport(handler))
    )
    assert [(a.provider, a.external_id, a.name) for a in found] == [
        ("facebook_page", "1", "Klant A"),
        ("instagram", "17", "@klanta"),
    ]
    assert all(a.token == "PAGE1" for a in found)


def test_facebook_reconcile_matches_caption_since_first_attempt() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/published_posts")
        return httpx.Response(
            200,
            json={
                "data": [
                    {"id": "X_1", "message": "Anders"},
                    {
                        "id": "X_2",
                        "message": "Opgeleverd!\n#project",
                        "permalink_url": "https://fb/2",
                    },
                ]
            },
        )

    p = MetaProvider("facebook_page", MetaClient(transport=httpx.MockTransport(handler)))
    found = p.reconcile(
        FB,
        caption="Opgeleverd! #project",
        since=datetime.now(UTC) - timedelta(minutes=5),
        container_id=None,
    )
    assert found and found.post_id == "X_2"
