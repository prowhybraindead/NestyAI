from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.main import app


def main() -> int:
    parser = argparse.ArgumentParser(description="Export NestyAI OpenAPI JSON Schema.")
    parser.add_argument("--stdout", action="store_true", help="Print schema to stdout instead of saving to a file.")
    args = parser.parse_args()

    # Generate the OpenAPI schema dictionary
    schema = app.openapi()

    if args.stdout:
        print(json.dumps(schema, indent=2))
    else:
        out_path = ROOT / "docs" / "openapi.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(schema, f, indent=2)
        print(f"OpenAPI schema successfully exported to {out_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
