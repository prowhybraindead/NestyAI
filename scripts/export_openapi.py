from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.main import app  # noqa: E402 – must come after sys.path patch


def main() -> int:
    parser = argparse.ArgumentParser(description="Export NestyAI OpenAPI JSON Schema.")
    parser.add_argument(
        "--stdout",
        action="store_true",
        help="Print schema to stdout instead of saving to a file.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help=(
            "Validate that the on-disk docs/openapi.json matches the current schema "
            "without updating it. Exits 1 if they differ or the file is missing."
        ),
    )
    args = parser.parse_args()

    # Generate the OpenAPI schema dictionary (no provider calls involved).
    schema = app.openapi()

    out_path = ROOT / "docs" / "openapi.json"

    if args.check:
        if not out_path.exists():
            print(
                f"[FAIL] docs/openapi.json does not exist. "
                f"Run `python scripts/export_openapi.py` to generate it.",
                file=sys.stderr,
            )
            return 1
        with open(out_path, encoding="utf-8") as f:
            on_disk = json.load(f)
        if on_disk != schema:
            print(
                "[FAIL] docs/openapi.json is out-of-date with the current schema. "
                "Run `python scripts/export_openapi.py` to regenerate.",
                file=sys.stderr,
            )
            return 1
        print("[PASS] docs/openapi.json is up-to-date with the current schema.")
        return 0

    if args.stdout:
        print(json.dumps(schema, indent=2))
    else:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(schema, f, indent=2)
        print(f"OpenAPI schema successfully exported to {out_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
