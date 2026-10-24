from pydantic import Field

from app.schema.base import CamelModel
from app.schema.brand import BrandKitData
from app.schema.formats import Format
from app.schema.post import PostDocument
from app.schema.template import TemplateDefinition


class RenderAsset(CamelModel):
    src: str
    width: int | None = None
    height: int | None = None
    mime: str


class RenderOptions(CamelModel):
    show_safe_zones: bool = False
    hide_text: bool = False


class RenderInput(CamelModel):
    """Alles wat de compositie nodig heeft om een formaat te renderen.

    De render-service en de browser-preview krijgen precies dit document, zodat preview en
    export dezelfde bron hebben.
    """

    format: Format
    template: TemplateDefinition
    brand: BrandKitData
    post: PostDocument
    assets: dict[str, RenderAsset] = Field(default_factory=dict)
    options: RenderOptions = RenderOptions()
