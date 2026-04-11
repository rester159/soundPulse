"""
Spotify Audio Analysis enrichment scraper for SoundPulse.

Enriches existing tracks that have a spotify_id but are missing audio_features
by fetching data from Spotify's Audio Features and Audio Analysis endpoints.

- GET /v1/audio-features?ids={ids}  (batch of up to 100)
- GET /v1/audio-analysis/{track_id} (per-track detailed analysis)

Uses the same Client Credentials auth flow as the main Spotify scraper.
"""

from __future__ import annotations

import asyncio
import base64
import logging
import time
from datetime import date
from typing import Any

import httpx

from scrapers.base import AuthenticationError, BaseScraper, RawDataPoint, ScraperError


class SpotifyEndpointForbidden(ScraperError):
    """
    Raised when Spotify returns 401/403 on audio-features or audio-analysis.

    Most likely cause: the client-credential app post-dates Spotify's
    November 2024 policy change that revoked access to these endpoints
    for apps created after that date. Surface this explicitly so the
    scheduler dashboard shows a real error rather than silent success
    with zero records.
    """

logger = logging.getLogger(__name__)

# How many top tracks (by raw_score) get full audio analysis
TOP_TRACKS_FOR_ANALYSIS = 50

# Audio feature keys returned by /v1/audio-features
AUDIO_FEATURE_KEYS = [
    "tempo", "energy", "danceability", "valence", "acousticness",
    "instrumentalness", "liveness", "speechiness", "loudness",
    "key", "mode", "duration_ms", "time_signature",
]


class SpotifyAudioScraper(BaseScraper):
    """Enrich existing tracks with Spotify audio features and analysis."""

    PLATFORM = "spotify_audio"

    SPOTIFY_API_BASE = "https://api.spotify.com"
    SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"

    def __init__(self, credentials: dict, api_base_url: str, admin_key: str):
        super().__init__(credentials, api_base_url, admin_key)
        self.access_token: str = ""
        self.token_expires_at: float = 0.0
        self._semaphore = asyncio.Semaphore(2)

    # ------------------------------------------------------------------
    # Authentication (same Client Credentials flow as spotify.py)
    # ------------------------------------------------------------------

    async def authenticate(self) -> None:
        """Obtain an access token via Client Credentials flow."""
        client_id = self.credentials.get("client_id", "")
        client_secret = self.credentials.get("client_secret", "")

        if not client_id or not client_secret:
            raise AuthenticationError("client_id and client_secret are required")

        encoded = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()

        try:
            resp = await self.client.post(
                self.SPOTIFY_TOKEN_URL,
                data={"grant_type": "client_credentials"},
                headers={
                    "Authorization": f"Basic {encoded}",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
            )
            resp.raise_for_status()
        except Exception as e:
            raise AuthenticationError(f"Spotify auth failed: {e}") from e

        body = resp.json()
        self.access_token = body["access_token"]
        self.token_expires_at = time.time() + body.get("expires_in", 3600)
        logger.info(
            "[spotify_audio] Authenticated, token expires in %ds",
            body.get("expires_in", 3600),
        )

    # ------------------------------------------------------------------
    # Throttled request helpers
    # ------------------------------------------------------------------

    async def _throttled_get(self, url: str, params: dict | None = None, delay: float = 1.0) -> Any:
        """GET with concurrency limit and configurable inter-request delay."""
        async with self._semaphore:
            await asyncio.sleep(delay)
            resp = await self._rate_limited_request(
                "GET",
                url,
                headers={"Authorization": f"Bearer {self.access_token}"},
                params=params,
            )
            return resp.json()

    # ------------------------------------------------------------------
    # Query SoundPulse API for tracks needing enrichment
    # ------------------------------------------------------------------

    async def _fetch_tracks_needing_enrichment(self) -> list[dict[str, Any]]:
        """
        Query the SoundPulse API to find tracks with spotify_id but no
        audio_features yet.

        AUD-011 fix: the previous implementation tried to parse the
        /api/v1/trending response — which doesn't include audio_features,
        uses `limit`/`offset` not `page`/`per_page`, and returns a different
        item shape. The scraper silently got 0 results for months. Now
        using the purpose-built /api/v1/admin/tracks/needing-audio-features
        endpoint which queries the DB directly.
        """
        tracks: list[dict[str, Any]] = []
        offset = 0
        limit = 500
        max_iterations = 20  # hard cap: 10,000 tracks per run

        for _ in range(max_iterations):
            try:
                resp = await self.client.get(
                    f"{self.api_base_url}/api/v1/admin/tracks/needing-audio-features",
                    params={"limit": limit, "offset": offset},
                    headers={"X-API-Key": self.admin_key},
                )
                if resp.status_code != 200:
                    logger.warning(
                        "[spotify_audio] Failed to fetch tracks: HTTP %d body=%s",
                        resp.status_code, resp.text[:200],
                    )
                    break

                body = resp.json()
                rows = body.get("data", [])
                if not rows:
                    break

                for row in rows:
                    spotify_id = row.get("spotify_id")
                    if not spotify_id:
                        continue
                    tracks.append({
                        "spotify_id": spotify_id,
                        "track_id": row.get("track_id", ""),
                        "title": row.get("title", ""),
                        "isrc": row.get("isrc"),
                    })

                if len(rows) < limit:
                    break
                offset += limit

            except Exception as exc:
                logger.warning("[spotify_audio] Error fetching tracks offset=%d: %s", offset, exc)
                break

        logger.info(
            "[spotify_audio] Found %d tracks needing audio enrichment",
            len(tracks),
        )
        return tracks

    # ------------------------------------------------------------------
    # Batch fetch audio features (up to 100 per request)
    # ------------------------------------------------------------------

    async def _batch_fetch_audio_features(
        self, track_ids: list[str]
    ) -> dict[str, dict[str, Any]]:
        """
        Fetch audio features for tracks in batches of 100.

        If Spotify returns 401/403 on the *first* batch, we raise
        SpotifyEndpointForbidden so the run fails loudly instead of
        completing with zero features. For subsequent batches or
        transient 5xx errors we log and continue.
        """
        features_map: dict[str, dict[str, Any]] = {}

        for i in range(0, len(track_ids), 100):
            batch = track_ids[i : i + 100]
            ids_param = ",".join(batch)
            url = f"{self.SPOTIFY_API_BASE}/v1/audio-features?ids={ids_param}"

            try:
                data = await self._throttled_get(url, delay=1.0)
                for feat in data.get("audio_features", []):
                    if feat is not None and feat.get("id"):
                        features_map[feat["id"]] = {
                            k: feat.get(k) for k in AUDIO_FEATURE_KEYS
                        }
            except httpx.HTTPStatusError as e:
                code = e.response.status_code
                body = (e.response.text or "")[:300]
                if code in (401, 403) and i == 0:
                    raise SpotifyEndpointForbidden(
                        f"Spotify /v1/audio-features returned {code}: {body}. "
                        "Likely cause: this Spotify app was created after "
                        "2024-11-27 and no longer has access to audio-features. "
                        "Register a pre-2024 app or switch to a different "
                        "audio-features source (Chartmetric, AcousticBrainz)."
                    ) from e
                logger.warning(
                    "[spotify_audio] HTTP %d on batch %d-%d: %s",
                    code, i, i + len(batch), body,
                )
            except Exception as e:
                logger.warning(
                    "[spotify_audio] Failed to fetch audio features batch %d-%d: %s",
                    i, i + len(batch), e,
                )

        logger.info(
            "[spotify_audio] Fetched audio features for %d/%d tracks",
            len(features_map), len(track_ids),
        )
        return features_map

    # ------------------------------------------------------------------
    # Fetch full audio analysis for a single track
    # ------------------------------------------------------------------

    async def _fetch_audio_analysis(self, track_id: str) -> dict[str, Any] | None:
        """
        Fetch detailed audio analysis for a single track.
        Returns condensed sections/segments data, or None on failure.
        Uses a slower rate (2s delay) since this is a heavier endpoint.
        """
        url = f"{self.SPOTIFY_API_BASE}/v1/audio-analysis/{track_id}"

        try:
            data = await self._throttled_get(url, delay=2.0)
        except Exception as e:
            logger.warning(
                "[spotify_audio] Failed to fetch audio analysis for %s: %s",
                track_id, e,
            )
            return None

        # Condense the analysis to the most useful parts
        analysis: dict[str, Any] = {}

        # Sections: verse/chorus/bridge structure with tempo/key/loudness changes
        raw_sections = data.get("sections", [])
        analysis["sections"] = [
            {
                "start": s.get("start"),
                "duration": s.get("duration"),
                "loudness": s.get("loudness"),
                "tempo": s.get("tempo"),
                "tempo_confidence": s.get("tempo_confidence"),
                "key": s.get("key"),
                "key_confidence": s.get("key_confidence"),
                "mode": s.get("mode"),
                "mode_confidence": s.get("mode_confidence"),
                "time_signature": s.get("time_signature"),
                "time_signature_confidence": s.get("time_signature_confidence"),
            }
            for s in raw_sections
        ]

        # Segments: condense to summary stats rather than storing thousands of
        # individual segments. We keep the first 3 and last 3 for intro/outro
        # analysis, plus aggregate timbre and pitch statistics.
        raw_segments = data.get("segments", [])
        if raw_segments:
            analysis["segment_count"] = len(raw_segments)

            # Average timbre vector across all segments (12 dimensions)
            timbre_sums = [0.0] * 12
            pitch_sums = [0.0] * 12
            loudness_sum = 0.0
            for seg in raw_segments:
                timbre = seg.get("timbre", [0.0] * 12)
                pitches = seg.get("pitches", [0.0] * 12)
                for j in range(min(12, len(timbre))):
                    timbre_sums[j] += timbre[j]
                for j in range(min(12, len(pitches))):
                    pitch_sums[j] += pitches[j]
                loudness_sum += seg.get("loudness_max", 0.0)

            n = len(raw_segments)
            analysis["avg_timbre"] = [round(t / n, 3) for t in timbre_sums]
            analysis["avg_pitches"] = [round(p / n, 3) for p in pitch_sums]
            analysis["avg_segment_loudness"] = round(loudness_sum / n, 3)

            # Intro segments (first 3) and outro segments (last 3)
            def _condense_segment(seg: dict) -> dict:
                return {
                    "start": seg.get("start"),
                    "duration": seg.get("duration"),
                    "loudness_max": seg.get("loudness_max"),
                    "timbre": seg.get("timbre", []),
                    "pitches": seg.get("pitches", []),
                }

            analysis["intro_segments"] = [
                _condense_segment(s) for s in raw_segments[:3]
            ]
            analysis["outro_segments"] = [
                _condense_segment(s) for s in raw_segments[-3:]
            ]

        # Beat/bar/tatum counts (useful metadata without storing every timestamp)
        analysis["beat_count"] = len(data.get("beats", []))
        analysis["bar_count"] = len(data.get("bars", []))
        analysis["tatum_count"] = len(data.get("tatums", []))

        # Track-level analysis metadata
        track_info = data.get("track", {})
        if track_info:
            analysis["analysis_sample_rate"] = track_info.get("analysis_sample_rate")
            analysis["end_of_fade_in"] = track_info.get("end_of_fade_in")
            analysis["start_of_fade_out"] = track_info.get("start_of_fade_out")
            analysis["duration"] = track_info.get("duration")

        return analysis

    # ------------------------------------------------------------------
    # collect_trending — main enrichment pipeline
    # ------------------------------------------------------------------

    async def collect_trending(self) -> list[RawDataPoint]:
        """
        Enrichment pipeline:
        1. Query SoundPulse for tracks missing audio features
        2. Batch fetch audio features from Spotify
        3. For top tracks, fetch full audio analysis
        4. Return data points to be POSTed back to SoundPulse
        """
        today = date.today()

        # Step 1: Find tracks needing enrichment
        tracks = await self._fetch_tracks_needing_enrichment()
        if not tracks:
            logger.info("[spotify_audio] No tracks need enrichment")
            return []

        # Deduplicate by spotify_id
        seen: set[str] = set()
        unique_tracks: list[dict[str, Any]] = []
        for t in tracks:
            sid = t["spotify_id"]
            if sid not in seen:
                seen.add(sid)
                unique_tracks.append(t)

        all_spotify_ids = [t["spotify_id"] for t in unique_tracks]
        logger.info(
            "[spotify_audio] Enriching %d unique tracks", len(all_spotify_ids)
        )

        # Step 2: Batch fetch audio features
        features_map = await self._batch_fetch_audio_features(all_spotify_ids)

        # Step 3: For the most recently added tracks, also fetch full audio
        # analysis. The admin endpoint returns tracks ordered by created_at
        # DESC, so unique_tracks is already in "newest first" order — no
        # raw_score available here (entity_resolution strips it from the
        # track row), so we can't re-rank by trending strength.
        top_track_ids = [
            t["spotify_id"] for t in unique_tracks[:TOP_TRACKS_FOR_ANALYSIS]
        ]
        analysis_map: dict[str, dict[str, Any]] = {}

        logger.info(
            "[spotify_audio] Fetching full audio analysis for top %d tracks",
            len(top_track_ids),
        )
        for track_id in top_track_ids:
            analysis = await self._fetch_audio_analysis(track_id)
            if analysis:
                analysis_map[track_id] = analysis

        logger.info(
            "[spotify_audio] Fetched audio analysis for %d/%d top tracks",
            len(analysis_map), len(top_track_ids),
        )

        # Step 4: Build data points
        data_points: list[RawDataPoint] = []

        for track in unique_tracks:
            spotify_id = track["spotify_id"]
            features = features_map.get(spotify_id)
            if not features:
                # No audio features available for this track, skip
                continue

            signals: dict[str, Any] = {
                "audio_features": features,
                "enrichment_source": "spotify_audio",
            }

            # Attach full analysis if available
            analysis = analysis_map.get(spotify_id)
            if analysis:
                signals["audio_analysis"] = analysis

            # spotify_id alone is enough to match the existing track via
            # entity resolution. title is included only for log/debug
            # readability; artist_name is not available from the admin
            # endpoint (the old code sent an empty string, which could
            # disrupt resolution — now omitted entirely).
            entity_identifier: dict[str, Any] = {"spotify_id": spotify_id}
            if track.get("title"):
                entity_identifier["title"] = track["title"]

            data_points.append(
                RawDataPoint(
                    platform="spotify",
                    entity_type="track",
                    entity_identifier=entity_identifier,
                    raw_score=None,
                    signals=signals,
                    snapshot_date=today,
                )
            )

        logger.info(
            "[spotify_audio] Built %d enrichment data points (%d with full analysis)",
            len(data_points), len(analysis_map),
        )
        return data_points

    # ------------------------------------------------------------------
    # collect_entity_details
    # ------------------------------------------------------------------

    async def collect_entity_details(self, entity_id: str) -> dict:
        """Fetch audio features and analysis for a single track."""
        features_map = await self._batch_fetch_audio_features([entity_id])
        analysis = await self._fetch_audio_analysis(entity_id)

        return {
            "audio_features": features_map.get(entity_id, {}),
            "audio_analysis": analysis or {},
        }
