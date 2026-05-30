from __future__ import annotations

from app.core.model_config_loader import get_effective_model_config
from app.core.provider_diagnostics import extract_configured_provider_targets
from app.storage.db import init_db
from app.storage.model_configs import upsert_model_override


def test_extract_provider_targets_includes_main_chain() -> None:
    targets = extract_configured_provider_targets(
        model_alias="nesty-flash-1.0",
        model_config={
            "provider_chain": [
                {"provider": "groq", "model": "llama-3.1-8b-instant"},
                {"provider": "openrouter", "model": "deepseek/deepseek-v4-flash:free"},
            ]
        },
        include_roles=False,
    )
    assert len(targets) == 2
    assert targets[0]["role"] == "main"
    assert targets[0]["provider"] == "groq"


def test_extract_provider_targets_includes_orchestration_roles_when_enabled() -> None:
    targets = extract_configured_provider_targets(
        model_alias="nesty-pro-1.0",
        model_config={
            "provider_chain": [{"provider": "openrouter", "model": "deepseek/deepseek-v4-flash:free"}],
            "orchestration_roles": {
                "planner": {"provider_chain": [{"provider": "groq", "model": "llama-3.1-8b-instant"}]},
                "researcher": {"provider_chain": [{"provider": "openrouter", "model": "moonshotai/kimi-k2.6:free"}]},
            },
        },
        include_roles=True,
    )
    roles = {(item["role"], item["provider"]) for item in targets}
    assert ("main", "openrouter") in roles
    assert ("planner", "groq") in roles
    assert ("researcher", "openrouter") in roles


def test_extract_provider_targets_deduplicates_exact_duplicates() -> None:
    targets = extract_configured_provider_targets(
        model_alias="nesty-combined-1.0",
        model_config={
            "provider_chain": [
                {"provider": "openrouter", "model": "deepseek/deepseek-v4-flash:free"},
                {"provider": "openrouter", "model": "deepseek/deepseek-v4-flash:free"},
            ]
        },
        include_roles=False,
    )
    assert len(targets) == 1


def test_extract_provider_targets_uses_runtime_override_provider_chain(monkeypatch, tmp_path) -> None:
    db_path = str(tmp_path / "provider_targets_runtime_override.db")
    init_db(db_path)
    monkeypatch.setattr("app.storage.model_configs.get_settings", lambda: type("S", (), {"nesty_db_path": db_path})())
    upsert_model_override(
        model_id="nesty-flash-1.0",
        config={"provider_chain": [{"provider": "openrouter", "model": "runtime-test-model"}]},
        db_path=db_path,
    )
    effective = get_effective_model_config("nesty-flash-1.0")
    assert effective is not None
    targets = extract_configured_provider_targets(
        model_alias="nesty-flash-1.0",
        model_config=effective,
        include_roles=False,
    )
    assert targets
    assert targets[0]["provider"] == "openrouter"
    assert targets[0]["model"] == "runtime-test-model"
