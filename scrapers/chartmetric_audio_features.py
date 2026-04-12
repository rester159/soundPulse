"""
Chartmetric audio-features enrichment scraper (tempo + duration only).

HONEST SCOPE (verified 2026-04-12 via /admin/chartmetric/probe-sub-endpoints):
Chartmetric's paid API `/api/track/{cm_track_id}` endpoint returns only
`tempo` and `duration_ms` — not the full 13-field Spotify audio features
set. The hidden sub-endpoints (/audio-features, /sp-audio-features,
/audio-analysis, v2/track) all return 401 "Chartmetric internal API
endpoint" — they're reserved for Chartmetric's own web UI and are not
exposed to API subscribers. So we take the 2 fields we can get and
move on.

Why this still has value:
- `tempo` is arguably the single most useful audio feature for
  songwriting + blueprint generation.
- `duration_ms` is trivially useful for song structure.
- Partial audio features are infinitely better than zero, which is
  what the broken Spotify /v1/audio-features pipeline produced.

For the other 11 features (energy, danceability, valence, etc.) we
need a different data source — see planning/tasks.md for the follow-up
options (AcousticBrainz, pre-2024 Spotify app, Cyanite.ai, local
Essentia).

Rate limit: Chartmetric documents "2 req/sec" but in practice /api/track/{id}
starts returning 429 "Rate limit exceeded, retry in -X ms" much faster
than that. We run conservatively at one call per 2.5 seconds (0.4 req/s)
with a semaphore of 1 (serial) to stay comfortably under the real ceiling.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import date
from typing import Any

import httpx

from scrapers.base import AuthenticationError, BaseScraper, RawDataPoint

logger = logging.getLogger(__name__)


# Work-queue endpoint that returns tracks needing enrichment
QUEUE_ENDPOINT = "/api/v1/admin/tracks/needing-audio-features-cm"

# Page size when paging the queue endpoint
PAGE_SIZE = 500

# Hard cap per run. At 2.5s per track = ~40 min to process 1000 tracks.
# Runs every 6h so the full ~5,200-track backlog drains in ~32 hours.
MAX_TRACKS_PER_RUN = 1000

# Canonical audio feature field names (matches Spotify's /v1/audio-features
# response shape and what the rest of SoundPulse expects to find in
# tracks.audio_features).
AUDIO_FEATURE_KEYS = [
    "tempo", "energy", "danceability", "valence", "acousticness",
    "instrumentalness", "liveness", "speechiness", "loudness",
    "key", "mode", "duration_ms", "time_signature",
]


def _extract_audio_features(payload: dict[str, Any]) -> dict[str, Any] | None:
    """
    Pull a canonical audio_features dict out of a Chartmetric /api/track/{id}
    response. Returns None if no recognizable features are present.

    Chartmetric has used at least three shapes historically:
      1. Flat top-level: {tempo, energy, danceability, ...}
      2. Nested: {audio_features: {tempo, energy, ...}}
      3. Prefixed nested: {sp_audio_features: {tempo, ...}}
      4. Inside an `obj` wrapper for any of the above.
    We try all combinations and return the first that yields a non-empty
    dict of known keys.
    """
    # Unwrap Chartmetric's common `obj` envelope
    if not isinstance(payload, dict):
        return None
    candidates: list[dict[str, Any]] = []

    obj = payload.get("obj")
    if isinstance(obj, dict):
        candidates.append(obj)
    candidates.append(payload)  # also try the raw payload

    for c in candidates:
        # Shape 2/3: nested under a key
        for wrapper_key in ("audio_features", "sp_audio_features", "spotify_audio_features"):
            nested = c.get(wrapper_key)
            if isinstance(nested, dict):
                extracted = {k: nested.get(k) for k in AUDIO_FEATURE_KEYS if nested.get(k) is not None}
                if extracted:
                    return extracted
        # Shape 1: flat top-level
        flat = {k: c.get(k) for k in AUDIO_FEATURE_KEYS if c.get(k) is not None}
        if flat:
            return flat

    return None


class ChartmetricAudioFeaturesScraper(BaseScraper):
    """
    Pulls Spotify audio features from Chartmetric's per-track endpoint
    for every track with chartmetric_id but no audio_features. Uses its
    own run() override (like chartmetric_artist_tracks) to batch via the
    bulk ingest endpoint rather than per-record POST.
    """

    PLATFORM = "chartmetric"  # we're writing rows under the chartmetric platform namespace
    API_BASE = "https://api.chartmetric.com"
    TOKEN_URL = "https://api.chartmetric.com/api/token"
    # Conservative 0.4 req/s. Chartmetric's documented 2 req/s limit
    # doesn't apply to /api/track/{id} in practice — observed 429s with
    # "retry in -436ms" at 2 req/s sustained. 2.5s gives comfortable margin.
    REQUEST_DELAY = 2.5
    # Smaller batches flush sooner, so progress shows up in DB quickly
    # and a mid-run kill loses at most 50 tracks of work.
    BULK_BATCH_SIZE = 50

    def __init__(self, credentials: dict, api_base_url: str, admin_key: str):
        super().__init__(credentials, api_base_url, admin_key)
        self.access_token: str | None = None
        # Serial (semaphore of 1) — parallelism was causing Chartmetric
        # to return 429s before the first flush could land.
        self._semaphore = asyncio.Semaphore(1)
        self._buffer: list[dict[str, Any]] = []
        self._stats: dict[str, int] = {
            "tracks_fetched": 0,
            "tracks_with_features": 0,
            "tracks_without_features": 0,
            "errors": 0,
            "bulk_flushes": 0,
        }

    async def authenticate(self) -> None:
        api_key = self.credentials.get("api_key")
        if not api_key:
            raise AuthenticationError("chartmetric_audio_features missing 'api_key'")
        try:
            resp = await self._rate_limited_request(
                "POST", self.TOKEN_URL, json={"refreshtoken": api_key},
            )
            data = resp.json()
            token = data.get("token") or data.get("access_token")
            if not token:
                raise AuthenticationError(f"no token in response: {list(data.keys())}")
            self.access_token = token
            logger.info("[cm-audio-features] authenticated")
        except httpx.HTTPError as exc:
            raise AuthenticationError(f"auth failed: {exc}") from exc

    async def collect_trending(self) -> list[RawDataPoint]:
        await self._enrich_all()
        return []

    async def collect_entity_details(self, entity_id: str) -> dict:
        return {"error": "chartmetric_audio_features does not support entity detail"}

    async def run(self) -> dict[str, int]:
        try:
            await self.authenticate()
            await self._enrich_all()
            await self._flush_buffer()
            logger.info("[cm-audio-features] complete: %s", self._stats)
            return {"total": self._stats["tracks_with_features"], **self._stats}
        finally:
            await self.close()

    # ---------------- main loop ----------------

    async def _enrich_all(self) -> None:
        """Page the work queue and process each track."""
        offset = 0
        processed_total = 0
        logged_sample_shape = False

        while processed_total < MAX_TRACKS_PER_RUN:
            page = await self._fetch_queue_page(offset=offset)
            if not page:
                logger.info("[cm-audio-features] queue empty at offset=%d, stopping", offset)
                break
            logger.info(
                "[cm-audio-features] page offset=%d size=%d processed=%d",
                offset, len(page), processed_total,
            )
            for i, row in enumerate(page):
                cm_id = row.get("chartmetric_id")
                track_uuid = row.get("track_id")
                if cm_id is None or track_uuid is None:
                    continue

                features, raw_keys = await self._fetch_track_features(int(cm_id))
                self._stats["tracks_fetched"] += 1
                # Log the first track's raw shape so we can tell from the
                # logs exactly what Chartmetric returned — diagnosis on
                # first run without needing a separate probe.
                if not logged_sample_shape and raw_keys:
                    logger.info(
                        "[cm-audio-features] first track cm_id=%s raw response top-level "
                        "keys: %s",
                        cm_id, raw_keys[:30],
                    )
                    logged_sample_shape = True

                if not features:
                    self._stats["tracks_without_features"] += 1
                    continue

                self._stats["tracks_with_features"] += 1
                self._buffer.append({
                    "platform": "chartmetric",
                    "entity_type": "track",
                    "entity_identifier": {
                        "chartmetric_id": cm_id,
                        "title": row.get("title") or "",
                    },
                    "raw_score": None,
                    "rank": None,
                    "snapshot_date": date.today().isoformat(),
                    "signals": {
                        "audio_features": features,
                        "chart_type": "audio_features_enrichment",
                        "source_platform": "chartmetric_audio",
                        "cm_track_id": cm_id,
                    },
                })

                if len(self._buffer) >= self.BULK_BATCH_SIZE:
                    await self._flush_buffer()

                # Verbose progress log every 10 tracks so Railway logs
                # show liveness — critical for diagnosing future hangs.
                if (processed_total + i + 1) % 10 == 0:
                    logger.info(
                        "[cm-audio-features] progress: fetched=%d with_features=%d "
                        "without_features=%d errors=%d bulk_flushes=%d",
                        self._stats["tracks_fetched"],
                        self._stats["tracks_with_features"],
                        self._stats["tracks_without_features"],
                        self._stats["errors"],
                        self._stats["bulk_flushes"],
                    )

            processed_total += len(page)
            if len(page) < PAGE_SIZE:
                logger.info(
                    "[cm-audio-features] partial page (%d<%d), stopping at %d processed",
                    len(page), PAGE_SIZE, processed_total,
                )
                break
            offset += PAGE_SIZE

    async def _fetch_queue_page(self, *, offset: int) -> list[dict[str, Any]]:
        url = f"{self.api_base_url}{QUEUE_ENDPOINT}"
        try:
            resp = await self.client.get(
                url,
                params={"offset": offset, "limit": PAGE_SIZE},
                headers={"X-API-Key": self.admin_key},
                timeout=60.0,
            )
            if resp.status_code != 200:
                logger.warning(
                    "[cm-audio-features] queue page HTTP %d offset=%d",
                    resp.status_code, offset,
                )
                return []
            return resp.json().get("data", [])
        except httpx.HTTPError as exc:
            logger.warning(
                "[cm-audio-features] queue page fetch failed offset=%d: %s",
                offset, exc,
            )
            return []

    async def _fetch_track_features(self, cm_id: int) -> tuple[dict[str, Any] | None, list[str]]:
        """
        Hit /api/track/{cm_id} and extract audio features.

        Returns (features_dict, raw_top_level_keys). Returning the raw keys
        lets the caller log the shape of Chartmetric's first response for
        diagnosis.
        """
        url = f"{self.API_BASE}/api/track/{cm_id}"
        async with self._semaphore:
            await asyncio.sleep(self.REQUEST_DELAY)
            try:
                resp = await self._rate_limited_request(
                    "GET", url,
                    headers={"Authorization": f"Bearer {self.access_token}"},
                )
            except httpx.HTTPStatusError as exc:
                code = exc.response.status_code
                if code in (401, 403, 404):
                    return None, []
                self._stats["errors"] += 1
                return None, []
            except Exception:
                self._stats["errors"] += 1
                return None, []

        try:
            payload = resp.json()
        except Exception:
            return None, []

        raw_keys = list(payload.keys()) if isinstance(payload, dict) else []
        # If the payload is wrapped in `obj`, report those keys too for
        # diagnosis — they're the actually interesting ones.
        if isinstance(payload, dict) and isinstance(payload.get("obj"), dict):
            raw_keys = raw_keys + [f"obj.{k}" for k in payload["obj"].keys()]

        features = _extract_audio_features(payload)
        return features, raw_keys

    async def _flush_buffer(self) -> None:
        if not self._buffer:
            return
        url = f"{self.api_base_url}/api/v1/trending/bulk"
        while self._buffer:
            chunk = self._buffer[: self.BULK_BATCH_SIZE]
            self._buffer = self._buffer[self.BULK_BATCH_SIZE :]
            try:
                resp = await self.client.post(
                    url,
                    json={"items": chunk},
                    headers={"X-API-Key": self.admin_key},
                    timeout=120.0,
                )
                if resp.status_code in (200, 201):
                    body = resp.json().get("data", {})
                    self._stats["bulk_flushes"] += 1
                    logger.info(
                        "[cm-audio-features] bulk: received=%d ingested=%d dupes=%d errors=%d",
                        body.get("received", 0), body.get("ingested", 0),
                        body.get("duplicates", 0), body.get("errors", 0),
                    )
                else:
                    logger.error(
                        "[cm-audio-features] bulk flush HTTP %d: %s",
                        resp.status_code, resp.text[:300],
                    )
            except httpx.HTTPError as exc:
                logger.error("[cm-audio-features] bulk flush error: %s", exc)
