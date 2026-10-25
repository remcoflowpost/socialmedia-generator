"""Smalle interface voor sociale netwerken. Buiten deze map weet niemand iets van HTTP,
OAuth-parameters of JSON van een netwerk."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


class ProviderError(Exception):
    """Genormaliseerde fout. `code` is een FailureCode uit app.publishing.retry."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        http_status: int | None = None,
        retry_after: float | None = None,
        provider_message: str | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status
        self.retry_after = retry_after
        self.provider_message = provider_message


@dataclass(frozen=True)
class AccountCreds:
    provider: str
    external_id: str
    token: str


@dataclass(frozen=True)
class Published:
    post_id: str
    url: str | None
    container_id: str | None = None
    note: str | None = None


@dataclass(frozen=True)
class ConnectableAccount:
    """Een account dat na OAuth gekoppeld kan worden (pagina of Instagram-account)."""

    provider: str
    external_id: str
    name: str
    handle: str
    token: str
    token_expires_at: datetime | None


class Provider(Protocol):
    id: str

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
        """Publiceert. Roept `on_container` aan zodra een netwerk-id bestaat dat bij een
        onzekere uitkomst gebruikt kan worden om de status na te vragen."""
        ...

    def reconcile(
        self,
        account: AccountCreds,
        *,
        caption: str,
        since: datetime,
        container_id: str | None,
    ) -> Published | None:
        """Zoekt een post die mogelijk al gepubliceerd is. None = niet gevonden."""
        ...

    def verify(self, account: AccountCreds) -> None:
        """Werpt ProviderError('auth') als de toegang niet meer werkt."""
        ...
