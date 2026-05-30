from __future__ import annotations

import json
from collections.abc import AsyncIterator
from dataclasses import dataclass

import pytest

from app.config import ModelProfile, ModelsConfig, OrchestrationRoleConfig, ProviderTarget, Settings
from app.core.orchestrator import ChatOrchestrator
from app.guards.context_guard import ContextGuard
from app.guards.input_guard import InputGuard
from app.guards.output_guard import OutputGuard
from app.schemas.chat import ChatCompletionRequest, ChatMessage
from app.schemas.provider import ProviderChatResult, ProviderStreamChunk, ProviderUsage
from app.tools.registry import ToolRegistry
from app.utils.logging import get_logger


@dataclass
class _RouteResult:
    provider_result: ProviderChatResult
    provider_used: str


@dataclass
class _StreamRouteResult:
    provider_used: str
    stream: AsyncIterator[ProviderStreamChunk]


class _ModeRouter:
    def __init__(self) -> None:
        self.route_chat_calls = 0
        self.generate_calls: list[str] = []

    async def route_chat(self, request_id, model_alias, messages, temperature, max_tokens):
        self.route_chat_calls += 1
        return _RouteResult(
            provider_result=ProviderChatResult(provider="single", content="single answer", usage=ProviderUsage(total_tokens=3)),
            provider_used="single",
        )

    async def route_chat_stream(self, request_id, model_alias, messages, temperature, max_tokens):
        async def _stream():
            yield ProviderStreamChunk(delta="hello")
            yield ProviderStreamChunk(finish_reason="stop", usage=ProviderUsage(total_tokens=2))

        return _StreamRouteResult(provider_used="single-stream", stream=_stream())

    async def generate_with_provider_chain(
        self,
        request_id,
        provider_chain,
        messages,
        temperature,
        max_tokens,
        trace_label="custom_chain",
    ):
        self.generate_calls.append(trace_label)
        role = trace_label.split(":")[-1]
        return _RouteResult(
            provider_result=ProviderChatResult(
                provider="internal",
                content=f"{role} answer",
                usage=ProviderUsage(prompt_tokens=1, completion_tokens=1, total_tokens=2),
            ),
            provider_used="internal",
        )


def _models_config() -> ModelsConfig:
    roles = {
        "planner": OrchestrationRoleConfig(provider_chain=[ProviderTarget(provider="dummy", model="planner-model")]),
        "researcher": OrchestrationRoleConfig(
            provider_chain=[ProviderTarget(provider="dummy", model="researcher-model")]
        ),
        "critic": OrchestrationRoleConfig(provider_chain=[ProviderTarget(provider="dummy", model="critic-model")]),
        "finalizer": OrchestrationRoleConfig(provider_chain=[ProviderTarget(provider="dummy", model="finalizer-model")]),
    }
    return ModelsConfig(
        models={
            "nesty-pro-1.0": ModelProfile(
                display_name="Nesty Pro 1.0",
                description="pro test",
                strategy="quality",
                search_mode="off",
                behavior_profile="pro",
                response_style="detailed",
                reasoning_depth="high",
                search_aggressiveness="high_when_needed",
                tool_aggressiveness="high_when_needed",
                orchestration_enabled=True,
                orchestration_mode="multi_model_synthesis",
                default_temperature=0.5,
                default_max_tokens=4096,
                max_tool_calls=0,
                max_search_results=0,
                max_context_chars=4000,
                provider_chain=[ProviderTarget(provider="dummy", model="base-model")],
                orchestration_roles=roles,
            ),
            "nesty-combined-1.0": ModelProfile(
                display_name="Nesty Combined 1.0",
                description="combined test",
                strategy="balanced",
                search_mode="off",
                orchestration_enabled=False,
                max_tool_calls=0,
                max_search_results=0,
                max_context_chars=4000,
                provider_chain=[ProviderTarget(provider="dummy", model="base-model")],
            ),
        }
    )


def _build_orchestrator(router: _ModeRouter) -> ChatOrchestrator:
    settings = Settings(
        nesty_pro_orchestration_enabled=True,
        nesty_pro_orchestration_max_internal_calls=4,
        nesty_pro_orchestration_complexity_min_score=2,
        nesty_pro_orchestration_role_timeout_seconds=30,
        nesty_pro_orchestration_include_role_latency=True,
        rate_limit_enabled=False,
    )
    return ChatOrchestrator(
        router=router,
        input_guard=InputGuard(),
        output_guard=OutputGuard(),
        context_guard=ContextGuard(),
        models_config=_models_config(),
        tool_registry=ToolRegistry(),
        guard_rules={"tools": {"search_timeout_seconds": 3}, "tool_context": {"max_chars": 4000}},
        settings=settings,
        enable_input_guard=True,
        enable_output_guard=True,
        logger=get_logger("test.orchestration.modes"),
    )


def _extract_stream_metadata_payload(raw_sse: str) -> dict:
    for line in raw_sse.splitlines():
        if not line.startswith("data: "):
            continue
        data = line[len("data: ") :].strip()
        if data == "[DONE]":
            continue
        payload = json.loads(data)
        if payload.get("object") == "chat.completion.metadata":
            return payload
    return {}


def test_orchestration_default_mode_is_auto() -> None:
    req = ChatCompletionRequest(
        model="nesty-pro-1.0",
        messages=[ChatMessage(role="user", content="hello")],
    )
    assert req.orchestration == "auto"


def test_invalid_orchestration_mode_returns_error(client, monkeypatch) -> None:
    router = _ModeRouter()
    orchestrator = _build_orchestrator(router)
    settings = Settings(require_api_key=False, rate_limit_enabled=False)
    monkeypatch.setattr("app.api.chat.get_orchestrator", lambda: orchestrator)
    monkeypatch.setattr("app.api.chat.get_settings", lambda: settings)

    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "nesty-pro-1.0",
            "messages": [{"role": "user", "content": "hello"}],
            "orchestration": "weird",
            "search": "off",
            "tools": "off",
        },
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_orchestration_mode"


@pytest.mark.asyncio
async def test_non_pro_model_ignores_orchestration_force() -> None:
    router = _ModeRouter()
    orchestrator = _build_orchestrator(router)
    request = ChatCompletionRequest(
        model="nesty-combined-1.0",
        messages=[ChatMessage(role="user", content="quick answer")],
        orchestration="force",
        search="off",
        tools="off",
    )
    response = await orchestrator.create_chat_completion("req_non_pro", request)
    assert response.orchestration is not None
    assert response.orchestration.enabled is False
    assert response.orchestration.used is False
    assert response.orchestration.decision_reason == "not_pro_model"
    assert router.generate_calls == []


@pytest.mark.asyncio
async def test_nesty_pro_off_uses_single_provider_path() -> None:
    router = _ModeRouter()
    orchestrator = _build_orchestrator(router)
    request = ChatCompletionRequest(
        model="nesty-pro-1.0",
        messages=[ChatMessage(role="user", content="analyze architecture and compare options")],
        orchestration="off",
        search="off",
        tools="off",
    )
    response = await orchestrator.create_chat_completion("req_off", request)
    assert response.orchestration is not None
    assert response.orchestration.used is False
    assert response.orchestration.decision_reason == "request_off"
    assert router.route_chat_calls == 1
    assert router.generate_calls == []


@pytest.mark.asyncio
async def test_nesty_pro_force_non_stream_uses_orchestration() -> None:
    router = _ModeRouter()
    orchestrator = _build_orchestrator(router)
    request = ChatCompletionRequest(
        model="nesty-pro-1.0",
        messages=[ChatMessage(role="user", content="quick answer")],
        orchestration="force",
        search="off",
        tools="off",
    )
    response = await orchestrator.create_chat_completion("req_force", request)
    assert response.orchestration is not None
    assert response.orchestration.used is True
    assert response.orchestration.requested == "force"
    assert response.orchestration.decision_reason == "request_force"
    assert len(router.generate_calls) >= 2


def test_nesty_pro_stream_force_skips_multi_model(client, monkeypatch) -> None:
    router = _ModeRouter()
    orchestrator = _build_orchestrator(router)
    settings = Settings(require_api_key=False, rate_limit_enabled=False)
    monkeypatch.setattr("app.api.chat.get_orchestrator", lambda: orchestrator)
    monkeypatch.setattr("app.api.chat.get_settings", lambda: settings)

    with client.stream(
        "POST",
        "/v1/chat/completions",
        json={
            "model": "nesty-pro-1.0",
            "messages": [{"role": "user", "content": "analyze deeply"}],
            "orchestration": "force",
            "stream": True,
            "search": "off",
            "tools": "off",
        },
    ) as response:
        payload = "".join(response.iter_text())
    metadata = _extract_stream_metadata_payload(payload)
    assert response.status_code == 200
    assert metadata["orchestration"]["used"] is False
    assert metadata["orchestration"]["decision_reason"] == "streaming_not_supported"
    assert router.generate_calls == []
