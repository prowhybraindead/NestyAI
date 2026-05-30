from __future__ import annotations

from types import SimpleNamespace

from app.core.multi_model_orchestrator import should_use_orchestration


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


def _config(max_calls: int, threshold: int = 2):
    return SimpleNamespace(
        nesty_pro_orchestration_enabled=True,
        nesty_pro_orchestration_max_internal_calls=max_calls,
        nesty_pro_orchestration_complexity_min_score=threshold,
        nesty_pro_orchestration_simple_max_chars=220,
    )


def test_moderate_complexity_uses_reduced_flow() -> None:
    request = SimpleNamespace(orchestration="auto", stream=False)
    context = {"latest_user_message": "Analyze this architecture quickly"}
    decision = should_use_orchestration(
        "nesty-pro-1.0",
        request,
        _model_config(),
        context,
        _config(max_calls=4, threshold=2),
    )
    assert decision["should_use"] is True
    assert decision["roles"] == ["planner", "finalizer"]


def test_high_complexity_uses_full_flow_when_budget_allows() -> None:
    request = SimpleNamespace(orchestration="auto", stream=False)
    context = {
        "latest_user_message": "Analyze compare debug design architecture plan research verify and optimize this system",
        "search_enabled": True,
        "tools_used_count": 2,
        "sources_count": 2,
        "conversation_summary_used": True,
    }
    decision = should_use_orchestration(
        "nesty-pro-1.0",
        request,
        _model_config(),
        context,
        _config(max_calls=4, threshold=2),
    )
    assert decision["should_use"] is True
    assert decision["roles"] == ["planner", "researcher", "critic", "finalizer"]


def test_max_internal_calls_two_limits_roles_to_reduced_flow() -> None:
    request = SimpleNamespace(orchestration="force", stream=False)
    context = {"latest_user_message": "very complex and long debug architecture research question"}
    decision = should_use_orchestration(
        "nesty-pro-1.0",
        request,
        _model_config(),
        context,
        _config(max_calls=2, threshold=2),
    )
    assert decision["should_use"] is True
    assert decision["roles"] == ["planner", "finalizer"]
