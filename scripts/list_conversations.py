from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.storage.conversations import (
    export_conversation,
    get_conversation,
    get_conversation_stats,
    list_conversations,
)
from app.storage.db import init_db


def main() -> int:
    parser = argparse.ArgumentParser(description="List conversations in NestyAI SQLite DB.")
    parser.add_argument("--limit", type=int, default=20, help="Maximum number of conversations to list.")
    parser.add_argument("--db", type=str, default=None, help="Optional DB path override.")
    parser.add_argument(
        "--show-summary",
        action="store_true",
        help="Show summary content (off by default).",
    )
    parser.add_argument("--export", type=str, default="", help="Export a conversation by id as JSON.")
    args = parser.parse_args()

    db_path = args.db or os.getenv("NESTY_DB_PATH", "data/nesty.db")
    init_db(db_path)

    if args.export.strip():
        exported = export_conversation(
            conversation_id=args.export.strip(),
            api_key_id=None,
            db_path=db_path,
        )
        if exported is None:
            print("Conversation not found.")
            return 1
        print(json.dumps(exported, ensure_ascii=True, indent=2))
        return 0

    rows = list_conversations(api_key_id=None, limit=max(1, int(args.limit)), offset=0, db_path=db_path)

    if not rows:
        print("No conversations found.")
        return 0

    if args.show_summary:
        print(
            "id | title | updated_at | message_count | last_message_at | "
            "summary_message_count | summary_updated_at | summary | summary_exists"
        )
    else:
        print(
            "id | title | updated_at | message_count | last_message_at | "
            "summary_message_count | summary_updated_at | summary_exists"
        )
    for row in rows:
        stats = get_conversation_stats(str(row["id"]), db_path=db_path)
        columns = [
            str(row["id"]),
            str(row["title"] or "-"),
            str(row["updated_at"]),
            str(int(stats.get("message_count") or 0)),
            str(stats.get("last_message_at") or "-"),
            str(int(row.get("summary_message_count") or 0)),
            str(row.get("summary_updated_at") or "-"),
        ]
        if args.show_summary:
            conversation = get_conversation(str(row["id"]), db_path=db_path)
            summary = str((conversation or {}).get("summary") or "-")
            columns.append(summary)
        columns.append(str(bool(row.get("summary_exists"))))
        print(" | ".join(columns))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
