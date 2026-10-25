"""Classificatie van publicatiefouten en het retrybeleid."""

import random
from dataclasses import dataclass
from typing import Literal

FailureCode = Literal[
    "auth",  # token ongeldig of rechten ingetrokken: account gepauzeerd
    "rate_limited",
    "timeout",  # verzonden, geen antwoord: uitkomst onbekend
    "network",  # niet verbonden: zeker niet aangekomen
    "provider_unavailable",  # 5xx of tijdelijke fout
    "media_not_ready",
    "validation",  # inhoud geweigerd
    "blocked",  # door het platform geblokkeerd (spam, beleid)
    "missed_window",
    "channel_paused",
    "not_publishable",  # regel geschonden vlak voor verzenden
    "uncertain",
    "unknown",
]


@dataclass(frozen=True)
class Classification:
    retryable: bool
    uncertain: bool


_TABLE: dict[str, Classification] = {
    "auth": Classification(False, False),
    "rate_limited": Classification(True, False),
    "timeout": Classification(True, True),
    "network": Classification(True, False),
    "provider_unavailable": Classification(True, True),
    "media_not_ready": Classification(True, False),
    "validation": Classification(False, False),
    "blocked": Classification(False, False),
    "missed_window": Classification(False, False),
    "channel_paused": Classification(False, False),
    "not_publishable": Classification(False, False),
    "uncertain": Classification(False, True),
    "unknown": Classification(True, True),
}


def classify(code: str) -> Classification:
    return _TABLE.get(code, _TABLE["unknown"])


MAX_AUTO_ATTEMPTS = 3
MISSED_WINDOW_SECONDS = 60 * 60
LEASE_SECONDS = 3 * 60
_BACKOFF = (60, 5 * 60, 15 * 60)


def backoff_seconds(
    next_attempt_no: int, retry_after: float | None = None, jitter: float | None = None
) -> float:
    """Wachttijd voor poging `next_attempt_no` (2, 3, ...).

    Een Retry-After van het netwerk gaat voor als die langer is."""
    base = _BACKOFF[min(max(next_attempt_no - 2, 0), len(_BACKOFF) - 1)]
    factor = 0.9 + 0.2 * (random.random() if jitter is None else jitter)
    return max(round(base * factor), retry_after or 0)


HELP: dict[str, str] = {
    "auth": "Het netwerk weigerde de toegang van de generator. Koppel het account opnieuw "
    "via Accounts en probeer het daarna opnieuw.",
    "rate_limited": "Het netwerk vroeg om even te wachten. "
    "Er wordt automatisch opnieuw geprobeerd.",
    "timeout": "Het netwerk antwoordde niet op tijd. Voor een nieuwe poging wordt eerst "
    "gecontroleerd of de post al online staat.",
    "network": "Het netwerk was niet bereikbaar. Er wordt automatisch opnieuw geprobeerd.",
    "provider_unavailable": "Het netwerk had een storing. Voor een nieuwe poging wordt eerst "
    "gecontroleerd of de post al online staat.",
    "media_not_ready": "Het netwerk was het beeld nog aan het verwerken.",
    "validation": "Het netwerk weigerde de inhoud. Pas de post of het bijschrift aan en plan "
    "opnieuw in.",
    "blocked": "Het netwerk heeft de publicatie geblokkeerd (beleid of spamfilter). Controleer "
    "het account in de app van het netwerk.",
    "missed_window": "Deze publicatie was meer dan een uur te laat en is daarom niet alsnog "
    "verstuurd. Probeer opnieuw om nu te publiceren, of plan opnieuw in.",
    "channel_paused": "Het account is gepauzeerd tot het opnieuw is gekoppeld.",
    "not_publishable": "Niet verstuurd omdat de post niet meer aan de voorwaarden voldoet.",
    "uncertain": "Niet te bevestigen of deze post online staat. Controleer het account; "
    "bij een nieuwe poging wordt eerst opnieuw gecontroleerd.",
    "unknown": "Er ging iets onverwachts mis. Probeer opnieuw en bekijk de log als het blijft "
    "gebeuren.",
}


def failure_message(code: str, provider_message: str | None, final_after: int | None) -> str:
    """Leesbare melding. `final_after` = aantal pogingen als er niet meer automatisch wordt
    geprobeerd; dan belooft de melding geen automatische retry meer."""
    text = HELP.get(code, HELP["unknown"])
    if final_after is not None and classify(code).retryable:
        for promise in (
            " Er wordt automatisch opnieuw geprobeerd.",
            " Voor een nieuwe poging wordt eerst gecontroleerd of de post al online staat.",
        ):
            text = text.replace(promise, "")
        text += (
            f" Gestopt na {final_after} {'poging' if final_after == 1 else 'pogingen'}; "
            "probeer opnieuw wanneer je wilt "
            "(er wordt eerst gecontroleerd of de post al online staat)."
        )
    if provider_message and code != "auth":
        text += f" Netwerk meldde: “{provider_message[:160]}”."
    return text
