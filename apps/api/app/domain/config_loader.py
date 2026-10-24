"""Laadt formats.yaml en de template-YAML's uit de repo en valideert ze."""

from functools import lru_cache
from pathlib import Path

import yaml

from app.schema import FormatsConfig, TemplateDefinition
from app.settings import get_settings


def _read_yaml(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


@lru_cache
def load_formats() -> FormatsConfig:
    return FormatsConfig.model_validate(_read_yaml(get_settings().config_dir / "formats.yaml"))


def load_templates() -> list[TemplateDefinition]:
    paths = sorted(get_settings().templates_dir.glob("*.yaml"))
    return [TemplateDefinition.model_validate(_read_yaml(path)) for path in paths]
