from typing import Literal

from pydantic import Field, model_validator

from app.schema.base import CamelModel

ExportType = Literal["jpeg", "png", "mp4"]


class SafeZone(CamelModel):
    top: int = Field(ge=0)
    bottom: int = Field(ge=0)
    left: int = Field(ge=0)
    right: int = Field(ge=0)


class Format(CamelModel):
    id: str = Field(pattern=r"^[a-z0-9-]+$")
    platform: str = Field(pattern=r"^[a-z0-9-]+$")
    label: str
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    layout_class: str
    safe_zone: SafeZone
    exports: list[ExportType]

    @property
    def key(self) -> str:
        return f"{self.platform}/{self.id}"

    @model_validator(mode="after")
    def _safe_zone_fits(self) -> "Format":
        zone = self.safe_zone
        if zone.left + zone.right >= self.width or zone.top + zone.bottom >= self.height:
            raise ValueError(f"safe zone van {self.platform}/{self.id} is groter dan het canvas")
        return self


class FormatsConfig(CamelModel):
    formats: list[Format]

    @model_validator(mode="after")
    def _unique_keys(self) -> "FormatsConfig":
        keys = [f.key for f in self.formats]
        duplicates = {k for k in keys if keys.count(k) > 1}
        if duplicates:
            raise ValueError(f"dubbele formaten: {sorted(duplicates)}")
        return self

    def get(self, key: str) -> Format | None:
        return next((f for f in self.formats if f.key == key), None)
