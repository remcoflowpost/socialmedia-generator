from datetime import UTC, datetime, timedelta

from app.domain.naming import embargo_active, export_filename, slugify, zip_filename


def test_slugify_strips_accents_and_symbols() -> None:
    assert slugify("Café Één: VFX-breakdown!") == "cafe-een-vfx-breakdown"
    assert slugify("   ") == "post"


def test_export_filename_follows_convention() -> None:
    name = export_filename("bedrijf-b", "nieuwe-serie", "instagram", "story", 3, "jpg")
    assert name == "bedrijf-b_nieuwe-serie_instagram-story_v003.jpg"


def test_embargo_prefix() -> None:
    assert (
        export_filename("a", "b", "linkedin", "square", 12, "png", embargo=True)
        == "EMBARGO_a_b_linkedin-square_v012.png"
    )
    assert zip_filename("a", "b", 1, embargo=True) == "EMBARGO_a_b_alle-formaten_v001.zip"


def test_embargo_active_only_in_future() -> None:
    now = datetime(2026, 10, 24, tzinfo=UTC)
    assert embargo_active(now + timedelta(hours=1), now)
    assert not embargo_active(now - timedelta(hours=1), now)
    assert not embargo_active(None, now)
