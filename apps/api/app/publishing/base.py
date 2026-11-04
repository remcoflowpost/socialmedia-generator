"""Contract voor publicatieproviders. De rest van de app kent alleen dit contract."""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal, Protocol

PublishMode = Literal["now", "schedule", "draft"]


class PublishError(RuntimeError):
    """Fout van de provider die de gebruiker te zien krijgt."""


@dataclass(frozen=True)
class Channel:
    """Een gekoppeld social-account (bij Postiz: een integration)."""

    id: str
    name: str
    platform: str  # provider-identifier, bijv. instagram, linkedin-page, facebook
    picture: str | None = None
    disabled: bool = False
    group: str | None = None  # bij Postiz: de naam van de customer


@dataclass(frozen=True)
class MediaFile:
    key: str  # storage-key, uniek per bestand
    filename: str
    path: Path | None = None  # pas ingevuld in de worker
    # Formaat waaruit het bestand komt (export), bijv. "instagram/story". Leeg bij uploads.
    format_key: str | None = None


@dataclass
class ChannelPost:
    channel: Channel
    media: list[MediaFile] = field(default_factory=list)


@dataclass
class PublishRequest:
    caption: str
    mode: PublishMode
    date: datetime  # moment van publicatie; bij "now" het huidige moment
    posts: list[ChannelPost]


@dataclass
class PublishResult:
    provider: str
    group: str | None
    posts: list[dict]


class PublishProvider(Protocol):
    name: str

    def list_channels(self) -> list[Channel]: ...

    def publish(self, request: PublishRequest) -> PublishResult: ...
