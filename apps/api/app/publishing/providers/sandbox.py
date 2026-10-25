"""Sandbox-netwerk voor ontwikkeling en tests. Gedraagt zich zoals Instagram waar het
ertoe doet: een container-id voor het publiceren en een unieke constraint die dubbel
publiceren onmogelijk maakt.

Foutinjectie via het bijschrift:
  [sandbox:down]       503, elke keer
  [sandbox:reject]     inhoud geweigerd
  [sandbox:ratelimit]  rate limit, Retry-After 120 s
  [sandbox:timeout]    de post wordt WEL opgeslagen, maar het antwoord gaat verloren
  [sandbox:auth]       token ingetrokken
"""

import uuid
from collections.abc import Callable
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.db import SessionLocal
from app.models import SandboxPost
from app.publishing.providers.base import AccountCreds, ProviderError, Published
from app.settings import get_settings


class SandboxProvider:
    id = "sandbox"

    def verify(self, account: AccountCreds) -> None:
        if account.token.startswith("revoked"):
            raise ProviderError("auth", "Sandbox-token ingetrokken.", http_status=401)

    def publish(
        self,
        account: AccountCreds,
        *,
        media_url: str,
        caption: str,
        format_key: str,
        existing_container_id: str | None,
        on_container: Callable[[str], None],
    ) -> Published:
        self.verify(account)
        if "[sandbox:auth]" in caption:
            raise ProviderError("auth", "Sandbox-token ingetrokken.", http_status=401)
        if "[sandbox:reject]" in caption:
            raise ProviderError(
                "validation",
                "Inhoud geweigerd.",
                http_status=400,
                provider_message="Blocked phrase",
            )
        if "[sandbox:down]" in caption:
            raise ProviderError(
                "provider_unavailable", "Storing.", http_status=503, provider_message="Unavailable"
            )
        if "[sandbox:ratelimit]" in caption:
            raise ProviderError("rate_limited", "Rate limit.", http_status=429, retry_after=120)
        container = existing_container_id or f"sbx-{uuid.uuid4()}"
        on_container(container)
        with SessionLocal() as session:
            session.execute(
                insert(SandboxPost)
                .values(
                    id=str(uuid.uuid4()),
                    account_id=account.external_id,
                    container_id=container,
                    caption=caption,
                    media_key=media_url[:500],
                )
                .on_conflict_do_nothing(constraint="sandbox_post_container")
            )
            session.commit()
            row = session.scalar(select(SandboxPost).where(SandboxPost.container_id == container))
        if "[sandbox:timeout]" in caption:
            raise ProviderError("timeout", "Geen antwoord.")
        return self._published(row)

    def reconcile(
        self, account: AccountCreds, *, caption: str, since: datetime, container_id: str | None
    ) -> Published | None:
        with SessionLocal() as session:
            stmt = select(SandboxPost).where(SandboxPost.account_id == account.external_id)
            if container_id:
                stmt = stmt.where(SandboxPost.container_id == container_id)
            else:
                stmt = stmt.where(
                    SandboxPost.caption == caption,
                    SandboxPost.created_at >= since - timedelta(minutes=1),
                )
            row = session.scalar(stmt.limit(1))
        return self._published(row) if row else None

    @staticmethod
    def _published(row: SandboxPost) -> Published:
        url = f"{get_settings().public_url.rstrip('/')}/api/sandbox/posts/{row.id}"
        return Published(post_id=row.id, url=url, container_id=row.container_id)
