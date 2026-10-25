"""Meta Graph API: Facebook-pagina's en Instagram (Business/Creator via Facebook Login for
Business). Zie docs/publiceren.md voor de regels en het exactly-once-ontwerp.

Instagram publiceert in twee stappen: een container maken en die publiceren. Het
container-id wordt via `on_container` opgeslagen voordat er gepubliceerd wordt, zodat een
onzekere uitkomst later via de containerstatus is na te gaan. Facebook kent zoiets niet;
daar zoeken we na een onzekere uitkomst in de recente posts van de pagina.
"""

import re
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

import httpx

from app.publishing.providers.base import AccountCreds, ConnectableAccount, ProviderError, Published
from app.settings import get_settings

SCOPES = (
    "pages_show_list",
    "pages_read_engagement",
    "pages_manage_posts",
    "instagram_basic",
    "instagram_content_publish",
    "business_management",
)
CONTAINER_POLLS = 6
CONTAINER_POLL_SECONDS = 2.0

# Graph-foutcodes, zie de tabel in docs/publiceren.md.
_AUTH_CODES = {102, 190, 10, 463, 467}
_RATE_CODES = {4, 17, 32, 613} | set(range(80001, 80010))
_NOT_READY_CODES = {9007, 2207027}
_INVALID_CODES = {100, 2207009, 2207004, 2207003, 2207005, 2207026, 36003}
_BLOCKED_CODES = {368, 2207050}
_TOKEN_RE = re.compile(r"(access_token=)[^&\s]+|(EAA[A-Za-z0-9]{10,})")


def _redact(text: str) -> str:
    return _TOKEN_RE.sub(lambda m: (m.group(1) or "") + "[redacted]", text or "")[:300]


def _graph_base() -> str:
    return f"https://graph.facebook.com/{get_settings().meta_graph_version}"


class MetaClient:
    """Dunne HTTP-laag. `transport` is injecteerbaar voor tests (httpx.MockTransport)."""

    def __init__(
        self, transport: httpx.BaseTransport | None = None, sleep: Callable = time.sleep
    ) -> None:
        settings = get_settings()
        self._client = httpx.Client(
            base_url=_graph_base(),
            timeout=httpx.Timeout(settings.provider_timeout_seconds, connect=5.0),
            transport=transport,
            follow_redirects=False,
        )
        self.sleep = sleep

    def call(self, method: str, path: str, token: str, **params: object) -> dict:
        data = {k: v for k, v in params.items() if v is not None}
        if token:  # OAuth-uitwisselingen hebben (nog) geen token
            data["access_token"] = token
        try:
            if method == "GET":
                response = self._client.get(path, params=data)
            else:
                response = self._client.post(path, data=data)
        except httpx.ConnectError as error:
            raise ProviderError("network", "Meta was niet bereikbaar.") from error
        except httpx.TimeoutException as error:
            # Bij POST weten we niet of Meta het verzoek heeft verwerkt.
            raise ProviderError("timeout", "Meta antwoordde niet op tijd.") from error
        except httpx.HTTPError as error:
            raise ProviderError("timeout", "Verbinding met Meta verbroken.") from error
        try:
            body = response.json()
        except ValueError:
            body = {}
        if response.status_code < 400 and "error" not in body:
            return body
        raise error_from(response.status_code, body, response.headers)


def error_from(status: int, body: dict, headers: httpx.Headers | dict) -> ProviderError:
    err = body.get("error") or {}
    code = int(err.get("code") or 0)
    sub = int(err.get("error_subcode") or 0)
    message = _redact(str(err.get("error_user_msg") or err.get("message") or f"HTTP {status}"))
    opts = {"http_status": status, "provider_message": message}
    # 190 = token ongeldig/verlopen, 10 en 200-299 = rechten ontbreken of ingetrokken.
    if code in _AUTH_CODES or 200 <= code <= 299:
        return ProviderError("auth", "Meta weigerde de toegang.", **opts)
    if code in _RATE_CODES or status == 429:
        retry = headers.get("retry-after") if hasattr(headers, "get") else None
        return ProviderError(
            "rate_limited",
            "Rate limit van Meta.",
            retry_after=float(retry) if retry and str(retry).isdigit() else 15 * 60,
            **opts,
        )
    if code in _NOT_READY_CODES or sub in _NOT_READY_CODES:
        return ProviderError("media_not_ready", "Meta verwerkt het beeld nog.", **opts)
    if code in _BLOCKED_CODES or sub in _BLOCKED_CODES:
        return ProviderError("blocked", "Meta blokkeerde de publicatie.", **opts)
    if code in _INVALID_CODES or sub in _INVALID_CODES:
        return ProviderError("validation", "Meta weigerde de inhoud.", **opts)
    if err.get("is_transient") or status >= 500:
        return ProviderError("provider_unavailable", "Tijdelijke storing bij Meta.", **opts)
    return ProviderError("unknown", "Onverwacht antwoord van Meta.", **opts)


class MetaProvider:
    def __init__(self, provider_id: str, client: MetaClient | None = None) -> None:
        self.id = provider_id
        self.client = client or MetaClient()

    def verify(self, account: AccountCreds) -> None:
        self.client.call("GET", f"/{account.external_id}", account.token, fields="id")

    # ------------------------------------------------------------------ publiceren

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
        if self.id == "facebook_page":
            return self._publish_facebook(account, media_url, caption)
        return self._publish_instagram(
            account, media_url, caption, format_key, existing_container_id, on_container
        )

    def _publish_facebook(self, account: AccountCreds, media_url: str, caption: str) -> Published:
        body = self.client.call(
            "POST", f"/{account.external_id}/photos", account.token, url=media_url, caption=caption
        )
        post_id = str(body.get("post_id") or body.get("id"))
        return Published(post_id=post_id, url=f"https://www.facebook.com/{post_id}")

    def _publish_instagram(
        self,
        account: AccountCreds,
        media_url: str,
        caption: str,
        format_key: str,
        container_id: str | None,
        on_container: Callable[[str], None],
    ) -> Published:
        ig = account.external_id
        status = self._container_status(account, container_id) if container_id else None
        if status == "PUBLISHED":
            found = self.reconcile(
                account,
                caption=caption,
                since=datetime.now(UTC) - timedelta(days=2),
                container_id=container_id,
            )
            if found:
                return found
            raise ProviderError(
                "uncertain", "Container is gepubliceerd maar de post is niet gevonden."
            )
        if status not in ("FINISHED", "IN_PROGRESS"):
            story = format_key == "instagram/story"
            created = self.client.call(
                "POST",
                f"/{ig}/media",
                account.token,
                image_url=media_url,
                caption=None if story else caption,
                media_type="STORIES" if story else None,
            )
            container_id = str(created["id"])
            on_container(container_id)
            status = "IN_PROGRESS"
        for _ in range(CONTAINER_POLLS):
            if status == "FINISHED":
                break
            if status == "ERROR":
                raise ProviderError("validation", "Instagram kon het beeld niet verwerken.")
            self.client.sleep(CONTAINER_POLL_SECONDS)
            status = self._container_status(account, container_id)
        if status != "FINISHED":
            raise ProviderError("media_not_ready", "Instagram verwerkt het beeld nog.")
        published = self.client.call(
            "POST", f"/{ig}/media_publish", account.token, creation_id=container_id
        )
        media_id = str(published["id"])
        return Published(
            post_id=media_id, url=self._permalink(account, media_id), container_id=container_id
        )

    def _container_status(self, account: AccountCreds, container_id: str | None) -> str | None:
        if not container_id:
            return None
        body = self.client.call("GET", f"/{container_id}", account.token, fields="status_code")
        return str(body.get("status_code") or "") or None

    def _permalink(self, account: AccountCreds, media_id: str) -> str | None:
        try:
            body = self.client.call("GET", f"/{media_id}", account.token, fields="permalink")
        except ProviderError:
            return None  # gepubliceerd is gepubliceerd; de link is bijzaak
        return body.get("permalink")

    # ------------------------------------------------------------------ reconciliatie

    def reconcile(
        self, account: AccountCreds, *, caption: str, since: datetime, container_id: str | None
    ) -> Published | None:
        if self.id == "instagram":
            if container_id and self._container_status(account, container_id) != "PUBLISHED":
                return None
            body = self.client.call(
                "GET",
                f"/{account.external_id}/media",
                account.token,
                fields="id,caption,timestamp,permalink",
                limit=25,
            )
            for item in body.get("data", []):
                if _same(item.get("caption"), caption) and _after(item.get("timestamp"), since):
                    return Published(str(item["id"]), item.get("permalink"), container_id)
            return None
        body = self.client.call(
            "GET",
            f"/{account.external_id}/published_posts",
            account.token,
            fields="id,message,created_time,permalink_url",
            since=int((since - timedelta(minutes=2)).timestamp()),
            limit=25,
        )
        for item in body.get("data", []):
            if _same(item.get("message"), caption):
                return Published(str(item["id"]), item.get("permalink_url"))
        return None


def _same(a: str | None, b: str) -> bool:
    norm = lambda s: " ".join((s or "").split())  # noqa: E731
    return norm(a) == norm(b)


def _after(stamp: str | None, since: datetime) -> bool:
    if not stamp:
        return False
    try:
        moment = datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%S%z")
    except ValueError:
        return False
    return moment >= since - timedelta(minutes=2)


# ---------------------------------------------------------------------- koppelen (OAuth)


def authorize_url(state: str, redirect_uri: str) -> str:
    settings = get_settings()
    query = urlencode(
        {
            "client_id": settings.meta_app_id,
            "redirect_uri": redirect_uri,
            "state": state,
            "response_type": "code",
            "scope": ",".join(SCOPES),
        }
    )
    return f"https://www.facebook.com/{settings.meta_graph_version}/dialog/oauth?{query}"


def connectable_accounts(
    code: str, redirect_uri: str, client: MetaClient | None = None
) -> list[ConnectableAccount]:
    """Wisselt de code in voor een langlevende gebruikerstoken en geeft de pagina's (en
    gekoppelde Instagram-accounts) terug waar de gebruiker berichten op mag plaatsen.
    Paginatokens die van een langlevende gebruikerstoken komen, verlopen niet."""
    settings = get_settings()
    client = client or MetaClient()
    short = client.call(
        "GET",
        "/oauth/access_token",
        "",
        client_id=settings.meta_app_id,
        client_secret=settings.meta_app_secret,
        redirect_uri=redirect_uri,
        code=code,
    )
    long = client.call(
        "GET",
        "/oauth/access_token",
        "",
        grant_type="fb_exchange_token",
        client_id=settings.meta_app_id,
        client_secret=settings.meta_app_secret,
        fb_exchange_token=short["access_token"],
    )
    pages = client.call(
        "GET",
        "/me/accounts",
        long["access_token"],
        fields="id,name,access_token,tasks,instagram_business_account{id,username}",
        limit=100,
    )
    found: list[ConnectableAccount] = []
    for page in pages.get("data", []):
        tasks = set(page.get("tasks") or [])
        if tasks and not tasks & {"CREATE_CONTENT", "MANAGE"}:
            continue  # gebruiker mag op deze pagina niet publiceren
        found.append(
            ConnectableAccount(
                "facebook_page",
                str(page["id"]),
                page["name"],
                page["name"],
                page["access_token"],
                None,
            )
        )
        ig = page.get("instagram_business_account")
        if ig:
            found.append(
                ConnectableAccount(
                    "instagram",
                    str(ig["id"]),
                    f"@{ig.get('username', ig['id'])}",
                    ig.get("username", ""),
                    page["access_token"],
                    None,
                )
            )
    return found
