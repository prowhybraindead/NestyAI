from __future__ import annotations

from app.storage.db import init_db
from app.storage.embeddings import (
    count_embedding_records,
    create_embedding_record,
    delete_embeddings_for_owner,
    get_embedding_for_owner,
    list_embeddings_for_owner,
    upsert_embedding_record,
)


def test_embedding_records_table_initializes_and_crud_works(tmp_path) -> None:
    db_path = str(tmp_path / "embedding_storage.db")
    init_db(db_path)

    created = create_embedding_record(
        owner_type="conversation_message",
        owner_id="msg_1",
        api_key_id="key_1",
        provider="openrouter",
        model="nvidia/llama-nemotron-embed-vl-1b-v2:free",
        embedding=[0.1, 0.2, 0.3],
        content_hash="hash_1",
        metadata={"role": "user"},
        db_path=db_path,
    )
    assert created["owner_id"] == "msg_1"
    assert created["dimensions"] == 3
    assert count_embedding_records(db_path=db_path) == 1

    fetched = get_embedding_for_owner(
        owner_type="conversation_message",
        owner_id="msg_1",
        provider="openrouter",
        model="nvidia/llama-nemotron-embed-vl-1b-v2:free",
        db_path=db_path,
    )
    assert fetched is not None
    assert fetched["embedding"] == [0.1, 0.2, 0.3]
    assert fetched["metadata"]["role"] == "user"

    listed = list_embeddings_for_owner("conversation_message", "msg_1", db_path=db_path)
    assert len(listed) == 1
    assert listed[0]["provider"] == "openrouter"

    updated = upsert_embedding_record(
        owner_type="conversation_message",
        owner_id="msg_1",
        api_key_id="key_1",
        provider="openrouter",
        model="nvidia/llama-nemotron-embed-vl-1b-v2:free",
        embedding=[0.4, 0.5],
        content_hash="hash_2",
        metadata={"role": "assistant"},
        db_path=db_path,
    )
    assert updated["embedding"] == [0.4, 0.5]
    assert updated["content_hash"] == "hash_2"
    assert count_embedding_records(db_path=db_path) == 1

    deleted = delete_embeddings_for_owner("conversation_message", "msg_1", db_path=db_path)
    assert deleted == 1
    assert count_embedding_records(db_path=db_path) == 0
