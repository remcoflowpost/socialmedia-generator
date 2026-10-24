"""Schrijft genormaliseerde formats en templates naar packages/layout/test/fixtures.json.

De TypeScript-tests gebruiken zo exact dezelfde, door Pydantic gevalideerde documenten
(met ingevulde defaults) als de API.
"""

import json
import sys
from pathlib import Path

from app.domain.config_loader import load_formats, load_templates

OUTPUT = Path(__file__).resolve().parents[3] / "packages" / "layout" / "test" / "fixtures.json"


def main() -> int:
    data = {
        "formats": [f.model_dump(by_alias=True) for f in load_formats().formats],
        "templates": {t.key: t.model_dump(by_alias=True) for t in load_templates()},
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"geschreven: {OUTPUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
