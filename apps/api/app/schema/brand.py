from typing import Literal

from pydantic import Field

from app.schema.base import CamelModel

HEX = r"^#[0-9a-fA-F]{6}$"
LockKey = Literal["logo", "colors", "fonts", "style_anchor"]


class BrandColors(CamelModel):
    primary: str = Field(pattern=HEX)
    secondary: str = Field(pattern=HEX)
    accent: str = Field(pattern=HEX)
    text_on_dark: str = Field(pattern=HEX)
    text_on_light: str = Field(pattern=HEX)


class BrandFontFile(CamelModel):
    asset_id: str
    weight: int = 400
    style: Literal["normal", "italic"] = "normal"


class BrandFont(CamelModel):
    family: str
    files: list[BrandFontFile] = []
    fallback: str = "Arial, Helvetica, sans-serif"


class BrandFonts(CamelModel):
    heading: BrandFont
    body: BrandFont


class BrandLogos(CamelModel):
    """Asset-id's. light = lichte variant voor donkere achtergronden."""

    logo_light: str | None = None
    logo_dark: str | None = None
    logo_icon: str | None = None


class StyleAnchor(CamelModel):
    description: str = ""
    reference_asset_ids: list[str] = Field(default_factory=list, max_length=6)


class BrandKitData(CamelModel):
    colors: BrandColors
    fonts: BrandFonts
    logos: BrandLogos = BrandLogos()
    style_anchor: StyleAnchor = StyleAnchor()
    negative_prompt: str = ""
    locks: list[LockKey] = ["logo", "colors", "fonts"]
