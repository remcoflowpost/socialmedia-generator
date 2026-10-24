"""Bouwt het RenderInput-document voor de compositie uit een post-snapshot."""

from collections.abc import Callable, Iterable

from app.schema import (
    BrandKitData,
    Format,
    PostDocument,
    RenderAsset,
    RenderInput,
    RenderOptions,
    TemplateDefinition,
)


def referenced_asset_ids(
    template: TemplateDefinition, brand: BrandKitData, document: PostDocument
) -> set[str]:
    ids: set[str] = set()
    image_fields = {f.key for f in template.fields if f.type == "image"}
    for key in image_fields:
        value = document.content.get(key)
        if isinstance(value, str) and value:
            ids.add(value)
    ids.update(o.asset_id for o in document.overrides.values() if o.asset_id)
    logos = brand.logos
    ids.update(filter(None, (logos.logo_light, logos.logo_dark, logos.logo_icon)))
    for font in (brand.fonts.heading, brand.fonts.body):
        ids.update(file.asset_id for file in font.files)
    return ids


class AssetInfo:
    def __init__(
        self, asset_id: str, storage_key: str, mime: str, width: int | None, height: int | None
    ):
        self.id = asset_id
        self.storage_key = storage_key
        self.mime = mime
        self.width = width
        self.height = height


def build_render_input(
    fmt: Format,
    template: TemplateDefinition,
    brand: BrandKitData,
    document: PostDocument,
    assets: Iterable[AssetInfo],
    url_for: Callable[[AssetInfo], str],
    options: RenderOptions | None = None,
) -> RenderInput:
    return RenderInput(
        format=fmt,
        template=template,
        brand=brand,
        post=document,
        assets={
            asset.id: RenderAsset(
                src=url_for(asset), mime=asset.mime, width=asset.width, height=asset.height
            )
            for asset in assets
        },
        options=options or RenderOptions(),
    )
