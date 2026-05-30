from __future__ import annotations

from types import SimpleNamespace

from app.core.multi_model_orchestrator import should_use_orchestration


def _config(**overrides):
    base = {
        "nesty_pro_orchestration_enabled": True,
        "nesty_pro_orchestration_max_internal_calls": 4,
        "nesty_pro_orchestration_complexity_min_score": 2,
        "nesty_pro_orchestration_simple_max_chars": 220,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _model_config():
    return {
        "orchestration_enabled": True,
        "orchestration_mode": "multi_model_synthesis",
        "orchestration_roles": {
            "planner": {"provider_chain": [{"provider": "x", "model": "a"}]},
            "researcher": {"provider_chain": [{"provider": "x", "model": "b"}]},
            "critic": {"provider_chain": [{"provider": "x", "model": "c"}]},
            "finalizer": {"provider_chain": [{"provider": "x", "model": "d"}]},
        },
    }


def test_auto_skips_simple_request() -> None:
    request = SimpleNamespace(orchestration="auto", stream=False)
    context = {"latest_user_message": "hello", "search_enabled": False, "tools_used_count": 0, "sources_count": 0}
    decision = should_use_orchestration("nesty-pro-1.0", request, _model_config(), context, _config())
    assert decision["should_use"] is False
    assert decision["reason"] == "simple_request"


def test_auto_uses_orchestration_for_complex_request() -> None:
    request = SimpleNamespace(orchestration="auto", stream=False)
    context = {
        "latest_user_message": "Please analyze and compare this architecture, debug risks, and verify assumptions",
        "search_enabled": True,
        "tools_used_count": 2,
        "sources_count": 2,
    }
    decision = should_use_orchestration("nesty-pro-1.0", request, _model_config(), context, _config())
    assert decision["should_use"] is True
    assert decision["reason"] == "complex_request"
    assert decision["complexity_score"] >= 2


def test_max_internal_calls_below_two_disables_orchestration() -> None:
    request = SimpleNamespace(orchestration="force", stream=False)
    context = {"latest_user_message": "analyze deeply"}
    decision = should_use_orchestration(
        "nesty-pro-1.0",
        request,
        _model_config(),
        context,
        _config(nesty_pro_orchestration_max_internal_calls=1),
    )
    assert decision["should_use"] is False
    assert decision["reason"] == "internal_call_limit_too_low"
