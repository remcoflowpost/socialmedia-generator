"""Mock-provider: standaard, voor ontwikkeling en tests. Post nooit echt iets."""

import logging
import uuid

from app.publishing.base import Channel, PublishRequest, PublishResult

log = logging.getLogger("publish.mock")

MOCK_CHANNELS = [
    Channel(id="mock-instagram", name="Instagram (test)", platform="instagram"),
    Channel(id="mock-facebook", name="Facebook-pagina (test)", platform="facebook"),
    Channel(id="mock-linkedin", name="LinkedIn-pagina (test)", platform="linkedin-page"),
]


class MockProvider:
    name = "mock"

    def list_channels(self) -> list[Channel]:
        return list(MOCK_CHANNELS)

    def publish(self, request: PublishRequest) -> PublishResult:
        group = f"mock-{uuid.uuid4().hex[:12]}"
        posts = []
        for item in request.posts:
            log.info(
                "mock-publicatie %s naar %s met %d bestand(en)",
                request.mode,
                item.channel.name,
                len(item.media),
            )
            posts.append(
                {
                    "channelId": item.channel.id,
                    "channel": item.channel.name,
                    "postId": f"mock-{uuid.uuid4().hex[:12]}",
                    "files": [m.filename for m in item.media],
                }
            )
        return PublishResult(provider=self.name, group=group, posts=posts)
