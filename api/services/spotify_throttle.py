"""
Shared Spotify rate-limit governor.

Background: on 2026-04-11 the `backfill-spotify-ids` endpoint burst
through ~2,500 Spotify /v1/search calls in a few minutes. Spotify
responded with a 429 carrying `Retry-After: 45001` — a 12.5-hour
cooldown. Every Spotify caller in the codebase (the backfill endpoint,
the spotify scraper, the spotify_audio scraper) now routes through
this module so that:

  1. A process-wide semaphore caps in-flight Spotify requests to 3,
     smoothing bursts from multiple callers hitting Spotify at once.
  2. A process-wide cooldown timestamp blocks ALL Spotify calls after
     a 429 until the Retry-After window expires. Callers get
     `SpotifyCooldownActive` immediately instead of hammering a
     throttled API.
  3. The default per-call delay is 0.5s (2 req/s), well under
     Spotify's ~10-20 req/s soft limit.
  4. Retry-After values are capped at 600 seconds to prevent single
     runaway responses from pinning us for hours — if the real cooldown
     is longer, the next attempt will set it again.

This module is intentionally stateless outside of two module-level
variables. It does not persist cooldown state across process restarts;
that's acceptable because a deploy is effectively a "maybe Spotify has
calmed down by now, try once" signal.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# Hard ceiling on concurrent Spotify requests across all callers in
# this process. Spotify's soft limit applies per-app, not per-connection,
# so even 3 concurrent callers can trigger rate limits if they're fast.
_SEMAPHORE = asyncio.Semaphore(3)

# Unix timestamp before which all Spotify calls are refused. Set by
# record_rate_limit() when Spotify returns 429.
_COOLDOWN_UNTIL: float = 0.0

# Cap on Retry-After values we'll honor. If Spotify says "wait 12 hours",
# we record 10 minutes and let the next attempt refresh the cooldown.
# Without this cap a single bad response can hang the entire ingestion
# pipeline for hours.
MAX_COOLDOWN_SECONDS = 600

# Default inter-request delay inside the semaphore. Callers that need
# to be even slower can pass a larger value via `delay=`.
DEFAULT_REQUEST_DELAY = 0.5


class SpotifyCooldownActive(Exception):
    """Raised when a Spotify call is refused because the process is in
    a cooldown window from a previous 429."""


def is_cooldown_active() -> tuple[bool, float]:
    """Return (active, seconds_remaining). If not in cooldown, (False, 0)."""
    remaining = _COOLDOWN_UNTIL - time.time()
    if remaining > 0:
        return True, remaining
    return False, 0.0


def record_rate_limit(retry_after_seconds: int | float | str | None) -> float:
    """
    Tell the throttle that Spotify just returned 429. Sets the cooldown
    window and returns the number of seconds until it expires.

    Accepts whatever Spotify gave us in the Retry-After header (int, str,
    or missing); tolerates garbage.
    """
    global _COOLDOWN_UNTIL
    try:
        raw = int(float(retry_after_seconds)) if retry_after_seconds is not None else 60
    except (ValueError, TypeError):
        raw = 60
    capped = max(5, min(raw, MAX_COOLDOWN_SECONDS))
    _COOLDOWN_UNTIL = time.time() + capped
    logger.warning(
        "[spotify-throttle] 429 received, raw Retry-After=%s, "
        "setting cooldown for %ds (capped from %ds)",
        retry_after_seconds, capped, raw,
    )
    return capped


def clear_cooldown() -> None:
    """Force-clear the cooldown window. For tests and explicit admin overrides."""
    global _COOLDOWN_UNTIL
    _COOLDOWN_UNTIL = 0.0


async def throttled_request(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    delay: float = DEFAULT_REQUEST_DELAY,
    **kwargs: Any,
) -> httpx.Response:
    """
    Make a Spotify API call through the shared semaphore + cooldown
    governor. Raises SpotifyCooldownActive if a prior 429 cooldown is
    still in effect — callers should treat that as "stop, try again
    later" rather than retrying in a tight loop.

    On a 429 response this function records the cooldown and raises
    SpotifyCooldownActive. On any other response (including non-200),
    it returns the response and lets the caller decide what to do.
    """
    active, remaining = is_cooldown_active()
    if active:
        raise SpotifyCooldownActive(
            f"Spotify cooldown active for another {remaining:.0f}s"
        )

    async with _SEMAPHORE:
        await asyncio.sleep(delay)
        resp = await client.request(method, url, **kwargs)

    if resp.status_code == 429:
        record_rate_limit(resp.headers.get("Retry-After"))
        raise SpotifyCooldownActive(
            f"Spotify returned 429 Retry-After={resp.headers.get('Retry-After', '?')}"
        )

    return resp
