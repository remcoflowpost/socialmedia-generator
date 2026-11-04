"""Publicatieproviders zonder netwerk: Postiz via een nep-transport, nooit een echte server."""

import json
from datetime import UTC, datetime
from types import SimpleNamespace

import httpx
import pytest

from app.domain.publish import channels_for_company, run_publication
from app.publishing import Channel, ChannelPost, MediaFile, PublishError, PublishRequest
from app.publishing.mock import MockProvider
from app.publishing.postiz import PostizProvider, default_settings

INTEGRATIONS = [
    {
        "id": "ig1",
        "name": "Flow IG",
        "identifier": "instagram",
        "picture": None,
        "disabled": False,
        "customer": {"id": "c1", "name": "Flow Postproduction"},
    },
    {"id": "li1", "name": "Flow LinkedIn", "identifier": "linkedin-page", "disabled": False},
]


def fake_postiz(calls: list):
    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        assert request.headers["Authorization"] == "sleutel"
        if request.url.path.endswith("/integrations"):
            return httpx.Response(200, json=INTEGRATIONS)
        if request.url.path.endswith("/upload"):
            n = sum(1 for c in calls if c.url.path.endswith("/upload"))
            return httpx.Response(200, json={"id": f"m{n}", "path": f"https://pz/u/m{n}.jpg"})
        if request.url.path.endswith("/posts"):
            body = json.loads(request.content)
            if body["posts"][0]["value"][0]["content"] == "te lang":
                return httpx.Response(
                    400, json={"provider": "x", "name": "Flow X", "msg": "post is too long"}
                )
            return httpx.Response(
                201, json=[{"postId": f"p-{p['integration']['id']}"} for p in body["posts"]]
            )
        return httpx.Response(404)

    return httpx.MockTransport(handler)


def provider(calls):
    return PostizProvider("https://postiz.test/api/", "sleutel", transport=fake_postiz(calls))


def test_postiz_lists_channels_with_customer_as_group():
    channels = provider([]).list_channels()
    assert [(c.id, c.platform, c.group) for c in channels] == [
        ("ig1", "instagram", "Flow Postproduction"),
        ("li1", "linkedin-page", None),
    ]


def test_postiz_uploads_each_file_once_and_posts_per_channel(tmp_path):
    image = tmp_path / "a.jpg"
    image.write_bytes(b"jpeg")
    story = tmp_path / "s.jpg"
    story.write_bytes(b"jpeg")
    shared = MediaFile(key="k/a.jpg", filename="a.jpg", path=image, format_key="linkedin/feed")
    calls: list[httpx.Request] = []
    result = provider(calls).publish(
        PublishRequest(
            caption="Hallo",
            mode="schedule",
            date=datetime(2026, 12, 1, 9, tzinfo=UTC),
            posts=[
                ChannelPost(
                    Channel("ig1", "IG", "instagram"),
                    [MediaFile("k/s.jpg", "s.jpg", story, "instagram/story")],
                ),
                ChannelPost(Channel("li1", "LI", "linkedin-page"), [shared]),
                ChannelPost(Channel("li2", "LI 2", "linkedin"), [shared]),
            ],
        )
    )
    uploads = [c for c in calls if c.url.path == "/api/public/v1/upload"]
    assert len(uploads) == 2  # gedeeld bestand maar een keer geupload
    body = json.loads(calls[-1].content)
    assert body["type"] == "schedule"
    assert body["date"] == "2026-12-01T09:00:00Z"
    assert body["posts"][0]["settings"] == {
        "__type": "instagram",
        "post_type": "story",
        "collaborators": [],
    }
    assert body["posts"][1]["value"][0]["image"] == body["posts"][2]["value"][0]["image"]
    assert {p["group"] for p in body["posts"]} == {result.group}
    assert [p["postId"] for p in result.posts] == ["p-ig1", "p-li1", "p-li2"]


def test_postiz_error_is_readable():
    with pytest.raises(PublishError, match="Flow X: post is too long"):
        provider([]).publish(
            PublishRequest(
                caption="te lang",
                mode="now",
                date=datetime.now(UTC),
                posts=[ChannelPost(Channel("x1", "Flow X", "x"))],
            )
        )


def test_postiz_requires_configuration():
    with pytest.raises(PublishError):
        PostizProvider("", "")


def test_instagram_feed_is_post_and_x_gets_reply_setting():
    feed = ChannelPost(Channel("a", "a", "instagram"), [MediaFile("k", "f", None, "x/feed")])
    assert default_settings("instagram", feed)["post_type"] == "post"
    assert default_settings("x", feed)["who_can_reply_post"] == "everyone"
    assert default_settings("bluesky", feed) == {"__type": "bluesky"}


def test_channels_matched_on_company_name_or_slug():
    channels = [
        Channel("1", "a", "instagram", group="Flow Postproduction"),
        Channel("2", "b", "instagram", group="andere klant"),
    ]
    company = SimpleNamespace(name="Flow Postproduction", slug="flow")
    assert channels_for_company(channels, company) == ([channels[0]], True)
    other = SimpleNamespace(name="Onbekend", slug="onbekend")
    assert channels_for_company(channels, other) == (channels, False)


def test_mock_publication_round_trip(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "app.domain.publish.get_storage",
        lambda: SimpleNamespace(local_path=lambda key: tmp_path / key),
    )
    payload = {
        "caption": "Test",
        "mode": "draft",
        "date": "2026-11-04T10:00:00+00:00",
        "items": [
            {
                "channel": {"id": "mock-instagram", "name": "IG", "platform": "instagram"},
                "media": [{"key": "a.jpg", "filename": "a.jpg", "formatKey": None}],
            }
        ],
    }
    result = run_publication(payload, MockProvider())
    assert result["provider"] == "mock"
    assert result["posts"][0]["files"] == ["a.jpg"]
