"""Gedeelde documentschema's. Bron van waarheid voor Python en TypeScript.

TypeScript-types worden hieruit gegenereerd met scripts/export_schema.py en
`pnpm schema:generate`. Pas types dus hier aan, nooit in packages/schema.
"""

from app.schema.brand import BrandColors, BrandFont, BrandFontFile, BrandKitData, BrandLogos
from app.schema.formats import Format, FormatsConfig, SafeZone
from app.schema.post import LayerOverride, PostDocument
from app.schema.quality import LayerReport, LayoutReport, QualityIssue
from app.schema.render import RenderAsset, RenderInput, RenderOptions
from app.schema.template import (
    Box,
    ContentField,
    Layer,
    LayerLayout,
    Point,
    PromptSpec,
    ShapeStyle,
    TemplateDefinition,
    TextStyle,
)

__all__ = [
    "BrandColors",
    "BrandFont",
    "BrandFontFile",
    "BrandKitData",
    "BrandLogos",
    "Box",
    "ContentField",
    "Format",
    "FormatsConfig",
    "Layer",
    "LayerLayout",
    "LayerOverride",
    "LayerReport",
    "LayoutReport",
    "Point",
    "PostDocument",
    "PromptSpec",
    "QualityIssue",
    "RenderAsset",
    "RenderInput",
    "RenderOptions",
    "SafeZone",
    "ShapeStyle",
    "TemplateDefinition",
    "TextStyle",
]
