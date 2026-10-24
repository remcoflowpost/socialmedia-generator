from typing import Any, Literal

from app.schema.base import CamelModel

Severity = Literal["warning", "error"]
IssueCode = Literal[
    "missing_required_field",
    "missing_asset",
    "resolution_low",
    "resolution_too_low",
    "outside_safe_zone",
    "text_overflow",
    "contrast_low",
    "embargo_active",
    "font_missing",
]


class QualityIssue(CamelModel):
    code: IssueCode
    severity: Severity
    message: str
    layer_id: str | None = None
    format_key: str | None = None
    details: dict[str, Any] = {}


class PixelBox(CamelModel):
    x: float
    y: float
    width: float
    height: float


class LayerReport(CamelModel):
    id: str
    type: str
    hidden: bool
    box: PixelBox
    font_size: float | None = None
    lines: list[str] | None = None
    color: str | None = None
    source_scale: float | None = None


class LayoutReport(CamelModel):
    """Uitkomst van de layout-engine (TypeScript) voor een formaat."""

    format_key: str
    width: int
    height: int
    layers: list[LayerReport]
    issues: list[QualityIssue]
