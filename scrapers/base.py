"""
Base scraper class for all SoundPulse data collectors.

All scrapers inherit from BaseScraper, which provides:
- Retry logic with exponential backoff
- Rate limit handling (429 responses)
- Structured logging
- POST to SoundPulse ingestion API
"""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from datetime import date
from typing import Any

import httpx
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class ScraperError(Exception):
    """Base exception for scraper errors."""

class AuthenticationError(ScraperError):
    """Failed to authenticate with upstream platform."""

class RateLimitError(ScraperError):
    """Hit rate limit after max retries."""

class IngestionError(ScraperError):
    """Failed to POST data to SoundPulse API."""


class RawDataPoint(BaseModel):
    """Raw data as received from upstream platform."""
    platform: str
    entity_type: str  # "artist" or "track"
    entity_identifier: dict[str, Any]
    raw_score: float | None = None
    rank: int | None = None
    signals: dict[str, Any] = {}
    snapshot_date: date


class BaseScraper(ABC):
    """
    Abstract base class for all platform scrapers.
    Subclasses must implement authenticate(), collect_trending(), collect_entity_details().
    """

    PLATFORM: str = ""  # override in subclass
    MAX_RETRIES: int = 5
    BASE_DELAY: float = 1.0

    def __init__(self, credentials: dict, api_base_url: str, admin_key: str):
        self.credentials = credentials
        self.api_base_url = api_base_url.rstrip("/")
        self.admin_key = admin_key
        self.client = httpx.AsyncClient(timeout=60.0)

    @abstractmethod
    async def authenticate(self) -> None:
        """Obtain/refresh access token."""

    @abstractmethod
    async def collect_trending(self) -> list[RawDataPoint]:
        """Fetch current trending data from upstream."""

    @abstractmethod
    async def collect_entity_details(self, entity_id: str) -> dict:
        """Fetch detailed info for a specific entity."""

    async def run(self) -> dict[str, int]:
        """Full pipeline: auth -> collect -> POST to SoundPulse API."""
        try:
            await self.authenticate()
            data_points = await self.collect_trending()
            logger.info("[%s] Collected %d data points", self.PLATFORM, len(data_points))

            success, failed, skipped = 0, 0, 0
            for i, point in enumerate(data_points):
                try:
                    result = await self._post_to_api(point)
                    if result == "created":
                        success += 1
                    else:
                        skipped += 1  # duplicate
                    if (i + 1) % 10 == 0:
                        logger.info("[%s] Ingested %d/%d", self.PLATFORM, i + 1, len(data_points))
                except Exception as e:
                    logger.error("[%s] Ingest failed: %s | entity=%s", self.PLATFORM, e, point.entity_identifier)
                    failed += 1
                await asyncio.sleep(0.2)  # pace ingestion to avoid overwhelming the API

            stats = {"success": success, "failed": failed, "skipped": skipped, "total": len(data_points)}
            logger.info("[%s] Ingestion complete: %s", self.PLATFORM, stats)
            return stats

        except AuthenticationError:
            logger.error("[%s] Authentication failed", self.PLATFORM)
            raise
        except Exception as e:
            logger.error("[%s] Collection failed: %s", self.PLATFORM, e)
            raise

    async def _post_to_api(self, point: RawDataPoint) -> str:
        """POST a data point to the SoundPulse ingestion endpoint. Returns 'created' or 'duplicate'."""
        for attempt in range(self.MAX_RETRIES):
            try:
                resp = await self.client.post(
                    f"{self.api_base_url}/api/v1/trending",
                    json=point.model_dump(mode="json"),
                    headers={"X-API-Key": self.admin_key},
                )
                if resp.status_code == 201:
                    return "created"
                elif resp.status_code == 409:
                    return "duplicate"
                elif resp.status_code == 429:
                    try:
                        retry_after = max(1, int(float(resp.headers.get("Retry-After", 60))))
                    except (ValueError, TypeError):
                        retry_after = 60
                    logger.warning("[%s] Rate limited by API, waiting %ds", self.PLATFORM, retry_after)
                    await asyncio.sleep(retry_after)
                    continue
                else:
                    resp.raise_for_status()
            except httpx.HTTPStatusError as e:
                body = e.response.text[:200] if e.response else ""
                logger.warning("[%s] HTTP %d on attempt %d: %s", self.PLATFORM, e.response.status_code, attempt + 1, body)
                delay = self.BASE_DELAY * (2 ** attempt)
                await asyncio.sleep(delay)
            except httpx.HTTPError as e:
                logger.warning("[%s] Request error on attempt %d: %s: %s", self.PLATFORM, attempt + 1, type(e).__name__, e)
                delay = self.BASE_DELAY * (2 ** attempt)
                await asyncio.sleep(delay)

        raise IngestionError(f"Failed after {self.MAX_RETRIES} retries")

    # Cap on Retry-After sleeps to prevent a single 429 with a large
    # header value from silently hanging a run for 30+ minutes. If the
    # upstream wants a longer wait, better to fail loudly and let the
    # scheduler surface the error than to sit idle with last_status=running.
    MAX_RETRY_AFTER_SECONDS: int = 120

    async def _rate_limited_request(self, method: str, url: str, **kwargs) -> httpx.Response:
        """Make an upstream request with retry and rate limit handling."""
        for attempt in range(self.MAX_RETRIES):
            try:
                resp = await self.client.request(method, url, **kwargs)
                if resp.status_code == 429:
                    try:
                        raw_retry = int(float(resp.headers.get("Retry-After", 5)))
                    except (ValueError, TypeError):
                        raw_retry = 5
                    if raw_retry > self.MAX_RETRY_AFTER_SECONDS:
                        logger.error(
                            "[%s] Upstream 429 Retry-After=%ds exceeds cap %ds, "
                            "failing fast: %s",
                            self.PLATFORM, raw_retry, self.MAX_RETRY_AFTER_SECONDS, url,
                        )
                        raise RateLimitError(
                            f"Upstream requested Retry-After={raw_retry}s "
                            f"(cap={self.MAX_RETRY_AFTER_SECONDS}s) — refusing to hang"
                        )
                    retry_after = max(1, raw_retry)
                    logger.warning("[%s] Upstream rate limited, waiting %ds: %s", self.PLATFORM, retry_after, url)
                    await asyncio.sleep(retry_after)
                    continue
                # Don't retry 4xx client errors (except 429) — they're permanent
                if 400 <= resp.status_code < 500:
                    resp.raise_for_status()
                resp.raise_for_status()
                return resp
            except httpx.HTTPStatusError:
                if resp.status_code < 500 and resp.status_code != 429:
                    raise  # don't retry client errors
                if attempt < self.MAX_RETRIES - 1:
                    delay = self.BASE_DELAY * (2 ** attempt)
                    await asyncio.sleep(delay)
                else:
                    raise
        raise RateLimitError(f"Rate limited after {self.MAX_RETRIES} retries: {url}")

    async def close(self):
        """Close the httpx client."""
        await self.client.aclose()
