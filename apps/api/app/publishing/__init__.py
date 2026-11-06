"""Publicatie naar social media via een provider (mock of Postiz)."""

from app.publishing.base import (
    Channel,
    ChannelPost,
    MediaFile,
    PublishError,
    PublishProvider,
    PublishRequest,
    PublishResult,
)
from app.settings import get_settings


def get_provider() -> PublishProvider:
    settings = get_settings()
    if settings.publish_provider == "postiz":
        from app.publishing.postiz import PostizProvider

        return PostizProvider(settings.postiz_url, settings.postiz_api_key)
    from app.publishing.mock import MockProvider

    return MockProvider()


__all__ = [
    "Channel",
    "ChannelPost",
    "MediaFile",
    "PublishError",
    "PublishProvider",
    "PublishRequest",
    "PublishResult",
    "get_provider",
]
