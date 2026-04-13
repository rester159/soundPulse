"""
LLM client with provider abstraction and call logging.

Generality principle: NO caller should hardcode a provider name, model ID,
or API URL. Every LLM call goes through this module, which reads
config/llm.json to resolve (action → model_spec → provider_spec) and
makes the actual HTTP call. The same code path works for Groq, OpenAI,
Anthropic, and any future OpenAI-compatible provider — add a new entry
to llm.json and you're done.

CLAUDE.md mandate: every LLM call logs model, tokens, cost, timestamp,
action type. This module writes one row to `llm_calls` per call,
success or failure. That row captures everything needed for a usage
dashboard / cost audit / debugging later.

Usage
-----
    from api.services.llm_client import llm_chat

    result = await llm_chat(
        db=db,
        action="assistant_chat",    # looks up config/llm.json actions table
        messages=[
            {"role": "system", "content": "..."},
            {"role": "user", "content": "..."},
        ],
        context_id=str(request_id),
        caller="assistant_service.ask_assistant",
    )
    if result["success"]:
        answer = result["content"]

Response shape:
    {
      "success": bool,
      "content": str,
      "model": str,
      "provider": str,
      "input_tokens": int,
      "output_tokens": int,
      "total_tokens": int,
      "cost_cents": int,
      "latency_ms": int,
      "error": str | None,
    }
"""

from __future__ import annotations

import json
import logging
import os
import uuid as uuid_mod
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.llm_call import LlmCall

logger = logging.getLogger(__name__)


_CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "llm.json"


@lru_cache(maxsize=1)
def _load_config() -> dict[str, Any]:
    """Load config/llm.json once per process."""
    with open(_CONFIG_PATH) as f:
        return json.load(f)


def reload_config() -> None:
    """Invalidate the config cache (for admin PUT to llm config)."""
    _load_config.cache_clear()


def _resolve_action(action: str) -> dict[str, Any]:
    """
    action name → model_spec dict merged with provider_spec.

    Returns a dict like:
        {
            "provider": "groq",
            "model": "llama-3.3-70b-versatile",
            "api_url": "https://api.groq.com/...",
            "api_key": "<loaded from env>",
            "format": "openai_compat",
            "temperature": 0.3,
            "max_tokens": 1024,
            "price_per_million_input_usd": 0.59,
            "price_per_million_output_usd": 0.79,
        }

    Raises KeyError if action or provider is missing from config.
    """
    cfg = _load_config()
    model_name = cfg["actions"].get(action)
    if not model_name:
        raise KeyError(f"LLM action '{action}' not found in config/llm.json")
    model_spec = cfg["models"].get(model_name)
    if not model_spec:
        raise KeyError(f"LLM model '{model_name}' not found in config/llm.json")
    provider_name = model_spec["provider"]
    provider_spec = cfg["providers"].get(provider_name)
    if not provider_spec:
        raise KeyError(f"LLM provider '{provider_name}' not found in config/llm.json")

    api_key = os.environ.get(provider_spec["api_key_env"], "")
    return {
        **provider_spec,
        **model_spec,
        "provider": provider_name,
        "api_key": api_key,
    }


def _estimate_cost_cents(
    input_tokens: int, output_tokens: int, spec: dict[str, Any]
) -> int:
    """Convert (in, out) tokens to estimated cost in USD cents."""
    input_price = float(spec.get("price_per_million_input_usd") or 0)
    output_price = float(spec.get("price_per_million_output_usd") or 0)
    cost_usd = (input_tokens / 1_000_000) * input_price + (output_tokens / 1_000_000) * output_price
    return int(round(cost_usd * 100))


async def llm_chat(
    *,
    db: AsyncSession | None,
    action: str,
    messages: list[dict[str, str]],
    caller: str | None = None,
    context_id: str | None = None,
    override_temperature: float | None = None,
    override_max_tokens: int | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Make an LLM chat-completion call and log it.

    `db` is optional — if passed, we write a row to `llm_calls`. In
    scripts / tests where no session is available, pass db=None and we
    skip the write (but still log structured info to the Python logger).
    """
    started = datetime.now(timezone.utc)

    # ----- Resolve config (may raise KeyError for missing action) -----
    try:
        spec = _resolve_action(action)
    except KeyError as exc:
        logger.error("[llm-client] config resolution failed for action=%s: %s", action, exc)
        return {
            "success": False,
            "content": "",
            "model": "",
            "provider": "",
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "cost_cents": 0,
            "latency_ms": 0,
            "error": f"LLM config error: {exc}",
        }

    model = spec["model"]
    provider = spec["provider"]
    api_url = spec["api_url"]
    api_key = spec["api_key"]
    fmt = spec.get("format", "openai_compat")
    temperature = override_temperature if override_temperature is not None else spec.get("temperature", 0.3)
    max_tokens = override_max_tokens if override_max_tokens is not None else spec.get("max_tokens", 1024)

    # ----- Missing key → fail with a logged row -----
    if not api_key:
        latency_ms = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
        err = f"API key env var {spec.get('api_key_env')} is not set"
        logger.error("[llm-client] %s", err)
        await _log_call(
            db=db, action=action, model=model, provider=provider, caller=caller,
            context_id=context_id, input_tokens=0, output_tokens=0,
            cost_cents=0, latency_ms=latency_ms,
            success=False, error=err, metadata=metadata,
        )
        return {
            "success": False, "content": "",
            "model": model, "provider": provider,
            "input_tokens": 0, "output_tokens": 0, "total_tokens": 0,
            "cost_cents": 0, "latency_ms": latency_ms,
            "error": err,
        }

    # ----- Dispatch to provider format -----
    content = ""
    input_tokens = 0
    output_tokens = 0
    error: str | None = None

    try:
        if fmt == "openai_compat":
            # Groq, OpenAI, Gemini (via OpenAI-compat shim), anything OpenAI-compatible
            body: dict[str, Any] = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            # Gemini 2.5 models spend a "thinking" budget before producing
            # content — without capping it, max_tokens gets burned on
            # reasoning and the response comes back with empty content.
            # The OpenAI-compat shim accepts reasoning_effort; "low" is
            # the sweet spot for structured creative tasks (keeps enough
            # reasoning for instruction-following but doesn't eat the
            # token budget).
            if provider == "gemini":
                body["reasoning_effort"] = "low"
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(
                    api_url,
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json=body,
                )
            if resp.status_code != 200:
                error = f"{provider} HTTP {resp.status_code}: {resp.text[:200]}"
            else:
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                usage = data.get("usage", {}) or {}
                input_tokens = int(usage.get("prompt_tokens") or 0)
                output_tokens = int(usage.get("completion_tokens") or 0)

        elif fmt == "anthropic":
            # Anthropic Messages API — slightly different shape
            # System message is a top-level field; rest are conversation.
            system_content = ""
            convo_messages: list[dict[str, str]] = []
            for m in messages:
                if m.get("role") == "system":
                    system_content += m.get("content", "") + "\n"
                else:
                    convo_messages.append(m)
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    api_url,
                    headers={
                        "x-api-key": api_key,
                        "anthropic-version": "2023-06-01",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": model,
                        "system": system_content.strip(),
                        "messages": convo_messages,
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                    },
                )
            if resp.status_code != 200:
                error = f"{provider} HTTP {resp.status_code}: {resp.text[:200]}"
            else:
                data = resp.json()
                # Anthropic returns content as a list of blocks
                blocks = data.get("content") or []
                content = "".join(
                    b.get("text", "") for b in blocks if isinstance(b, dict) and b.get("type") == "text"
                )
                usage = data.get("usage", {}) or {}
                input_tokens = int(usage.get("input_tokens") or 0)
                output_tokens = int(usage.get("output_tokens") or 0)

        else:
            error = f"unknown LLM format: {fmt}"

    except httpx.HTTPError as exc:
        error = f"network: {exc}"
    except Exception as exc:  # noqa: BLE001
        error = f"unexpected: {exc}"

    latency_ms = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
    cost_cents = _estimate_cost_cents(input_tokens, output_tokens, spec)
    success = error is None

    await _log_call(
        db=db,
        action=action,
        model=model,
        provider=provider,
        caller=caller,
        context_id=context_id,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_cents=cost_cents,
        latency_ms=latency_ms,
        success=success,
        error=error,
        metadata=metadata,
    )

    return {
        "success": success,
        "content": content,
        "model": model,
        "provider": provider,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
        "cost_cents": cost_cents,
        "latency_ms": latency_ms,
        "error": error,
    }


async def _log_call(
    *,
    db: AsyncSession | None,
    action: str,
    model: str,
    provider: str,
    caller: str | None,
    context_id: str | None,
    input_tokens: int,
    output_tokens: int,
    cost_cents: int,
    latency_ms: int,
    success: bool,
    error: str | None,
    metadata: dict[str, Any] | None,
) -> None:
    """Write one row to llm_calls. Never raises — logging failure must
    not break the caller."""
    # Always emit to the Python logger so the row shows up in Railway logs
    # even if the DB write fails.
    logger.info(
        "[llm-call] action=%s provider=%s model=%s in=%d out=%d cost_cents=%d "
        "latency_ms=%d success=%s error=%s",
        action, provider, model, input_tokens, output_tokens, cost_cents,
        latency_ms, success, (error or "")[:200],
    )

    if db is None:
        return

    try:
        row = LlmCall(
            id=uuid_mod.uuid4(),
            model=model,
            provider=provider,
            action_type=action,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            cost_cents=cost_cents,
            latency_ms=latency_ms,
            caller=caller,
            context_id=context_id,
            success=success,
            error_message=(error or "")[:2000] if error else None,
            metadata_json=metadata,
        )
        db.add(row)
        await db.commit()
    except Exception as log_exc:  # noqa: BLE001
        # Logging failure must not break the caller. Surface via stderr
        # and move on.
        logger.error("[llm-client] failed to log call: %s", log_exc)
        try:
            await db.rollback()
        except Exception:
            pass
