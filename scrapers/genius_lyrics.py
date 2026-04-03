"""
Genius lyrics enricher — fetches song lyrics and extracts lyrical features.

Genius API provides song search and metadata. Full lyrics are scraped from
the song page (the API doesn't return lyrics directly). We extract:
- Raw lyrics text
- Lyrical themes (via keyword analysis)
- Word count, line count, vocabulary richness
- Language
- Chorus repetition ratio

This data feeds the "song DNA" profile used by the music generation pipeline.
"""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import date
from typing import Any

import httpx
from bs4 import BeautifulSoup

from scrapers.base import BaseScraper, RawDataPoint, AuthenticationError

logger = logging.getLogger(__name__)

# Theme keyword lists for classification
THEME_KEYWORDS = {
    "love": ["love", "heart", "baby", "kiss", "forever", "darling", "romance", "crush"],
    "heartbreak": ["broken", "tears", "goodbye", "alone", "miss you", "hurt", "pain", "lost"],
    "party": ["party", "dance", "club", "tonight", "drink", "celebrate", "turn up", "vibe"],
    "angst": ["scream", "hate", "rage", "anger", "fire", "burn", "destroy", "fight"],
    "flex": ["money", "cash", "drip", "ice", "chain", "rich", "boss", "flex", "bands"],
    "introspection": ["think", "wonder", "feel", "mind", "soul", "dream", "life", "truth"],
    "social": ["world", "people", "change", "freedom", "justice", "power", "struggle"],
    "nostalgia": ["remember", "back then", "used to", "childhood", "memory", "old days"],
    "desire": ["want", "need", "crave", "body", "touch", "closer", "fantasy"],
    "empowerment": ["strong", "queen", "king", "rise", "unstoppable", "power", "shine"],
}


class GeniusLyricsScraper(BaseScraper):
    PLATFORM = "genius"
    API_BASE = "https://api.genius.com"
    WEB_BASE = "https://genius.com"

    def __init__(self, credentials: dict, api_base_url: str, admin_key: str):
        super().__init__(credentials, api_base_url, admin_key)
        self.access_token = credentials.get("api_key", "")
        self._semaphore = asyncio.Semaphore(2)

    async def authenticate(self) -> None:
        if not self.access_token:
            raise AuthenticationError("Genius API token not configured")
        # Genius uses a simple bearer token, no exchange needed
        logger.info("[%s] Using configured API token", self.PLATFORM)

    async def collect_trending(self) -> list[RawDataPoint]:
        """Fetch lyrics for tracks in the database that don't have lyrics data yet."""
        # Get trending tracks from SoundPulse API
        try:
            resp = await self._rate_limited_request(
                "GET",
                f"{self.api_base_url}/api/v1/trending",
                params={"entity_type": "track", "limit": 50, "sort": "composite_score"},
                headers={"X-API-Key": self.admin_key},
            )
            tracks = resp.json().get("data", [])
        except Exception as e:
            logger.error("[%s] Failed to fetch tracks from API: %s", self.PLATFORM, e)
            return []

        all_points: list[RawDataPoint] = []
        snapshot = date.today()

        for track in tracks:
            entity = track.get("entity", {})
            title = entity.get("name", "")
            artist = entity.get("artist", {}).get("name", "")

            if not title or not artist:
                continue

            # Check if we already have lyrics data in signals
            platforms = track.get("scores", {}).get("platforms", {})
            if "genius" in platforms:
                continue  # Already enriched

            try:
                lyrics_data = await self._fetch_lyrics(title, artist)
                if lyrics_data:
                    point = RawDataPoint(
                        platform="genius",
                        entity_type="track",
                        entity_identifier={
                            "title": title,
                            "artist_name": artist,
                            "spotify_id": entity.get("platform_ids", {}).get("spotify"),
                            "isrc": entity.get("isrc"),
                        },
                        raw_score=lyrics_data.get("vocabulary_richness", 0) * 100,
                        rank=None,
                        signals=lyrics_data,
                        snapshot_date=snapshot,
                    )
                    all_points.append(point)
                    logger.info("[%s] Got lyrics for: %s - %s", self.PLATFORM, artist, title)

            except Exception as e:
                logger.debug("[%s] Failed to get lyrics for %s - %s: %s", self.PLATFORM, artist, title, e)

            await asyncio.sleep(2)  # Be respectful to Genius

        logger.info("[%s] Collected lyrics data for %d tracks", self.PLATFORM, len(all_points))
        return all_points

    async def _fetch_lyrics(self, title: str, artist: str) -> dict[str, Any] | None:
        """Search Genius for a song and extract lyrics + features."""
        # Search for the song
        async with self._semaphore:
            await asyncio.sleep(1)
            try:
                resp = await self._rate_limited_request(
                    "GET",
                    f"{self.API_BASE}/search",
                    headers={"Authorization": f"Bearer {self.access_token}"},
                    params={"q": f"{title} {artist}"},
                )
            except httpx.HTTPStatusError:
                return None

        data = resp.json()
        hits = data.get("response", {}).get("hits", [])

        if not hits:
            return None

        # Find best match
        song_url = None
        song_title = None
        for hit in hits[:3]:
            result = hit.get("result", {})
            result_artist = result.get("primary_artist", {}).get("name", "").lower()
            result_title = result.get("title", "").lower()

            # Fuzzy match: artist name should overlap
            if artist.lower().split()[0] in result_artist or result_artist.split()[0] in artist.lower():
                song_url = result.get("url")
                song_title = result.get("title")
                break

        if not song_url:
            # Fall back to first result
            song_url = hits[0].get("result", {}).get("url")
            song_title = hits[0].get("result", {}).get("title")

        if not song_url:
            return None

        # Scrape lyrics from the page
        async with self._semaphore:
            await asyncio.sleep(1.5)
            try:
                resp = await self.client.get(
                    song_url,
                    headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
                    follow_redirects=True,
                )
                if resp.status_code != 200:
                    return None
            except Exception:
                return None

        lyrics = self._extract_lyrics_from_html(resp.text)
        if not lyrics:
            return None

        # Analyze lyrics
        features = self._analyze_lyrics(lyrics)
        features["genius_url"] = song_url
        features["genius_title"] = song_title
        features["has_lyrics"] = True

        return features

    def _extract_lyrics_from_html(self, html: str) -> str | None:
        """Extract lyrics text from Genius song page HTML."""
        soup = BeautifulSoup(html, "html.parser")

        # Genius uses data-lyrics-container="true" for lyrics divs
        lyrics_containers = soup.find_all("div", {"data-lyrics-container": "true"})
        if lyrics_containers:
            lines = []
            for container in lyrics_containers:
                # Replace <br> with newlines
                for br in container.find_all("br"):
                    br.replace_with("\n")
                lines.append(container.get_text())
            return "\n".join(lines).strip()

        # Fallback: look for Lyrics__Container class
        containers = soup.find_all("div", class_=re.compile(r"Lyrics__Container"))
        if containers:
            lines = []
            for container in containers:
                for br in container.find_all("br"):
                    br.replace_with("\n")
                lines.append(container.get_text())
            return "\n".join(lines).strip()

        return None

    def _analyze_lyrics(self, lyrics: str) -> dict[str, Any]:
        """Extract features from lyrics text."""
        # Clean lyrics
        clean = re.sub(r"\[.*?\]", "", lyrics)  # Remove section headers [Verse 1], etc.
        clean = clean.strip()
        lines = [l.strip() for l in clean.split("\n") if l.strip()]
        words = clean.lower().split()

        # Basic stats
        word_count = len(words)
        line_count = len(lines)
        unique_words = len(set(words))
        vocabulary_richness = unique_words / word_count if word_count > 0 else 0

        # Section detection from brackets
        sections = re.findall(r"\[(.*?)\]", lyrics)
        section_types = []
        for s in sections:
            s_lower = s.lower()
            if "verse" in s_lower:
                section_types.append("verse")
            elif "chorus" in s_lower or "hook" in s_lower:
                section_types.append("chorus")
            elif "bridge" in s_lower:
                section_types.append("bridge")
            elif "intro" in s_lower:
                section_types.append("intro")
            elif "outro" in s_lower:
                section_types.append("outro")
            elif "pre" in s_lower:
                section_types.append("pre-chorus")
            else:
                section_types.append("other")

        # Chorus repetition ratio
        chorus_count = section_types.count("chorus")
        total_sections = len(section_types) if section_types else 1
        chorus_ratio = chorus_count / total_sections

        # Theme detection
        lyrics_lower = clean.lower()
        themes = {}
        for theme, keywords in THEME_KEYWORDS.items():
            count = sum(lyrics_lower.count(kw) for kw in keywords)
            if count > 0:
                themes[theme] = count

        # Top 3 themes
        sorted_themes = sorted(themes.items(), key=lambda x: x[1], reverse=True)
        top_themes = [t[0] for t in sorted_themes[:3]]
        primary_theme = top_themes[0] if top_themes else "other"

        # Language detection (simple heuristic)
        common_english = {"the", "and", "is", "in", "to", "of", "a", "i", "you", "it"}
        english_count = sum(1 for w in words[:50] if w in common_english)
        likely_english = english_count > 3

        return {
            "word_count": word_count,
            "line_count": line_count,
            "unique_words": unique_words,
            "vocabulary_richness": round(vocabulary_richness, 3),
            "section_structure": section_types,
            "section_count": len(section_types),
            "chorus_ratio": round(chorus_ratio, 3),
            "verse_count": section_types.count("verse"),
            "chorus_count": chorus_count,
            "has_bridge": "bridge" in section_types,
            "themes": top_themes,
            "primary_theme": primary_theme,
            "theme_scores": {k: v for k, v in sorted_themes[:5]},
            "likely_english": likely_english,
            "enrichment_source": "genius",
        }
