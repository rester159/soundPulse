"""
Spotify scraper for SoundPulse.

Collects trending track and artist data using Spotify Web API endpoints
that work with Client Credentials flow:
- Search API (genre-based discovery)
- Browse API (new releases)
- Artist top tracks
- Audio features

When playlist access is granted (Extended Quota Mode), playlist monitoring
can be re-enabled via TRENDING_PLAYLISTS.
"""

from __future__ import annotations

import asyncio
import base64
import logging
import time
from datetime import date
from typing import Any

from scrapers.base import AuthenticationError, BaseScraper, RawDataPoint

logger = logging.getLogger(__name__)

# Search queries to discover trending tracks across genres
# Covers all 12 root genres plus trending artists and terms
SEARCH_QUERIES = [
    # --- Pop ---
    "pop", "synth pop", "pop new release",
    "taylor swift", "dua lipa", "olivia rodrigo", "billie eilish",
    # --- Rock ---
    "rock", "alternative rock", "indie rock",
    # --- Electronic ---
    "electronic", "edm", "house music", "techno", "drum and bass",
    # --- Hip-hop ---
    "rap", "hip hop", "trap",
    "drake", "kendrick lamar", "travis scott", "post malone",
    # --- R&B ---
    "r&b", "soul", "funk", "neo soul",
    "sza", "weeknd", "doja cat",
    # --- Latin ---
    "latin", "reggaeton", "latin pop", "corridos tumbados",
    "bad bunny", "karol g", "peso pluma",
    # --- Country ---
    "country", "country pop", "country new release",
    # --- Jazz ---
    "jazz", "smooth jazz", "jazz fusion",
    # --- Classical ---
    "classical", "classical crossover",
    # --- African ---
    "afrobeats", "amapiano", "afro pop",
    "burna boy", "wizkid",
    # --- Asian ---
    "kpop", "jpop", "bollywood",
    "bts", "blackpink",
    # --- Caribbean ---
    "dancehall", "soca", "reggae",
    # --- Trending / discovery ---
    "viral hits", "new music friday", "trending",
    "tyler creator", "rihanna",
]


# US-only market focus for maximum data density and prediction precision
TOP_MARKETS = ["US"]


class SpotifyScraper(BaseScraper):
    """Scrape trending data from Spotify using Search + Browse APIs."""

    PLATFORM = "spotify"

    SPOTIFY_API_BASE = "https://api.spotify.com"
    SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"

    # Playlist monitoring — enable once Extended Quota Mode is granted
    TRENDING_PLAYLISTS: dict[str, str] = {
        # "37i9dQZF1DXcBWIGoYBM5M": "Today's Top Hits",
        # "37i9dQZEVXbLiRSasKsNU9": "Viral 50 Global",
        # "37i9dQZF1DX4JAvHpjipBk": "New Music Friday",
        # "37i9dQZF1DX0XUsuxWHRQd": "RapCaviar",
        # "37i9dQZF1DX4dyzvuaRJ0n": "mint",
        # "37i9dQZF1DX1lVhptIYRda": "Hot Country",
        # "37i9dQZF1DWXRqgorJj26U": "Rock This",
        # "37i9dQZF1DX4SBhb3fqCJd": "Are & Be",
        # "37i9dQZF1DX10zKzsJ2jva": "Viva Latino",
        # "37i9dQZF1DX4o1oenSJRJd": "All Out 2020s",
    }

    def __init__(self, credentials: dict, api_base_url: str, admin_key: str):
        super().__init__(credentials, api_base_url, admin_key)
        self.access_token: str = ""
        self.token_expires_at: float = 0.0
        self._semaphore = asyncio.Semaphore(3)

    # ------------------------------------------------------------------
    # Authentication
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
        logger.info("[spotify] Authenticated, token expires in %ds", body.get("expires_in", 3600))

    # ------------------------------------------------------------------
    # Throttled request helper
    # ------------------------------------------------------------------

    async def _throttled_get(self, url: str, params: dict | None = None) -> Any:
        """GET with concurrency limit and 350ms inter-request delay."""
        async with self._semaphore:
            await asyncio.sleep(1.0)  # 1s between requests to avoid rate limits
            resp = await self._rate_limited_request(
                "GET",
                url,
                headers={"Authorization": f"Bearer {self.access_token}"},
                params=params,
            )
            return resp.json()

    # ------------------------------------------------------------------
    # Search API — genre-based track discovery
    # ------------------------------------------------------------------

    async def _search_tracks(self, query: str, limit: int = 20) -> list[dict]:
        """Search for tracks by keyword query. Restricted to US market."""
        import urllib.parse

        # Spotify requires %20 for spaces (not +), so we build the URL manually
        # market=US ensures results are available in the US market
        q_encoded = urllib.parse.quote(query)
        url = (
            f"{self.SPOTIFY_API_BASE}/v1/search"
            f"?q={q_encoded}&type=track&limit={limit}&market=US"
        )
        params = None  # URL already has params

        try:
            data = await self._throttled_get(url, params=params)
            return data.get("tracks", {}).get("items", [])
        except Exception as e:
            logger.warning("[spotify] Search failed for '%s': %s", query, e)
            return []

    # ------------------------------------------------------------------
    # Batch fetch helpers
    # ------------------------------------------------------------------

    async def _batch_fetch_audio_features(self, track_ids: list[str]) -> dict[str, dict[str, Any]]:
        """Fetch audio features for tracks in batches of 100."""
        features_map: dict[str, dict[str, Any]] = {}

        for i in range(0, len(track_ids), 100):
            batch = track_ids[i : i + 100]
            ids_param = ",".join(batch)
            url = f"{self.SPOTIFY_API_BASE}/v1/audio-features?ids={ids_param}"

            try:
                data = await self._throttled_get(url)
                for feat in data.get("audio_features", []):
                    if feat is not None:
                        features_map[feat["id"]] = {
                            "tempo": feat.get("tempo"),
                            "energy": feat.get("energy"),
                            "valence": feat.get("valence"),
                            "danceability": feat.get("danceability"),
                            "acousticness": feat.get("acousticness"),
                            "instrumentalness": feat.get("instrumentalness"),
                        }
            except Exception as e:
                logger.warning("[spotify] Failed to fetch audio features batch: %s", e)

        return features_map

    async def _batch_fetch_artists(self, artist_ids: list[str]) -> dict[str, dict[str, Any]]:
        """Fetch artist details in batches of 50."""
        artists_map: dict[str, dict[str, Any]] = {}

        for i in range(0, len(artist_ids), 50):
            batch = artist_ids[i : i + 50]
            ids_param = ",".join(batch)
            url = f"{self.SPOTIFY_API_BASE}/v1/artists?ids={ids_param}"

            try:
                data = await self._throttled_get(url)
                for artist in data.get("artists", []):
                    if artist is not None:
                        artists_map[artist["id"]] = {
                            "name": artist.get("name", ""),
                            "genres": artist.get("genres", []),
                            "popularity": artist.get("popularity", 0),
                            "followers": artist.get("followers", {}).get("total", 0),
                        }
            except Exception as e:
                logger.warning("[spotify] Failed to fetch artists batch: %s", e)

        return artists_map

    # ------------------------------------------------------------------
    # Playlist fetching (with pagination) — for when access is granted
    # ------------------------------------------------------------------

    async def _fetch_playlist_tracks(self, playlist_id: str) -> list[dict[str, Any]]:
        """Fetch all tracks from a playlist, handling pagination."""
        url = f"{self.SPOTIFY_API_BASE}/v1/playlists/{playlist_id}/tracks?limit=100"
        all_items: list[dict[str, Any]] = []

        while url:
            data = await self._throttled_get(url)
            items = data.get("items", [])
            all_items.extend(items)
            url = data.get("next")

        return all_items

    # ------------------------------------------------------------------
    # collect_trending — main data collection
    # ------------------------------------------------------------------

    async def collect_trending(self) -> list[RawDataPoint]:
        """Collect trending tracks and artists from available Spotify endpoints."""
        today = date.today()

        # Accumulate track data: spotify_id → track info
        track_data: dict[str, dict[str, Any]] = {}

        # ---- Source 1: Keyword search (primary data source) ----
        logger.info("[spotify] Running %d search queries", len(SEARCH_QUERIES))
        for query in SEARCH_QUERIES:
            tracks = await self._search_tracks(query, limit=20)
            for rank, track in enumerate(tracks, start=1):
                self._add_track(track_data, track, source="search", rank=rank)

        logger.info("[spotify] Search found %d unique tracks", len(track_data))

        # ---- Source 3: Playlists (when available) ----
        if self.TRENDING_PLAYLISTS:
            for playlist_id, playlist_name in self.TRENDING_PLAYLISTS.items():
                logger.info("[spotify] Fetching playlist: %s (%s)", playlist_name, playlist_id)
                try:
                    items = await self._fetch_playlist_tracks(playlist_id)
                    for position, item in enumerate(items, start=1):
                        track = item.get("track")
                        if track and track.get("id"):
                            self._add_track(
                                track_data, track,
                                source="playlist", rank=position,
                                playlist_id=playlist_id,
                            )
                except Exception as e:
                    logger.warning("[spotify] Failed to fetch playlist %s: %s", playlist_id, e)

        # ---- Audio features (skipped — requires Extended Quota Mode) ----
        # When granted, uncomment _batch_fetch_audio_features
        audio_features_map: dict[str, dict] = {}
        logger.info("[spotify] Audio features skipped (Extended Quota required)")

        # ---- Batch-fetch artist details ----
        unique_artist_ids = list(
            {td["artist_spotify_id"] for td in track_data.values() if td["artist_spotify_id"]}
        )
        artists_map = await self._batch_fetch_artists(unique_artist_ids)
        logger.info("[spotify] Fetched details for %d artists", len(artists_map))

        # ---- Build track data points ----
        track_points: list[RawDataPoint] = []

        for spotify_track_id, td in track_data.items():
            sources = td["sources"]
            # Score: combine popularity with source bonuses
            raw_score = float(td["spotify_popularity"])
            # Bonus for appearing in multiple sources
            if len(sources) > 1:
                raw_score += len(sources) * 5
            # Bonus for high search rank
            best_rank = td.get("best_rank", 50)
            raw_score += max(0, (50 - best_rank))

            audio_feats = audio_features_map.get(spotify_track_id, {})
            artist_info = artists_map.get(td["artist_spotify_id"], {})
            artist_genres = artist_info.get("genres", [])

            signals: dict[str, Any] = {
                "sources": list(sources),
                "source_count": len(sources),
                "best_rank": best_rank,
                "spotify_popularity": td["spotify_popularity"],
                "audio_features": audio_feats,
                "spotify_genres": artist_genres,
            }

            # Add playlist data if available
            if td.get("playlist_appearances"):
                signals["playlist_appearances"] = len(td["playlist_appearances"])
                signals["best_playlist_position"] = min(
                    pos for _pid, pos in td["playlist_appearances"]
                )

            track_points.append(
                RawDataPoint(
                    platform="spotify",
                    entity_type="track",
                    entity_identifier={
                        "spotify_id": spotify_track_id,
                        "title": td["title"],
                        "artist_name": td["artist_name"],
                        "artist_spotify_id": td["artist_spotify_id"],
                        "isrc": td.get("isrc", ""),
                    },
                    raw_score=raw_score,
                    rank=best_rank,
                    signals=signals,
                    snapshot_date=today,
                )
            )

        # ---- Build artist data points ----
        artist_points: list[RawDataPoint] = []

        for artist_id, info in artists_map.items():
            artist_points.append(
                RawDataPoint(
                    platform="spotify",
                    entity_type="artist",
                    entity_identifier={
                        "spotify_id": artist_id,
                        "artist_name": info["name"],
                    },
                    raw_score=float(info["popularity"]),
                    signals={
                        "spotify_genres": info["genres"],
                        "popularity": info["popularity"],
                        "followers": info["followers"],
                    },
                    snapshot_date=today,
                )
            )

        logger.info(
            "[spotify] Built %d track points and %d artist points",
            len(track_points),
            len(artist_points),
        )

        return track_points + artist_points

    # ------------------------------------------------------------------
    # Helper: add a track to the accumulator
    # ------------------------------------------------------------------

    def _add_track(
        self,
        track_data: dict[str, dict[str, Any]],
        track: dict,
        source: str,
        rank: int,
        playlist_id: str | None = None,
    ) -> None:
        """Add or merge a track into the accumulator dict."""
        track_id = track.get("id")
        if not track_id:
            return

        artists = track.get("artists", [])
        primary_artist_name = artists[0]["name"] if artists else ""
        primary_artist_id = artists[0]["id"] if artists else ""
        isrc = (track.get("external_ids") or {}).get("isrc", "")

        if track_id not in track_data:
            track_data[track_id] = {
                "title": track.get("name", ""),
                "artist_name": primary_artist_name,
                "artist_spotify_id": primary_artist_id,
                "isrc": isrc,
                "spotify_popularity": track.get("popularity", 0),
                "sources": set(),
                "best_rank": rank,
                "playlist_appearances": [],
            }

        entry = track_data[track_id]
        entry["sources"].add(source)
        entry["best_rank"] = min(entry["best_rank"], rank)

        # Update popularity if higher
        pop = track.get("popularity", 0)
        if pop > entry["spotify_popularity"]:
            entry["spotify_popularity"] = pop

        # Backfill ISRC if missing
        if isrc and not entry.get("isrc"):
            entry["isrc"] = isrc

        if playlist_id:
            entry["playlist_appearances"].append((playlist_id, rank))

    # ------------------------------------------------------------------
    # collect_entity_details
    # ------------------------------------------------------------------

    async def collect_entity_details(self, entity_id: str) -> dict:
        """Fetch detailed info for a track or artist by Spotify ID."""
        try:
            url = f"{self.SPOTIFY_API_BASE}/v1/tracks/{entity_id}"
            return await self._throttled_get(url)
        except Exception:
            pass

        url = f"{self.SPOTIFY_API_BASE}/v1/artists/{entity_id}"
        return await self._throttled_get(url)
