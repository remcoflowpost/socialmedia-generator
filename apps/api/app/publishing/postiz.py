"""Postiz-adapter (https://github.com/gitroomhq/postiz-app), self-hosted.

Postiz beheert de OAuth-koppelingen met de platformen, tokens en de planning. Deze adapter
gebruikt alleen de public API (`/public/v1`):

- `GET  /integrations`   gekoppelde kanalen
- `POST /upload`         bestand uploaden (multipart, veld `file`), geeft `{id, path}`
- `POST /posts`          post maken voor een of meer kanalen (type now, schedule of draft)

Authenticatie: de API-sleutel uit Postiz (Settings > Public API) in de header
`Authorization`, zonder "Bearer". Postiz is AGPL-3.0; we draaien het ongewijzigd als aparte
dienst en praten er alleen via HTTP mee.
"""

import uuid
from datetime import UTC

import httpx

from app.publishing.base import (
    Channel,
    ChannelPost,
    MediaFile,
    PublishError,
    PublishRequest,
    PublishResult,
)

TIMEOUT = httpx.Timeout(120.0, connect=10.0)


def default_settings(platform: str, item: ChannelPost) -> dict:
    """Minimale instellingen per platform die Postiz verplicht stelt bij now/schedule.
    Platformen met verplichte keuzes zonder zinnige standaard (YouTube-titel,
    Pinterest-bord) geven een foutmelding van Postiz terug."""
    settings: dict = {"__type": platform}
    if platform in ("instagram", "instagram-standalone"):
        story = any((m.format_key or "").endswith("/story") for m in item.media)
        settings |= {"post_type": "story" if story else "post", "collaborators": []}
    elif platform == "x":
        settings |= {"who_can_reply_post": "everyone"}
    elif platform in ("tiktok", "tiktok-business"):
        settings |= {
            "title": "",
            "privacy_level": "PUBLIC_TO_EVERYONE",
            "duet": False,
            "stitch": False,
            "comment": True,
            "autoAddMusic": "no",
            "brand_content_toggle": False,
            "video_made_with_ai": False,
            "brand_organic_toggle": False,
            "content_posting_method": "DIRECT_POST",
        }
    return settings


def _error_message(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        return f"Postiz gaf HTTP {response.status_code}."
    if isinstance(body, dict):
        detail = body.get("msg") or body.get("message") or body.get("error")
        if isinstance(detail, list):
            detail = "; ".join(map(str, detail))
        if body.get("provider"):
            detail = f"{body.get('name') or body['provider']}: {detail}"
        if detail:
            return f"Postiz: {detail}"
    return f"Postiz gaf HTTP {response.status_code}."


class PostizProvider:
    name = "postiz"

    def __init__(self, base_url: str, api_key: str, transport: httpx.BaseTransport | None = None):
        if not base_url or not api_key:
            raise PublishError("POSTIZ_URL en POSTIZ_API_KEY moeten ingevuld zijn.")
        # base_url is de backend-URL van Postiz, bijv. https://postiz.flow.local/api
        self._client = httpx.Client(
            base_url=f"{base_url.rstrip('/')}/public/v1",
            headers={"Authorization": api_key},
            timeout=TIMEOUT,
            transport=transport,
        )

    def _check(self, response: httpx.Response) -> httpx.Response:
        if response.status_code >= 400:
            raise PublishError(_error_message(response))
        return response

    def list_channels(self) -> list[Channel]:
        rows = self._check(self._client.get("/integrations")).json()
        return [
            Channel(
                id=row["id"],
                name=row.get("name") or row["identifier"],
                platform=row["identifier"],
                picture=row.get("picture"),
                disabled=bool(row.get("disabled")),
                group=(row.get("customer") or {}).get("name"),
            )
            for row in rows
        ]

    def _upload(self, media: MediaFile) -> dict:
        if media.path is None:
            raise PublishError(f"{media.filename} staat niet in de opslag.")
        with media.path.open("rb") as handle:
            response = self._client.post("/upload", files={"file": (media.filename, handle)})
        body = self._check(response).json()
        if not body.get("id") or not body.get("path"):
            raise PublishError("Postiz gaf geen id of pad terug voor de upload.")
        return {"id": body["id"], "path": body["path"]}

    def build_body(self, request: PublishRequest, uploaded: dict[str, dict], group: str) -> dict:
        return {
            "type": request.mode,
            "date": request.date.astimezone(UTC).isoformat().replace("+00:00", "Z"),
            "shortLink": False,
            "tags": [],
            "posts": [
                {
                    "integration": {"id": item.channel.id},
                    "group": group,
                    "value": [
                        {
                            "content": request.caption,
                            "image": [uploaded[m.key] for m in item.media],
                        }
                    ],
                    "settings": default_settings(item.channel.platform, item),
                }
                for item in request.posts
            ],
        }

    def publish(self, request: PublishRequest) -> PublishResult:
        uploaded: dict[str, dict] = {}
        for item in request.posts:
            for media in item.media:
                if media.key not in uploaded:
                    uploaded[media.key] = self._upload(media)
        group = uuid.uuid4().hex
        response = self._check(
            self._client.post("/posts", json=self.build_body(request, uploaded, group))
        )
        created = response.json()
        posts = created if isinstance(created, list) else [created]
        return PublishResult(provider=self.name, group=group, posts=posts)
