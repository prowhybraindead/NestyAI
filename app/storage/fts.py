from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from app.utils.logging import get_logger, log_safe


logger = get_logger("nesty.storage.fts")


def _resolve_db_path(db_path: str) -> Path:
    path = Path(db_path)
    if path.is_absolute():
        return path
    return Path.cwd() / path


def _connect(db_path: str) -> sqlite3.Connection:
    resolved = _resolve_db_path(db_path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(resolved, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def is_fts5_available(db_path: str) -> bool:
    try:
        with _connect(db_path) as conn:
            conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS temp._nesty_fts5_probe USING fts5(content)")
            conn.execute("DROP TABLE IF EXISTS temp._nesty_fts5_probe")
            return True
    except Exception:
        return False


def init_conversation_fts(db_path: str) -> bool:
    if not is_fts5_available(db_path):
        return False
    try:
        with _connect(db_path) as conn:
            conn.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS conversation_messages_fts USING fts5(
                    message_id UNINDEXED,
                    conversation_id UNINDEXED,
                    api_key_id UNINDEXED,
                    role,
                    content,
                    title,
                    summary
                )
                """
            )
            conn.commit()
        return True
    except Exception:
        log_safe(logger, "conversation_fts_init_failed", error_code="fts_init_failed")
        return False


def rebuild_conversation_fts(db_path: str) -> dict[str, Any]:
    if not init_conversation_fts(db_path):
        return {
            "ok": False,
            "fts_available": False,
            "indexed_messages": 0,
            "error_code": "fts_unavailable",
        }

    try:
        with _connect(db_path) as conn:
            conn.execute("DELETE FROM conversation_messages_fts")
            conn.execute(
                """
                INSERT INTO conversation_messages_fts
                (message_id, conversation_id, api_key_id, role, content, title, summary)
                SELECT
                    m.id,
                    m.conversation_id,
                    COALESCE(c.api_key_id, ''),
                    m.role,
                    m.content,
                    COALESCE(c.title, ''),
                    COALESCE(c.summary, '')
                FROM conversation_messages m
                JOIN conversations c ON c.id = m.conversation_id
                """
            )
            row = conn.execute("SELECT COUNT(*) AS total FROM conversation_messages_fts").fetchone()
            conn.commit()
        indexed_messages = int(row["total"] or 0) if row else 0
        return {
            "ok": True,
            "fts_available": True,
            "indexed_messages": indexed_messages,
            "error_code": "",
        }
    except Exception:
        log_safe(logger, "conversation_fts_rebuild_failed", error_code="fts_rebuild_failed")
        return {
            "ok": False,
            "fts_available": True,
            "indexed_messages": 0,
            "error_code": "fts_rebuild_failed",
        }


def sync_message_to_fts(db_path: str, message: dict[str, Any]) -> bool:
    if not init_conversation_fts(db_path):
        return False

    message_id = str(message.get("id") or "").strip()
    conversation_id = str(message.get("conversation_id") or "").strip()
    if not message_id or not conversation_id:
        return False

    try:
        with _connect(db_path) as conn:
            conversation = conn.execute(
                """
                SELECT api_key_id, title, summary
                FROM conversations
                WHERE id = ?
                LIMIT 1
                """,
                (conversation_id,),
            ).fetchone()
            if conversation is None:
                return False

            conn.execute("DELETE FROM conversation_messages_fts WHERE message_id = ?", (message_id,))
            conn.execute(
                """
                INSERT INTO conversation_messages_fts
                (message_id, conversation_id, api_key_id, role, content, title, summary)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    message_id,
                    conversation_id,
                    str(conversation["api_key_id"] or ""),
                    str(message.get("role") or ""),
                    str(message.get("content") or ""),
                    str(conversation["title"] or ""),
                    str(conversation["summary"] or ""),
                ),
            )
            conn.commit()
        return True
    except Exception:
        log_safe(
            logger,
            "conversation_fts_sync_failed",
            error_code="fts_sync_failed",
            message_id=message_id,
            conversation_id=conversation_id,
        )
        return False


def delete_message_from_fts(db_path: str, message_id: str) -> bool:
    if not init_conversation_fts(db_path):
        return False
    try:
        with _connect(db_path) as conn:
            conn.execute("DELETE FROM conversation_messages_fts WHERE message_id = ?", (message_id,))
            conn.commit()
        return True
    except Exception:
        log_safe(logger, "conversation_fts_delete_failed", error_code="fts_delete_failed")
        return False
