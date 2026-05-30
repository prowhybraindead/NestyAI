from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.storage.db import init_db
from app.storage.fts import is_fts5_available, rebuild_conversation_fts


def main() -> int:
    parser = argparse.ArgumentParser(description="Rebuild SQLite FTS index for NestyAI conversations.")
    parser.add_argument("--db", type=str, default=None, help="Optional DB path override.")
    args = parser.parse_args()

    db_path = args.db or os.getenv("NESTY_DB_PATH", "data/nesty.db")
    init_db(db_path)

    available = is_fts5_available(db_path)
    print(f"fts5_available: {available}")
    if not available:
        print("indexed_messages: 0")
        print("status: unavailable")
        return 0

    result = rebuild_conversation_fts(db_path)
    print(f"indexed_messages: {int(result.get('indexed_messages') or 0)}")
    if result.get("ok"):
        print("status: ok")
        return 0
    print(f"status: {str(result.get('error_code') or 'fts_rebuild_failed')}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
