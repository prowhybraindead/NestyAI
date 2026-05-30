from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.storage.provider_health import get_latest_provider_health, summarize_provider_health


def _render_rows(rows: list[dict]) -> str:
    if not rows:
        return "No provider health checks."
    headers = ["provider", "model_alias", "role", "model", "status", "latency_ms", "checked_at", "error_code"]
    widths = {h: len(h) for h in headers}
    for row in rows:
        for h in headers:
            value = row.get(h)
            text = "" if value is None else str(value)
            widths[h] = max(widths[h], len(text))

    def _line(values: list[str]) -> str:
        return " | ".join(value.ljust(widths[h]) for value, h in zip(values, headers))

    lines = [_line(headers), "-+-".join("-" * widths[h] for h in headers)]
    for row in rows:
        lines.append(
            _line(
                [
                    str(row.get("provider") or ""),
                    str(row.get("model_alias") or ""),
                    str(row.get("role") or ""),
                    str(row.get("model") or ""),
                    str(row.get("status") or ""),
                    str(row.get("latency_ms") if row.get("latency_ms") is not None else ""),
                    str(row.get("checked_at") or ""),
                    str(row.get("error_code") or ""),
                ]
            )
        )
    return "\n".join(lines)


def _run(args) -> int:
    limit = max(1, int(args.limit or 50))
    rows = get_latest_provider_health(provider=args.provider, model_alias=args.model_alias)
    if len(rows) > limit:
        rows = rows[:limit]
    summary = summarize_provider_health()
    payload = {
        "ok": True,
        "filters": {
            "provider": args.provider,
            "model_alias": args.model_alias,
            "limit": limit,
        },
        "summary": summary,
        "latest": rows,
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=True))
        return 0

    print(_render_rows(rows))
    print(f"total_checks: {summary.get('total_checks', 0)}")
    print(f"avg_latency_ms: {summary.get('avg_latency_ms')}")
    print(f"status_counts: {summary.get('status_counts')}")
    print("status: ok")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Print latest provider health diagnostics summary from local SQLite.")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--provider", type=str, default=None)
    parser.add_argument("--model-alias", type=str, default=None)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    return _run(args)


if __name__ == "__main__":
    raise SystemExit(main())
