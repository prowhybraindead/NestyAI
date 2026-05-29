from __future__ import annotations

from pydantic import BaseModel, Field
from fastapi import APIRouter, Request

from app.core.conversation_summarizer import summarize_conversation
from app.core.errors import APIError
from app.deps import get_orchestrator, get_settings
from app.security.auth import AuthContext, optional_api_key, require_api_key
from app.storage.conversations import (
    archive_conversation,
    clear_conversation_messages,
    export_conversation,
    get_conversation_stats,
    get_conversation,
    get_recent_messages,
    list_conversations,
    reset_conversation_summary,
    update_conversation_title,
)


router = APIRouter(prefix="/v1/conversations", tags=["conversations"])


class UpdateConversationTitleRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)


class ClearConversationRequest(BaseModel):
    keep_summary: bool = False


def _resolve_auth_context(settings, request: Request) -> AuthContext | None:
    if settings.require_api_key:
        return require_api_key(request)
    return optional_api_key(request)


def _conversation_accessible(settings, conversation: dict | None, auth_context: AuthContext | None) -> bool:
    if conversation is None:
        return False
    if conversation.get("archived_at"):
        return False

    owner = conversation.get("api_key_id")
    if settings.require_api_key:
        return bool(auth_context and owner == auth_context.api_key_id)

    if owner is None:
        return True
    if auth_context is None:
        return False
    return owner == auth_context.api_key_id


@router.get("")
async def get_conversations(request: Request, limit: int = 20, offset: int = 0) -> dict:
    settings = get_settings()
    auth_context = _resolve_auth_context(settings, request)
    api_key_id = auth_context.api_key_id if auth_context else None

    items = list_conversations(
        api_key_id=api_key_id,
        limit=max(1, min(int(limit), 100)),
        offset=max(0, int(offset)),
        db_path=settings.nesty_db_path,
    )
    with_counts = []
    for item in items:
        stats = get_conversation_stats(str(item["id"]), db_path=settings.nesty_db_path)
        with_counts.append(
            {
                "id": item["id"],
                "title": item["title"],
                "created_at": item["created_at"],
                "updated_at": item["updated_at"],
                "archived_at": item.get("archived_at"),
                "message_count": int(stats.get("message_count") or 0),
                "last_message_at": stats.get("last_message_at"),
                "summary_exists": bool(item.get("summary_exists")),
                "summary_updated_at": item.get("summary_updated_at"),
                "summary_message_count": int(item.get("summary_message_count") or 0),
            }
        )
    return {"object": "list", "data": with_counts}


@router.get("/{conversation_id}")
async def get_conversation_detail(request: Request, conversation_id: str, limit: int = 20) -> dict:
    settings = get_settings()
    auth_context = _resolve_auth_context(settings, request)

    conversation = get_conversation(conversation_id, db_path=settings.nesty_db_path)
    if not _conversation_accessible(settings, conversation, auth_context):
        raise APIError(
            code="conversation_not_found",
            message="Conversation not found.",
            status_code=404,
        )

    messages = get_recent_messages(
        conversation_id=conversation_id,
        limit=max(1, min(int(limit), 200)),
        db_path=settings.nesty_db_path,
    )
    stats = get_conversation_stats(conversation_id, db_path=settings.nesty_db_path)
    return {
        "conversation": {
            "id": conversation["id"],
            "title": conversation["title"],
            "created_at": conversation["created_at"],
            "updated_at": conversation["updated_at"],
            "archived_at": conversation.get("archived_at"),
            "message_count": int(stats.get("message_count") or 0),
            "last_message_at": stats.get("last_message_at"),
            "summary_exists": bool(str(conversation.get("summary") or "").strip()),
            "summary": conversation.get("summary"),
            "summary_updated_at": conversation.get("summary_updated_at"),
            "summary_message_count": int(conversation.get("summary_message_count") or 0),
        },
        "messages": [
            {
                "id": item["id"],
                "role": item["role"],
                "content": item["content"],
                "model": item["model"],
                "provider": item["provider"],
                "created_at": item["created_at"],
            }
            for item in messages
        ],
    }


@router.delete("/{conversation_id}")
async def delete_conversation(request: Request, conversation_id: str) -> dict:
    settings = get_settings()
    auth_context = _resolve_auth_context(settings, request)
    api_key_id = auth_context.api_key_id if auth_context else None

    ok = archive_conversation(
        conversation_id=conversation_id,
        api_key_id=api_key_id,
        db_path=settings.nesty_db_path,
    )
    if not ok:
        raise APIError(
            code="conversation_not_found",
            message="Conversation not found.",
            status_code=404,
        )
    return {"ok": True}


@router.patch("/{conversation_id}")
async def patch_conversation_title(request: Request, conversation_id: str, body: UpdateConversationTitleRequest) -> dict:
    settings = get_settings()
    auth_context = _resolve_auth_context(settings, request)
    api_key_id = auth_context.api_key_id if auth_context else None

    ok = update_conversation_title(
        conversation_id=conversation_id,
        title=body.title.strip(),
        api_key_id=api_key_id,
        db_path=settings.nesty_db_path,
    )
    if not ok:
        raise APIError(
            code="conversation_not_found",
            message="Conversation not found.",
            status_code=404,
        )
    return {"ok": True}


@router.post("/{conversation_id}/summarize")
async def summarize_conversation_endpoint(request: Request, conversation_id: str) -> dict:
    settings = get_settings()
    auth_context = _resolve_auth_context(settings, request)
    conversation = get_conversation(conversation_id, db_path=settings.nesty_db_path)
    if not _conversation_accessible(settings, conversation, auth_context):
        raise APIError(
            code="conversation_not_found",
            message="Conversation not found.",
            status_code=404,
        )

    stats = get_conversation_stats(conversation_id=conversation_id, db_path=settings.nesty_db_path)
    if int(stats.get("message_count") or 0) <= 0:
        return {"ok": True, "summary_updated": False, "summary_message_count": 0}

    orchestrator = get_orchestrator()
    router = getattr(orchestrator, "router", None)
    if router is None:
        raise APIError(
            code="conversation_summary_failed",
            message="Conversation summarization failed.",
            status_code=500,
        )

    try:
        updated_summary = await summarize_conversation(
            conversation_id=conversation_id,
            router=router,
            config=settings,
            api_key_context=auth_context,
            force=True,
            raise_on_error=True,
        )
    except Exception:
        raise APIError(
            code="conversation_summary_failed",
            message="Conversation summarization failed.",
            status_code=502,
        )

    refreshed = get_conversation(conversation_id, db_path=settings.nesty_db_path) or {}
    return {
        "ok": True,
        "summary_updated": bool(updated_summary),
        "summary_message_count": int(refreshed.get("summary_message_count") or 0),
    }


@router.post("/{conversation_id}/clear")
async def clear_conversation_endpoint(request: Request, conversation_id: str, body: ClearConversationRequest) -> dict:
    settings = get_settings()
    auth_context = _resolve_auth_context(settings, request)
    api_key_id = auth_context.api_key_id if auth_context else None

    ok = clear_conversation_messages(
        conversation_id=conversation_id,
        api_key_id=api_key_id,
        keep_summary=bool(body.keep_summary),
        db_path=settings.nesty_db_path,
    )
    if not ok:
        raise APIError(
            code="conversation_not_found",
            message="Conversation not found.",
            status_code=404,
        )
    return {"ok": True}


@router.post("/{conversation_id}/reset-summary")
async def reset_summary_endpoint(request: Request, conversation_id: str) -> dict:
    settings = get_settings()
    auth_context = _resolve_auth_context(settings, request)
    api_key_id = auth_context.api_key_id if auth_context else None

    ok = reset_conversation_summary(
        conversation_id=conversation_id,
        api_key_id=api_key_id,
        db_path=settings.nesty_db_path,
    )
    if not ok:
        raise APIError(
            code="conversation_not_found",
            message="Conversation not found.",
            status_code=404,
        )
    return {"ok": True}


@router.get("/{conversation_id}/export")
async def export_conversation_endpoint(request: Request, conversation_id: str) -> dict:
    settings = get_settings()
    auth_context = _resolve_auth_context(settings, request)
    api_key_id = auth_context.api_key_id if auth_context else None

    exported = export_conversation(
        conversation_id=conversation_id,
        api_key_id=api_key_id,
        db_path=settings.nesty_db_path,
    )
    if exported is None:
        raise APIError(
            code="conversation_not_found",
            message="Conversation not found.",
            status_code=404,
        )
    return exported
