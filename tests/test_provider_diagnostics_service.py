from __future__ import annotations

import pytest

from app.core.errors import MissingAPIKeyError, ProviderError
from app.core.provider_diagnostics import (
    build_test_messages,
    diagnose_all_model_aliases,
    diagnose_model_alias,
    diagnose_provider_model,
)
from app.schemas.provider import ProviderChatResult, ProviderUsage


class _OkProvider:
    provider_name = "openrouter"

    async def generate_chat_completion(self, messages, model, temperature, max_tokens):
        return ProviderChatResult(
            provider="openrouter",
            content="OK",
            usage=ProviderUsage(prompt_tokens=1, completion_tokens=1, total_tokens=2),
        )


class _MissingKeyProvider:
    provider_name = "openrouter"

    async def generate_chat_completion(self, messages, model, temperature, max_tokens):
        raise MissingAPIKeyError("openrouter")


class _FailProvider:
    provider_name = "openrouter"

    async def generate_chat_completion(self, messages, model, temperature, max_tokens):
        raise ProviderError(provider="openrouter", message="Provider rejected request.", retryable=False, status_code=400)


class _SecretProvider:
    provider_name = "openrouter"

    async def generate_chat_completion(self, messages, model, temperature, max_tokens):
        return ProviderChatResult(
            provider="openrouter",
            content="Bearer secret_token sk-abcdef1234567890",
            usage=ProviderUsage(prompt_tokens=1, completion_tokens=4, total_tokens=5),
        )


def _settings():
    return type(
        "S",
        (),
        {
            "diagnostics_default_timeout_seconds": 10.0,
            "diagnostics_test_max_tokens": 16,
            "diagnostics_output_preview_chars": 80,
            "diagnostics_save_results": False,
            "groq_api_key": "",
            "openrouter_api_key": "",
            "nvidia_api_key": "",
            "nvidia_base_url": "",
        },
    )()


def test_build_test_messages_small_safe_prompt() -> None:
    msgs = build_test_messages()
    assert len(msgs) == 2
    assert msgs[1]["content"] == "Reply with exactly: OK"


@pytest.mark.asyncio
async def test_diagnose_provider_model_ok(monkeypatch) -> None:
    monkeypatch.setattr("app.core.provider_diagnostics.get_settings", _settings)
    monkeypatch.setattr(
        "app.core.provider_diagnostics._build_providers",
        lambda settings, timeout_seconds: {"openrouter": _OkProvider()},
    )
    result = await diagnose_provider_model(provider="openrouter", model="test-model", dry_run=True)
    assert result["status"] == "ok"
    assert result["latency_ms"] is not None
    assert result["output_chars"] == 2
    assert result["error_code"] is None


@pytest.mark.asyncio
async def test_diagnose_provider_model_missing_key_maps_unavailable(monkeypatch) -> None:
    monkeypatch.setattr("app.core.provider_diagnostics.get_settings", _settings)
    monkeypatch.setattr(
        "app.core.provider_diagnostics._build_providers",
        lambda settings, timeout_seconds: {"openrouter": _MissingKeyProvider()},
    )
    result = await diagnose_provider_model(provider="openrouter", model="test-model", dry_run=True)
    assert result["status"] == "unavailable"
    assert result["error_code"] == "missing_api_key"


@pytest.mark.asyncio
async def test_diagnose_provider_model_failure_maps_failed(monkeypatch) -> None:
    monkeypatch.setattr("app.core.provider_diagnostics.get_settings", _settings)
    monkeypatch.setattr(
        "app.core.provider_diagnostics._build_providers",
        lambda settings, timeout_seconds: {"openrouter": _FailProvider()},
    )
    result = await diagnose_provider_model(provider="openrouter", model="test-model", dry_run=True)
    assert result["status"] == "failed"
    assert result["error_code"] == "provider_diagnostic_failed"


@pytest.mark.asyncio
async def test_diagnose_provider_model_redacts_sensitive_preview(monkeypatch) -> None:
    monkeypatch.setattr("app.core.provider_diagnostics.get_settings", _settings)
    monkeypatch.setattr(
        "app.core.provider_diagnostics._build_providers",
        lambda settings, timeout_seconds: {"openrouter": _SecretProvider()},
    )
    result = await diagnose_provider_model(provider="openrouter", model="test-model", dry_run=True)
    preview = str((result.get("metadata") or {}).get("output_preview") or "")
    assert result["status"] == "ok"
    assert "Bearer" not in preview
    assert "sk-" not in preview


@pytest.mark.asyncio
async def test_diagnose_model_alias_uses_targets(monkeypatch) -> None:
    monkeypatch.setattr("app.core.provider_diagnostics.get_settings", _settings)
    monkeypatch.setattr(
        "app.core.provider_diagnostics.get_effective_model_config",
        lambda model_alias: {
            "provider_chain": [{"provider": "openrouter", "model": "m1"}],
            "orchestration_roles": {"planner": {"provider_chain": [{"provider": "groq", "model": "m2"}]}},
        },
    )

    async def _fake_diag(provider, model, message=None, **kwargs):
        return {
            "provider": provider,
            "model": model,
            "model_alias": kwargs.get("model_alias"),
            "role": kwargs.get("role"),
            "status": "ok",
            "error_code": None,
        }

    monkeypatch.setattr("app.core.provider_diagnostics.diagnose_provider_model", _fake_diag)
    result = await diagnose_model_alias("nesty-pro-1.0", include_roles=True, dry_run=True)
    assert result["targets_count"] == 2
    assert result["summary"]["ok"] == 2


@pytest.mark.asyncio
async def test_diagnose_all_model_aliases(monkeypatch) -> None:
    monkeypatch.setattr("app.core.provider_diagnostics.get_settings", _settings)
    monkeypatch.setattr(
        "app.core.provider_diagnostics.list_effective_model_configs",
        lambda: [
            {"model_id": "nesty-flash-1.0"},
            {"model_id": "nesty-combined-1.0"},
        ],
    )

    async def _fake_diag_alias(model_alias, include_roles=True, message=None, dry_run=False):
        return {
            "model_alias": model_alias,
            "results": [{"status": "ok"}],
            "summary": {"total": 1, "ok": 1, "failed": 0, "status_counts": {"ok": 1, "failed": 0}},
        }

    monkeypatch.setattr("app.core.provider_diagnostics.diagnose_model_alias", _fake_diag_alias)
    result = await diagnose_all_model_aliases(dry_run=True)
    assert result["model_aliases_checked"] == 2
    assert result["summary"]["ok"] == 2
