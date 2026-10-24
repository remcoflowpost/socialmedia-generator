import json

from app.domain.config_loader import load_formats, load_templates
from app.settings import Settings
from scripts.export_schema import OUTPUT, build_schema


def test_formats_are_valid_and_complete() -> None:
    keys = {f.key for f in load_formats().formats}
    assert len(keys) == 10
    assert {"instagram/story", "linkedin/landscape", "facebook/feed-landscape"} <= keys


def test_story_safe_zone_matches_meta_guidance() -> None:
    story = load_formats().get("instagram/story")
    assert story is not None
    assert (story.safe_zone.top, story.safe_zone.bottom) == (269, 672)


def test_templates_load() -> None:
    assert {t.key for t in load_templates()} == {"project_announcement", "team_member"}


def test_every_layout_class_is_known() -> None:
    known = (
        {f.layout_class for f in load_formats().formats}
        | {f.key for f in load_formats().formats}
        | {"default"}
    )
    for template in load_templates():
        for layer in template.layers:
            unknown = set(layer.layouts) - known
            assert not unknown, f"{template.key}.{layer.id}: onbekende layoutsleutel {unknown}"


def test_generated_schema_is_up_to_date() -> None:
    """Faalt als iemand app/schema aanpast zonder scripts/export_schema.py te draaien."""
    assert json.loads(OUTPUT.read_text()) == json.loads(build_schema())


def test_allowlist_parsing() -> None:
    settings = Settings(
        allowlist=" Remco@Example.test=admin , ed@example.test ,", session_secret="x"
    )
    assert settings.allowed_users() == {"remco@example.test": "admin", "ed@example.test": "editor"}
