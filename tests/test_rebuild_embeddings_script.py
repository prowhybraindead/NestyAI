from __future__ import annotations

import argparse
import asyncio
import importlib

from app.storage.conversations import add_message, create_conversation
from app.storage.db import init_db


def test_rebuild_embeddings_script_import_has_no_side_effects() -> None:
    module = importlib.import_module("scripts.rebuild_embeddings")
    assert callable(module.main)


def test_rebuild_embeddings_script_dry_run(monkeypatch, tmp_path, capsys) -> None:
    module = importlib.import_module("scripts.rebuild_embeddings")
    db_path = str(tmp_path / "rebuild_embeddings.db")
    init_db(db_path)

    conversation = create_conversation(api_key_id="key_1", title="Test", db_path=db_path)
    add_message(
        conversation_id=conversation["id"],
        role="user",
        content="This is a message for embeddings.",
        db_path=db_path,
    )

    monkeypatch.setattr(
        module,
        "get_settings",
        lambda: type(
            "S",
            (),
            {
                "nesty_db_path": db_path,
                "embeddings_enabled": True,
                "embeddings_provider": "openrouter",
                "embeddings_model": "nvidia/llama-nemotron-embed-vl-1b-v2:free",
                "embeddings_backfill_batch_size": 50,
            },
        )(),
    )
    args = argparse.Namespace(
        db=db_path,
        owner_type="conversation_message",
        limit=10,
        dry_run=True,
    )
    code = asyncio.run(module._run(args))
    output = capsys.readouterr().out
    assert code == 0
    assert "candidates_found: 1" in output
    assert "embedded_count: 0" in output
    assert "skipped_count: 1" in output
    assert "This is a message for embeddings." not in output
