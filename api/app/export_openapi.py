"""Write the API's OpenAPI schema to web/src/api/openapi.json (NFR-M2)."""

import json
from pathlib import Path

from app.main import app

# api/app/export_openapi.py -> parents[2] is the repository root
OUT = Path(__file__).resolve().parents[2] / "web" / "src" / "api" / "openapi.json"


def render() -> str:
    return json.dumps(app.openapi(), indent=2, ensure_ascii=False) + "\n"


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(render(), encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
