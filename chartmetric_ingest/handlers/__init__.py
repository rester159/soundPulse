"""Handler registry — maps handler names to response-parsing functions.

Mirrors the generality pattern from `scrapers/registry.py`: adding a
new endpoint is a registration call, not a new branch in the fetcher.

A handler's contract:
    async def my_handler(
        response_json: dict,
        handler_context: dict,
        db: AsyncSession,
    ) -> None

`response_json` is the parsed JSON body Chartmetric returned.
`handler_context` is whatever the planner stashed in the queue row —
e.g. `{"track_id": "<uuid>", "chartmetric_track_id": 12345,
"platform": "spotify"}` so the handler can write back to the right
DB row without re-deriving it.
`db` is a fresh session; the handler is responsible for its own commit.

The fetcher swallows handler exceptions, marks the job failed, and
moves on. Handlers should be idempotent — the queue will retry on
transient failures (network, deadlock) and dedup-by-pending on
planner re-emits.

Self-bootstrapping: the imports at the bottom of this file trigger
the @register side-effect in every implementation module. Adding a
new handler = adding one import line here + writing the impl file.
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

HandlerFn = Callable[[dict[str, Any], dict[str, Any], AsyncSession], Awaitable[None]]

_HANDLERS: dict[str, HandlerFn] = {}


def register(name: str) -> Callable[[HandlerFn], HandlerFn]:
    """Decorator to register a handler under the given name."""
    def decorator(fn: HandlerFn) -> HandlerFn:
        if name in _HANDLERS:
            raise RuntimeError(
                f"chartmetric_ingest handler {name!r} already registered"
            )
        _HANDLERS[name] = fn
        return fn
    return decorator


def get(name: str) -> HandlerFn | None:
    return _HANDLERS.get(name)


def all_handlers() -> list[str]:
    return sorted(_HANDLERS.keys())


def clear_for_tests() -> None:
    """Test-only: reset the registry between tests."""
    _HANDLERS.clear()


# ---- self-bootstrapping implementations ----
# Each import below triggers @register for one handler. Order doesn't
# matter — the registry is a plain dict keyed on name.
from chartmetric_ingest.handlers import track_history  # noqa: F401,E402
from chartmetric_ingest.handlers import artist_stats   # noqa: F401,E402
