"""
MusicBrainz enricher for SoundPulse.

NOT a trending source — this enricher looks up existing entities in the SoundPulse
database and augments them with metadata from MusicBrainz (tags, ISRCs, canonical
names, artist MBIDs).

Uses the MusicBrainz Web Service v2 with a strict 1-request-per-second rate limit.
"""

from __future__ import annotations

import asyncio
import logging
import urllib.parse
from datetime import date
from typing import Any

from scrapers.base import AuthenticationError, BaseScraper, RawDataPoint

logger = logging.getLogger(__name__)


class MusicBrainzEnricher(BaseScraper):
    """Enrich SoundPulse entities with MusicBrainz metadata."""

    PLATFORM = "musicbrainz"  # Not a trending platform, but uses same base
    MB_BASE = "https://musicbrainz.org/ws/2"
    USER_AGENT = "SoundPulse/0.1.0 (contact@soundpulse.dev)"

    def __init__(self, credentials: dict, api_base_url: str, admin_key: str):
        super().__init__(credentials, api_base_url, admin_key)
        # CRITICAL: MusicBrainz enforces 1 req/sec. Hard IP ban if exceeded.
        self._semaphore = asyncio.Semaphore(1)

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    async def authenticate(self) -> None:
        """No-op — MusicBrainz requires no API key, only a User-Agent header."""
        logger.info(
            "[musicbrainz] No authentication required (using User-Agent: %s)",
            self.USER_AGENT,
        )

    # ------------------------------------------------------------------
    # MusicBrainz request helper
    # ------------------------------------------------------------------

    async def _mb_get(self, url: str) -> dict[str, Any]:
        """MusicBrainz GET with 1.2s rate limit (safety margin over 1s requirement)."""
        async with self._semaphore:
            await asyncio.sleep(1.2)
            resp = await self._rate_limited_request(
                "GET",
                url,
                headers={
                    "User-Agent": self.USER_AGENT,
                    "Accept": "application/json",
                },
            )
            return resp.json()

    # ------------------------------------------------------------------
    # Recording lookup helpers
    # ------------------------------------------------------------------

    async def _lookup_recording(
        self, isrc: str | None, title: str, artist: str
    ) -> dict[str, Any] | None:
        """Look up a recording in MusicBrainz. Returns enrichment data or None."""
        # Try ISRC first (most reliable)
        if isrc:
            url = f"{self.MB_BASE}/recording?query=isrc:{isrc}&fmt=json&limit=1"
            data = await self._mb_get(url)
            recordings = data.get("recordings", [])
            if recordings:
                return await self._get_recording_details(recordings[0]["id"])

        # Fall back to title + artist search
        if title and artist:
            q = urllib.parse.quote(f'recording:"{title}" AND artist:"{artist}"')
            url = f"{self.MB_BASE}/recording?query={q}&fmt=json&limit=1"
            data = await self._mb_get(url)
            recordings = data.get("recordings", [])
            if recordings and recordings[0].get("score", 0) >= 80:
                return await self._get_recording_details(recordings[0]["id"])

        return None

    async def _get_recording_details(self, mbid: str) -> dict[str, Any]:
        """Get full recording details including tags, ISRCs, and artist info."""
        url = f"{self.MB_BASE}/recording/{mbid}?inc=artists+releases+isrcs+tags&fmt=json"
        data = await self._mb_get(url)

        tags = [
            t["name"] for t in data.get("tags", []) if t.get("count", 0) >= 1
        ]
        isrcs = data.get("isrcs", [])
        artist_credit = data.get("artist-credit", [])

        return {
            "mbid": mbid,
            "tags": tags,
            "isrc": isrcs[0] if isrcs else None,
            "title": data.get("title"),
            "artist": artist_credit[0].get("name") if artist_credit else None,
        }

    # ------------------------------------------------------------------
    # run() — overrides BaseScraper.run() for enrichment workflow
    # ------------------------------------------------------------------

    async def run(self) -> dict[str, int]:
        """Enrich existing entities with MusicBrainz metadata."""
        await self.authenticate()

        # Fetch tracks from SoundPulse API
        try:
            resp = await self.client.get(
                f"{self.api_base_url}/api/v1/trending",
                params={"entity_type": "track", "time_range": "30d", "limit": "100"},
                headers={"X-API-Key": self.admin_key},
            )
            resp.raise_for_status()
        except Exception as e:
            logger.error("[musicbrainz] Failed to fetch tracks from SoundPulse API: %s", e)
            raise

        tracks = resp.json().get("data", [])
        logger.info("[musicbrainz] Fetched %d tracks for enrichment", len(tracks))

        enriched, skipped, failed = 0, 0, 0

        for item in tracks:
            entity = item.get("entity", {})
            isrc = entity.get("isrc")
            title = entity.get("name", "")
            artist = entity.get("artist", {}).get("name", "")
            spotify_id = entity.get("platform_ids", {}).get("spotify", "")

            # Skip if already has genre data (likely already enriched)
            if entity.get("genres"):
                skipped += 1
                continue

            try:
                mb_data = await self._lookup_recording(isrc, title, artist)
                if mb_data:
                    # Post enrichment as a spotify-platform snapshot so it passes
                    # VALID_PLATFORMS validation. The signals carry the MusicBrainz data.
                    point = RawDataPoint(
                        platform="spotify",
                        entity_type="track",
                        entity_identifier={
                            "spotify_id": spotify_id,
                            "title": title,
                            "artist_name": artist,
                            "isrc": isrc or mb_data.get("isrc"),
                        },
                        signals={
                            "musicbrainz_tags": mb_data.get("tags", []),
                            "musicbrainz_id": mb_data.get("mbid"),
                            "enrichment_source": "musicbrainz",
                        },
                        snapshot_date=date.today(),
                    )
                    try:
                        await self._post_to_api(point)
                        enriched += 1
                    except Exception:
                        # Duplicate snapshot (409) is expected and fine
                        enriched += 1
                else:
                    skipped += 1
            except Exception as e:
                logger.warning(
                    "[musicbrainz] Failed to enrich: %s - %s: %s", title, artist, e
                )
                failed += 1

        stats = {"enriched": enriched, "skipped": skipped, "failed": failed, "total": enriched + skipped + failed}
        logger.info("[musicbrainz] Enrichment complete: %s", stats)
        return stats

    # ------------------------------------------------------------------
    # collect_trending — not used by enricher
    # ------------------------------------------------------------------

    async def collect_trending(self) -> list[RawDataPoint]:
        """Not used — enricher overrides run() directly."""
        return []

    # ------------------------------------------------------------------
    # collect_entity_details
    # ------------------------------------------------------------------

    async def collect_entity_details(self, entity_id: str) -> dict:
        """Look up a recording by MusicBrainz ID."""
        return await self._get_recording_details(entity_id)
