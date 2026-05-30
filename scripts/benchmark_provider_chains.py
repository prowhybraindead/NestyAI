from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.provider_diagnostics import diagnose_all_model_aliases, diagnose_model_alias
from app.deps import get_settings


def _render_rows(rows: list[dict]) -> str:
    if not rows:
        return "No targets."
    headers = ["model_alias", "role", "provider", "model", "status", "latency_ms", "tps", "error_code"]
    widths = {h: len(h) for h in headers}
    for row in rows:
        widths["model_alias"] = max(widths["model_alias"], len(str(row.get("model_alias") or "")))
        widths["role"] = max(widths["role"], len(str(row.get("role") or "")))
        widths["provider"] = max(widths["provider"], len(str(row.get("provider") or "")))
        widths["model"] = max(widths["model"], len(str(row.get("model") or "")))
        widths["status"] = max(widths["status"], len(str(row.get("status") or "")))
        widths["latency_ms"] = max(widths["latency_ms"], len(str(row.get("latency_ms") if row.get("latency_ms") is not None else "")))
        tps = row.get("tokens_per_second")
        widths["tps"] = max(widths["tps"], len(f"{float(tps):.2f}" if tps is not None else ""))
        widths["error_code"] = max(widths["error_code"], len(str(row.get("error_code") or "")))

    def _line(values: list[str]) -> str:
        return " | ".join(value.ljust(widths[h]) for value, h in zip(values, headers))

    lines = [_line(headers), "-+-".join("-" * widths[h] for h in headers)]
    for row in rows:
        tps = row.get("tokens_per_second")
        lines.append(
            _line(
                [
                    str(row.get("model_alias") or ""),
                    str(row.get("role") or ""),
                    str(row.get("provider") or ""),
                    str(row.get("model") or ""),
                    str(row.get("status") or ""),
                    str(row.get("latency_ms") if row.get("latency_ms") is not None else ""),
                    f"{float(tps):.2f}" if tps is not None else "",
                    str(row.get("error_code") or ""),
                ]
            )
        )
    return "\n".join(lines)


async def _run(args) -> int:
    settings = get_settings()
    if not bool(getattr(settings, "diagnostics_enabled", True)):
        print("status: diagnostics_disabled")
        return 0

    save_enabled = bool(args.save) and not bool(args.dry_run)
    if args.model_alias:
        result = await diagnose_model_alias(
            model_alias=args.model_alias,
            include_roles=bool(args.include_roles),
            message=args.message,
            dry_run=not save_enabled,
        )
    else:
        result = await diagnose_all_model_aliases(
            message=args.message,
            include_roles=bool(args.include_roles),
            dry_run=not save_enabled,
        )

    rows: list[dict] = []
    if "items" in result:
        for item in result.get("items") or []:
            rows.extend(list(item.get("results") or []))
    else:
        rows.extend(list(result.get("results") or []))

    payload = {
        "ok": True,
        "model_alias": args.model_alias,
        "include_roles": bool(args.include_roles),
        "saved": save_enabled,
        "summary": result.get("summary"),
        "rows": [
            {
                "model_alias": row.get("model_alias"),
                "role": row.get("role"),
                "provider": row.get("provider"),
                "model": row.get("model"),
                "status": row.get("status"),
                "latency_ms": row.get("latency_ms"),
                "tokens_per_second": row.get("tokens_per_second"),
                "error_code": row.get("error_code"),
            }
            for row in rows
        ],
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=True))
        return 0

    print(_render_rows(payload["rows"]))
    summary = payload.get("summary") or {}
    print(f"summary_total: {summary.get('total', 0)}")
    print(f"summary_ok: {summary.get('ok', 0)}")
    print(f"summary_failed: {summary.get('failed', 0)}")
    print("status: ok")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark configured provider chains with small diagnostic prompts.")
    parser.add_argument("--model-alias", type=str, default=None)
    parser.add_argument("--include-roles", action="store_true")
    parser.add_argument("--message", type=str, default="Reply with exactly: OK")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.set_defaults(save=True)
    parser.add_argument("--save", dest="save", action="store_true")
    parser.add_argument("--no-save", dest="save", action="store_false")
    args = parser.parse_args()
    return asyncio.run(_run(args))


if __name__ == "__main__":
    raise SystemExit(main())
