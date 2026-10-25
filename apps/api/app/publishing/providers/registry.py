from app.publishing.providers.base import Provider
from app.settings import get_settings

_overrides: dict[str, Provider] = {}


def override_provider(provider_id: str, provider: Provider | None) -> None:
    """Voor tests: vervang een provider door een gescripte variant."""
    if provider is None:
        _overrides.pop(provider_id, None)
        return
    _overrides[provider_id] = provider


def get_provider(provider_id: str) -> Provider:
    if provider_id in _overrides:
        return _overrides[provider_id]
    if provider_id in ("instagram", "facebook_page"):
        from app.publishing.providers.meta import MetaProvider

        return MetaProvider(provider_id)
    if provider_id == "sandbox":
        if not get_settings().allow_sandbox_provider:
            raise ValueError("Het Sandbox-netwerk staat uit (ALLOW_SANDBOX_PROVIDER).")
        from app.publishing.providers.sandbox import SandboxProvider

        return SandboxProvider()
    raise ValueError(f"Onbekende provider {provider_id}")
