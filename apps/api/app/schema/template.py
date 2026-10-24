from typing import Literal

from pydantic import Field, model_validator

from app.schema.base import CamelModel

Anchor = Literal[
    "top-left",
    "top",
    "top-right",
    "left",
    "center",
    "right",
    "bottom-left",
    "bottom",
    "bottom-right",
]
LayerType = Literal["background", "image", "element", "logo", "text", "shape", "video"]
LayerSource = Literal["upload", "brand_asset", "generated", "content_field", "static"]
FieldType = Literal["text", "longtext", "image", "select", "multiselect", "date"]
BrandAssetKey = Literal["logo_light", "logo_dark", "logo_icon"]


class Point(CamelModel):
    """Focuspunt, 0..1 over breedte en hoogte van het bronbeeld."""

    x: float = Field(0.5, ge=0, le=1)
    y: float = Field(0.5, ge=0, le=1)


class Box(CamelModel):
    """Positie en grootte in procenten van de safe area (of het canvas bij bleed).

    x en y zijn offsets vanaf het anker naar binnen; bij anker "center" schuiven ze
    het midden op.
    """

    anchor: Anchor = "top-left"
    x: float = 0
    y: float = 0
    width: float = Field(100, gt=0)
    height: float = Field(100, gt=0)
    bleed: bool = False


class LayerLayout(CamelModel):
    """Layout voor een formaat. Alle velden optioneel, zodat overrides alleen afwijkingen
    hoeven op te geven. Volgorde van samenvoegen: default, layout_class, formaatsleutel.
    """

    box: Box | None = None
    hidden: bool | None = None
    fit: Literal["cover", "contain"] | None = None
    focus: Point | None = None
    min_font_size: float | None = Field(None, gt=0)
    max_font_size: float | None = Field(None, gt=0)
    max_lines: int | None = Field(None, ge=1)
    align: Literal["left", "center", "right"] | None = None
    vertical_align: Literal["top", "center", "bottom"] | None = None


class TextStyle(CamelModel):
    font: Literal["heading", "body"] = "body"
    weight: int = 400
    color: str = "text_on_dark"
    line_height: float = 1.15
    letter_spacing: float = 0
    uppercase: bool = False


class Gradient(CamelModel):
    from_color: str
    to_color: str
    from_opacity: float = Field(1, ge=0, le=1)
    to_opacity: float = Field(0, ge=0, le=1)
    angle: float = 180


class ShapeStyle(CamelModel):
    fill: str | None = None
    gradient: Gradient | None = None
    opacity: float = Field(1, ge=0, le=1)
    radius: float = 0


class PromptSpec(CamelModel):
    """Generatie-instructie per laag. Wordt in fase 2 gebruikt, staat er nu al in zodat
    templates niet opnieuw hoeven te worden opgezet."""

    kind: Literal["image", "video", "element"]
    base: str
    variables: list[str] = []
    inherit_brand_style: bool = True
    use_brand_references: bool = True
    negative: str = ""
    provider: str = "mock"
    model: str | None = None
    master_aspect: str = "1:1"
    seed: int | None = None
    variants: int = Field(3, ge=1, le=4)


class ContentField(CamelModel):
    key: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    label: str
    type: FieldType
    required: bool = False
    max_length: int | None = Field(None, gt=0)
    options: list[str] = []
    help: str | None = None
    min_width: int | None = Field(None, gt=0)


class Layer(CamelModel):
    id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    type: LayerType
    source: LayerSource
    z: int
    editable: bool = False
    field: str | None = None
    brand_asset: BrandAssetKey | None = None
    static: str | None = None
    text_style: TextStyle | None = None
    shape_style: ShapeStyle | None = None
    layouts: dict[str, LayerLayout]
    prompt: PromptSpec | None = None

    @model_validator(mode="after")
    def _source_consistent(self) -> "Layer":
        if "default" not in self.layouts:
            raise ValueError(f"laag {self.id} mist een default-layout")
        if self.source in ("upload", "content_field") and not self.field:
            raise ValueError(f"laag {self.id} met bron {self.source} heeft een field nodig")
        if self.source == "brand_asset" and not self.brand_asset:
            raise ValueError(f"laag {self.id} met bron brand_asset heeft brandAsset nodig")
        if self.source == "generated" and not self.prompt:
            raise ValueError(f"laag {self.id} met bron generated heeft een prompt nodig")
        if self.type == "text" and not self.text_style:
            raise ValueError(f"tekstlaag {self.id} heeft een textStyle nodig")
        if self.type == "shape" and not self.shape_style:
            raise ValueError(f"vormlaag {self.id} heeft een shapeStyle nodig")
        return self


class TemplateDefinition(CamelModel):
    key: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    name: str
    type: str
    version: int = Field(1, ge=1)
    description: str = ""
    formats: list[str] | None = None
    fields: list[ContentField]
    layers: list[Layer]

    @model_validator(mode="after")
    def _references_exist(self) -> "TemplateDefinition":
        field_keys = {f.key for f in self.fields}
        for layer in self.layers:
            if layer.field and layer.field not in field_keys:
                raise ValueError(f"laag {layer.id} verwijst naar onbekend veld {layer.field}")
        layer_ids = [layer.id for layer in self.layers]
        if len(layer_ids) != len(set(layer_ids)):
            raise ValueError("laag-id's moeten uniek zijn")
        return self
