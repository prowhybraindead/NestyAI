from __future__ import annotations

import asyncio
import re
import time
from typing import Any

from app.config import Settings
from app.core.errors import APIError, MissingAPIKeyError, ProviderError
from app.core.model_config_loader import get_effective_model_config, list_effective_model_configs
from app.providers.base import BaseProvider
from app.providers.groq import GroqProvider
from app.providers.nvidia import NvidiaProvider
from app.providers.openrouter import OpenRouterProvider
from app.schemas.chat import ChatMessage
from app.storage.provider_health import record_provider_health_check


def get_settings() -> Settings:
    from app.deps import get_settings as deps_get_settings

    return deps_get_settings()


def build_test_messages(message: str | None = None) -> list[dict]:
    user_message = str(message or "Reply with exactly: OK").strip() or "Reply with exactly: OK"
    return [
        {
            "role": "system",
            "content": (
                "This is a provider diagnostics test. "
                "Return only a short direct answer. "
                "Do not include secrets."
            ),
        },
        {
            "role": "user",
            "content": user_message,
        },
    ]


def extract_configured_provider_targets(
    model_alias: str,
    model_config: dict,
    include_roles: bool = True,
) -> list[dict]:
    alias = str(model_alias or "").strip()
    if not alias:
        return []
    targets: list[dict] = []

    def _append_targets(chain: Any, role: str) -> None:
        if not isinstance(chain, list):
            return
        for index, item in enumerate(chain):
            if not isinstance(item, dict):
                continue
            provider = str(item.get("provider") or "").strip()
            model = str(item.get("model") or "").strip()
            if not provider or not model:
                continue
            targets.append(
                {
                    "model_alias": alias,
                    "role": role,
                    "provider": provider,
                    "model": model,
                    "order": index,
                }
            )

    _append_targets(model_config.get("provider_chain"), role="main")
    if include_roles:
        roles = model_config.get("orchestration_roles")
        if isinstance(roles, dict):
            for role_name, role_config in roles.items():
                if not isinstance(role_config, dict):
                    continue
                _append_targets(role_config.get("provider_chain"), role=str(role_name).strip() or "role")

    deduped: list[dict] = []
    seen: set[tuple[str, str, str, str]] = set()
    for item in targets:
        key = (
            str(item["model_alias"]),
            str(item["role"]),
            str(item["provider"]),
            str(item["model"]),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _build_providers(settings: Settings, timeout_seconds: float) -> dict[str, BaseProvider]:
    return {
        "groq": GroqProvider(api_key=settings.groq_api_key, timeout_seconds=timeout_seconds),
        "openrouter": OpenRouterProvider(api_key=settings.openrouter_api_key, timeout_seconds=timeout_seconds),
        "nvidia": NvidiaProvider(
            api_key=settings.nvidia_api_key,
            timeout_seconds=timeout_seconds,
            base_url=settings.nvidia_base_url,
        ),
    }


def _sanitize_output_preview(text: str, max_chars: int) -> str:
    cleaned = " ".join(str(text or "").replace("\r", " ").replace("\n", " ").split()).strip()
    cleaned = re.sub(r"(?i)\b(bearer\s+[a-z0-9_\-\.]+)\b", "[REDACTED_SECRET]", cleaned)
    cleaned = re.sub(r"(?i)\b(sk-[a-z0-9_\-]{8,})\b", "[REDACTED_SECRET]", cleaned)
    if len(cleaned) > max_chars:
        return cleaned[:max_chars].rstrip() + "..."
    return cleaned


def _estimate_tokens_per_second(completion_tokens: int, latency_ms: int, output_chars: int) -> float | None:
    if latency_ms <= 0:
        return None
    seconds = latency_ms / 1000.0
    if completion_tokens > 0:
        return completion_tokens / seconds
    if output_chars <= 0:
        return None
    approx_tokens = max(1.0, output_chars / 4.0)
    return approx_tokens / seconds


def _build_status_summary(results: list[dict[str, Any]]) -> dict[str, Any]:
    counts = {
        "ok": 0,
        "failed": 0,
        "skipped": 0,
        "unavailable": 0,
        "timeout": 0,
    }
    for row in results:
        status = str(row.get("status") or "failed")
        if status not in counts:
            status = "failed"
        counts[status] += 1
    return {
        "total": len(results),
        "ok": counts["ok"],
        "failed": counts["failed"] + counts["timeout"] + counts["unavailable"],
        "status_counts": counts,
    }


async def diagnose_provider_model(
    provider: str,
    model: str,
    message: str | None = None,
    *,
    model_alias: str | None = None,
    role: str | None = None,
    order: int | None = None,
    dry_run: bool = False,
) -> dict:
    settings = get_settings()
    provider_name = str(provider or "").strip().lower()
    model_name = str(model or "").strip()
    if not provider_name or not model_name:
        raise APIError(
            code="invalid_diagnostic_request",
            message="Provider and model are required.",
            status_code=400,
        )

    timeout_seconds = max(1.0, float(getattr(settings, "diagnostics_default_timeout_seconds", 20.0)))
    max_tokens = max(1, int(getattr(settings, "diagnostics_test_max_tokens", 16)))
    preview_chars = max(20, int(getattr(settings, "diagnostics_output_preview_chars", 80)))
    providers = _build_providers(settings, timeout_seconds=timeout_seconds)
    provider_client = providers.get(provider_name)
    checked_at = time.time()

    result: dict[str, Any] = {
        "model_alias": str(model_alias or "").strip() or None,
        "role": str(role or "").strip() or None,
        "order": int(order) if order is not None else None,
        "provider": provider_name,
        "model": model_name,
        "status": "failed",
        "error_code": None,
        "error_message": None,
        "latency_ms": None,
        "output_chars": 0,
        "tokens_per_second": None,
        "checked_at": checked_at,
        "metadata": {},
    }
    if provider_client is None:
        result.update({"status": "unavailable", "error_code": "provider_unavailable"})
    else:
        messages = [ChatMessage.model_validate(item) for item in build_test_messages(message)]
        started = time.perf_counter()
        try:
            provider_result = await asyncio.wait_for(
                provider_client.generate_chat_completion(
                    messages=messages,
                    model=model_name,
                    temperature=0.0,
                    max_tokens=max_tokens,
                ),
                timeout=timeout_seconds,
            )
            latency_ms = int((time.perf_counter() - started) * 1000)
            output_text = str(provider_result.content or "")
            output_chars = len(output_text)
            completion_tokens = int(getattr(provider_result.usage, "completion_tokens", 0) or 0)
            tokens_per_second = _estimate_tokens_per_second(
                completion_tokens=completion_tokens,
                latency_ms=latency_ms,
                output_chars=output_chars,
            )
            result.update(
                {
                    "status": "ok",
                    "latency_ms": latency_ms,
                    "output_chars": output_chars,
                    "tokens_per_second": tokens_per_second,
                    "metadata": {
                        "output_preview": _sanitize_output_preview(output_text, preview_chars),
                        "completion_tokens": completion_tokens,
                    },
                }
            )
        except asyncio.TimeoutError:
            result.update({"status": "timeout", "error_code": "provider_timeout"})
        except MissingAPIKeyError:
            result.update({"status": "unavailable", "error_code": "missing_api_key"})
        except ProviderError as exc:
            message_text = str(exc.message or "").lower()
            if "timed out" in message_text:
                status = "timeout"
                error_code = "provider_timeout"
            elif "missing api key" in message_text:
                status = "unavailable"
                error_code = "missing_api_key"
            elif exc.retryable:
                status = "unavailable"
                error_code = "provider_unavailable"
            else:
                status = "failed"
                error_code = "provider_diagnostic_failed"
            result.update({"status": status, "error_code": error_code})
        except Exception:
            result.update({"status": "failed", "error_code": "provider_diagnostic_failed"})

    should_save = bool(getattr(settings, "diagnostics_save_results", True)) and not dry_run
    if should_save:
        _ = record_provider_health_check(
            provider=result["provider"],
            model=result["model"],
            model_alias=result.get("model_alias"),
            role=result.get("role"),
            status=result["status"],
            error_code=result.get("error_code"),
            error_message=None,
            latency_ms=result.get("latency_ms"),
            output_chars=int(result.get("output_chars") or 0),
            tokens_per_second=result.get("tokens_per_second"),
            metadata=result.get("metadata") if isinstance(result.get("metadata"), dict) else None,
        )
    return result


async def diagnose_model_alias(
    model_alias: str,
    include_roles: bool = True,
    *,
    message: str | None = None,
    dry_run: bool = False,
) -> dict:
    effective = get_effective_model_config(model_alias)
    if not isinstance(effective, dict):
        raise APIError(
            code="invalid_diagnostic_request",
            message="Model alias is not configured.",
            status_code=404,
        )
    targets = extract_configured_provider_targets(
        model_alias=model_alias,
        model_config=effective,
        include_roles=include_roles,
    )
    results: list[dict[str, Any]] = []
    for item in targets:
        checked = await diagnose_provider_model(
            provider=str(item.get("provider") or ""),
            model=str(item.get("model") or ""),
            message=message,
            model_alias=str(item.get("model_alias") or model_alias),
            role=str(item.get("role") or "main"),
            order=int(item.get("order") or 0),
            dry_run=dry_run,
        )
        results.append(checked)
    return {
        "model_alias": model_alias,
        "include_roles": bool(include_roles),
        "targets_count": len(targets),
        "results": results,
        "summary": _build_status_summary(results),
    }


async def diagnose_all_model_aliases(
    *,
    message: str | None = None,
    include_roles: bool = True,
    dry_run: bool = False,
) -> dict:
    rows = list_effective_model_configs()
    items: list[dict[str, Any]] = []
    all_results: list[dict[str, Any]] = []
    for row in rows:
        model_alias = str(row.get("model_id") or "").strip()
        if not model_alias:
            continue
        result = await diagnose_model_alias(
            model_alias=model_alias,
            include_roles=include_roles,
            message=message,
            dry_run=dry_run,
        )
        items.append(result)
        all_results.extend(list(result.get("results") or []))
    return {
        "model_aliases_checked": len(items),
        "items": items,
        "summary": _build_status_summary(all_results),
    }
