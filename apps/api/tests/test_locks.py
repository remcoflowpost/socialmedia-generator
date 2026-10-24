import pytest

from app.domain.config_loader import load_templates
from app.domain.locks import LockViolation, validate_document
from app.schema import BrandKitData, PostDocument

TEMPLATE = next(t for t in load_templates() if t.key == "project_announcement")
BRAND = BrandKitData.model_validate(
    {
        "colors": {
            "primary": "#000000",
            "secondary": "#111111",
            "accent": "#222222",
            "textOnDark": "#ffffff",
            "textOnLight": "#000000",
        },
        "fonts": {"heading": {"family": "A"}, "body": {"family": "B"}},
        "locks": ["logo", "colors", "fonts"],
    }
)


def doc(**kwargs) -> PostDocument:
    return PostDocument.model_validate(kwargs)


def test_editor_may_override_editable_layer() -> None:
    validate_document(
        doc(overrides={"photo": {"focus": {"x": 0.2, "y": 0.4}}}), TEMPLATE, BRAND, "editor"
    )


def test_editor_may_not_touch_locked_logo() -> None:
    with pytest.raises(LockViolation):
        validate_document(doc(overrides={"logo": {"hidden": True}}), TEMPLATE, BRAND, "editor")


def test_admin_may_override_everything() -> None:
    validate_document(doc(overrides={"logo": {"hidden": True}}), TEMPLATE, BRAND, "admin")


def test_max_length_enforced_server_side() -> None:
    with pytest.raises(LockViolation, match="maximaal 70"):
        validate_document(doc(content={"headline": "x" * 71}), TEMPLATE, BRAND, "editor")


def test_select_value_must_be_option() -> None:
    with pytest.raises(LockViolation):
        validate_document(doc(content={"label": "Iets anders"}), TEMPLATE, BRAND, "editor")


def test_unknown_field_rejected() -> None:
    with pytest.raises(LockViolation):
        validate_document(doc(content={"bedrijfsnaam": "x"}), TEMPLATE, BRAND, "editor")
