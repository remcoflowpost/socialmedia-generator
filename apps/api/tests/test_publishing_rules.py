"""Pure regels van publiceren: tijdzones, platformregels, retrymeldingen, versleuteling."""

from datetime import UTC, date, datetime, time, timedelta

import pytest

from app.publishing import crypto
from app.publishing.retry import backoff_seconds, classify, failure_message
from app.publishing.rules import PublishFacts, check_publishable, normalize_caption
from app.publishing.slots import (
    LocalTimeError,
    Slot,
    is_valid_timezone,
    next_open_slot,
    resolve_local,
    slot_instants_between,
    week_start,
)

AMS = "Europe/Amsterdam"
NOW = datetime(2026, 10, 16, 8, 0, tzinfo=UTC)


def facts(**over) -> PublishFacts:
    base = dict(
        provider="instagram",
        account_status="active",
        account_company_id="c1",
        post_company_id="c1",
        format_key="instagram/feed-portrait",
        caption="Nieuw project opgeleverd.",
        version_number=3,
        approved_version=3,
        embargo_until=None,
        export_ok=True,
        export_severity=None,
        media_mime="image/jpeg",
        media_bytes=900_000,
        media_width=1080,
        media_height=1350,
        scheduled_at=NOW + timedelta(days=1),
        now=NOW,
    )
    return PublishFacts(**(base | over))


def codes(f: PublishFacts, **kw) -> list[str]:
    return sorted(i.code for i in check_publishable(f, **kw))


# ------------------------------------------------------------------ tijdzones


def test_local_time_resolves_in_named_zone() -> None:
    assert resolve_local(date(2026, 10, 20), time(9), AMS) == datetime(2026, 10, 20, 7, tzinfo=UTC)


def test_nonexistent_time_is_refused_when_chosen_and_shifted_for_slots() -> None:
    with pytest.raises(LocalTimeError):
        resolve_local(date(2027, 3, 28), time(2, 30), AMS)
    shifted = resolve_local(date(2027, 3, 28), time(2, 30), AMS, strict=False)
    assert shifted == datetime(2027, 3, 28, 1, 30, tzinfo=UTC)  # 03:30 CEST


def test_ambiguous_time_takes_first_occurrence() -> None:
    assert resolve_local(date(2026, 10, 25), time(2, 30), AMS) == datetime(
        2026, 10, 25, 0, 30, tzinfo=UTC
    )


def test_slots_keep_local_time_across_dst() -> None:
    slots = [Slot(1, "09:00")]
    got = slot_instants_between(
        slots, AMS, datetime(2026, 10, 19, tzinfo=UTC), datetime(2026, 11, 2, tzinfo=UTC)
    )
    assert got == [
        datetime(2026, 10, 19, 7, tzinfo=UTC),
        datetime(2026, 10, 26, 8, tzinfo=UTC),
    ]


def test_next_open_slot_skips_occupied_and_lead_time() -> None:
    slots = [Slot(1, "09:00"), Slot(3, "12:30")]
    now = datetime(2026, 10, 19, 6, 59, 30, tzinfo=UTC)
    occupied = {datetime(2026, 10, 21, 10, 30, tzinfo=UTC)}
    assert next_open_slot(slots, AMS, occupied, now) == datetime(2026, 10, 26, 8, tzinfo=UTC)
    assert next_open_slot([], AMS, set(), now) is None


def test_week_starts_on_monday_in_company_zone() -> None:
    assert week_start(AMS, datetime(2026, 10, 18, 23, 30, tzinfo=UTC)) == date(2026, 10, 19)
    assert is_valid_timezone(AMS)
    assert not is_valid_timezone("Mars/Base")


# ------------------------------------------------------------------ platformregels


def test_valid_publication_passes() -> None:
    assert codes(facts()) == []


def test_instagram_3x4_is_refused_with_a_hint() -> None:
    issues = check_publishable(facts(format_key="instagram/feed-3x4", media_height=1440))
    assert issues[0].code == "format"
    assert "3:4" in issues[0].message


def test_instagram_rejects_png_large_files_and_bad_ratio() -> None:
    f = facts(
        format_key="instagram/feed-square",
        media_mime="image/png",
        media_bytes=9 * 1024 * 1024,
        media_width=1080,
        media_height=1500,
    )
    assert codes(f) == ["aspect", "media_size", "media_type"]


def test_caption_limits_and_hashtags_per_platform() -> None:
    assert codes(facts(caption="x" * 2201)) == ["caption"]
    assert codes(facts(caption=" ".join(f"#t{i}" for i in range(31)))) == ["hashtags"]
    assert (
        codes(
            facts(provider="facebook_page", format_key="facebook/feed-square", caption="x" * 2201)
        )
        == []
    )
    assert codes(facts(format_key="instagram/story", media_height=1920, caption="nee")) == [
        "caption"
    ]


def test_approval_must_match_the_exact_version() -> None:
    assert codes(facts(approved_version=None)) == ["approval"]
    issue = check_publishable(facts(approved_version=2))[0]
    assert "versie 2, niet voor versie 3" in issue.message


def test_embargo_quality_export_company_and_account_are_enforced() -> None:
    assert codes(facts(embargo_until=NOW + timedelta(days=2))) == ["embargo"]
    assert codes(facts(export_severity="error")) == ["quality"]
    assert codes(facts(export_ok=False)) == ["export"]
    assert codes(facts(account_company_id="c2")) == ["company"]
    assert codes(facts(account_status="reauth_required")) == ["account"]


def test_time_rules_only_at_scheduling_not_at_send_time() -> None:
    late = facts(scheduled_at=NOW - timedelta(minutes=5))
    assert codes(late) == ["past"]
    assert codes(late, at_send_time=True) == []
    assert codes(facts(scheduled_at=NOW + timedelta(days=400))) == ["too_far"]


def test_daily_instagram_limit() -> None:
    assert codes(facts(published_last_24h=100)) == ["daily_limit"]


def test_caption_normalization() -> None:
    assert normalize_caption("  hoi\r\nwereld‮  \n") == "hoi\nwereld"
    assert normalize_caption("é") == "é"


# ------------------------------------------------------------------ retry


def test_classification_and_backoff() -> None:
    assert classify("timeout").uncertain and classify("timeout").retryable
    assert not classify("auth").retryable
    assert backoff_seconds(2, jitter=0.5) == 60
    assert backoff_seconds(3, jitter=0.5) == 300
    assert backoff_seconds(9, jitter=0.5) == 900
    assert backoff_seconds(2, retry_after=600, jitter=0.5) == 600


def test_final_failure_message_never_promises_an_automatic_retry() -> None:
    during = failure_message("network", "connect refused", None)
    final = failure_message("network", "connect refused", 3)
    assert "automatisch opnieuw" in during
    assert "automatisch opnieuw" not in final
    assert "Gestopt na 3 pogingen" in final
    assert "Netwerk meldde" in final
    assert "Netwerk meldde" not in failure_message("auth", "token EAAxyz", None)


# ------------------------------------------------------------------ versleuteling


def test_tokens_roundtrip_and_are_bound_to_their_row() -> None:
    blob = crypto.encrypt("EAAgeheimetoken", "account-1")
    assert blob.startswith("v1.") and "EAAgeheim" not in blob
    assert crypto.decrypt(blob, "account-1") == "EAAgeheimetoken"
    with pytest.raises(Exception):  # noqa: B017 - InvalidTag van cryptography
        crypto.decrypt(blob, "account-2")
