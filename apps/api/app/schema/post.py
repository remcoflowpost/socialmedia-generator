from pydantic import Field

from app.schema.base import CamelModel
from app.schema.template import Point

ContentValue = str | list[str] | None


class LayerOverride(CamelModel):
    """Afwijking per laag voor een post. Alleen toegestaan op lagen die editable zijn en
    niet onder een brand-kit-lock vallen."""

    asset_id: str | None = None
    focus: Point | None = None
    hidden: bool | None = None


class PostDocument(CamelModel):
    """Het bewerkbare deel van een post: ingevulde velden en per-laag overrides."""

    content: dict[str, ContentValue] = Field(default_factory=dict)
    overrides: dict[str, LayerOverride] = Field(default_factory=dict)
