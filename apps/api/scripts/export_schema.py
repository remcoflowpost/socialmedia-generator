"""Exporteert de Pydantic-documentschema's naar packages/schema/schema.json.

Daarna maakt `pnpm schema:generate` er TypeScript-types van. Draai beide na elke wijziging
in app/schema; de test test_schema_export controleert of het bestand actueel is.
"""

import json
import sys
from pathlib import Path

from pydantic.json_schema import models_json_schema

from app.schema import (
    BrandKitData,
    FormatsConfig,
    LayoutReport,
    PostDocument,
    RenderInput,
    TemplateDefinition,
)

ROOT_MODELS = [
    BrandKitData,
    FormatsConfig,
    LayoutReport,
    PostDocument,
    RenderInput,
    TemplateDefinition,
]
OUTPUT = Path(__file__).resolve().parents[3] / "packages" / "schema" / "schema.json"


def _strip_titles(node: object, keep: bool = False) -> None:
    """Verwijdert titels van velden, anders maakt json2ts per veld een los type-alias."""
    if isinstance(node, list):
        for item in node:
            _strip_titles(item)
        return
    if not isinstance(node, dict):
        return
    if not keep:
        node.pop("title", None)
    for key, value in node.items():
        if key == "$defs":
            for definition in value.values():
                _strip_titles(definition, keep=True)
            continue
        _strip_titles(value)


def build_schema() -> str:
    _, schema = models_json_schema(
        [(model, "serialization") for model in ROOT_MODELS],
        by_alias=True,
        title="FlowSocialSchema",
        ref_template="#/$defs/{model}",
    )
    _strip_titles(schema, keep=True)
    # json-schema-to-typescript genereert alleen types die vanaf de root bereikbaar zijn.
    schema["type"] = "object"
    schema["properties"] = {m.__name__: {"$ref": f"#/$defs/{m.__name__}"} for m in ROOT_MODELS}
    schema["additionalProperties"] = False
    return json.dumps(schema, indent=2, sort_keys=True) + "\n"


def main() -> int:
    OUTPUT.write_text(build_schema(), encoding="utf-8")
    print(f"geschreven: {OUTPUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
