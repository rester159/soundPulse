"""
Genius lyrics enricher — Layer 5 of the Breakout Analysis Engine.

Pulls tracks needing lyrics from /admin/tracks/needing-lyrics, searches
Genius for each, scrapes the lyrics page, extracts features (word count,
themes via keyword matching, section structure), and bulk-POSTs to
/admin/lyrics/bulk which writes to the track_lyrics table.

Prioritizes breakout tracks (the queue endpoint orders by is_breakout DESC),
since those feed the LLM lyrical analysis in Layer 6.

Rate limit: ~1 track per 3-4 seconds (Genius search + page scrape +
respectful delay). At ~1000 tracks per run × 3.5s = ~58 min per run.
12h cadence drains a 5,000-track backlog in ~30 hours.
"""
from __future__ import annotations

import asyncio
import logging
import re
import uuid as uuid_mod
from datetime import date, datetime, timezone
from typing import Any

import httpx
from bs4 import BeautifulSoup

from scrapers.base import AuthenticationError, BaseScraper, RawDataPoint

logger = logging.getLogger(__name__)


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

QUEUE_ENDPOINT = "/api/v1/admin/tracks/needing-lyrics"
BULK_INGEST_ENDPOINT = "/api/v1/admin/lyrics/bulk"
PAGE_SIZE = 50
MAX_TRACKS_PER_RUN = 1000
BULK_BATCH_SIZE = 25
REQUEST_DELAY = 2.5  # Be respectful to Genius


class GeniusLyricsScraper(BaseScraper):
    PLATFORM = "genius"
    API_BASE = "https://api.genius.com"

    def __init__(self, credentials: dict, api_base_url: str, admin_key: str):
        super().__init__(credentials, api_base_url, admin_key)
        self.access_token: str = credentials.get("api_key", "")
        self._semaphore = asyncio.Semaphore(1)  # serial — be polite
        self._buffer: list[dict[str, Any]] = []
        self._stats: dict[str, int] = {
            "tracks_fetched": 0,
            "lyrics_found": 0,
            "lyrics_missing": 0,
            "errors": 0,
            "bulk_flushes": 0,
        }

    async def authenticate(self) -> None:
        if not self.access_token:
            raise AuthenticationError("Genius API token not configured (GENIUS_API_KEY)")
        logger.info("[genius] using configured API token")

    async def collect_trending(self) -> list[RawDataPoint]:
        await self._enrich_all()
        return []

    async def collect_entity_details(self, entity_id: str) -> dict:
        return {"error": "genius_lyrics does not support entity detail"}

    async def run(self) -> dict[str, int]:
        try:
            await self.authenticate()
            await self._enrich_all()
            await self._flush_buffer()
            logger.info("[genius] complete: %s", self._stats)
            return {"total": self._stats["lyrics_found"], **self._stats}
        finally:
            await self.close()

    # ---- Main loop ----

    async def _enrich_all(self) -> None:
        offset = 0
        processed = 0
        while processed < MAX_TRACKS_PER_RUN:
            page = await self._fetch_queue_page(offset=offset)
            if not page:
                logger.info("[genius] queue empty at offset=%d, stopping", offset)
                break
            logger.info(
                "[genius] page offset=%d size=%d processed=%d",
                offset, len(page), processed,
            )

            for i, track in enumerate(page):
                title = track.get("title")
                artist = track.get("artist_name")
                track_id = track.get("track_id")

                if not title or not artist or not track_id:
                    self._stats["errors"] += 1
                    continue

                self._stats["tracks_fetched"] += 1

                try:
                    lyrics_data = await self._fetch_lyrics(title, artist)
                except Exception as exc:
                    logger.warning(
                        "[genius] fetch failed for %s — %s: %s",
                        artist, title, str(exc)[:120],
                    )
                    self._stats["errors"] += 1
                    continue

                if not lyrics_data:
                    self._stats["lyrics_missing"] += 1
                    continue

                lyrics_data["track_id"] = track_id
                self._buffer.append(lyrics_data)
                self._stats["lyrics_found"] += 1

                if len(self._buffer) >= BULK_BATCH_SIZE:
                    await self._flush_buffer()

                if (processed + i + 1) % 10 == 0:
                    logger.info(
                        "[genius] progress: fetched=%d found=%d missing=%d errors=%d",
                        self._stats["tracks_fetched"],
                        self._stats["lyrics_found"],
                        self._stats["lyrics_missing"],
                        self._stats["errors"],
                    )

            processed += len(page)
            if len(page) < PAGE_SIZE:
                break
            offset += PAGE_SIZE

    async def _fetch_queue_page(self, *, offset: int) -> list[dict[str, Any]]:
        url = f"{self.api_base_url}{QUEUE_ENDPOINT}"
        try:
            resp = await self.client.get(
                url,
                params={"limit": PAGE_SIZE, "offset": offset},
                headers={"X-API-Key": self.admin_key},
                timeout=60.0,
            )
            if resp.status_code != 200:
                logger.warning("[genius] queue HTTP %d offset=%d", resp.status_code, offset)
                return []
            return resp.json().get("data", [])
        except httpx.HTTPError as exc:
            logger.warning("[genius] queue fetch failed offset=%d: %s", offset, exc)
            return []

    # ---- Genius search + lyrics scrape ----

    async def _fetch_lyrics(self, title: str, artist: str) -> dict[str, Any] | None:
        async with self._semaphore:
            await asyncio.sleep(REQUEST_DELAY)
            try:
                resp = await self._rate_limited_request(
                    "GET",
                    f"{self.API_BASE}/search",
                    headers={"Authorization": f"Bearer {self.access_token}"},
                    params={"q": f"{title} {artist}"},
                )
            except httpx.HTTPStatusError:
                return None
            except Exception:
                return None

        try:
            data = resp.json()
        except Exception:
            return None
        hits = (data.get("response") or {}).get("hits") or []
        if not hits:
            return None

        # Pick the best match: artist name overlap
        chosen = None
        for hit in hits[:5]:
            result = hit.get("result") or {}
            result_artist = (result.get("primary_artist") or {}).get("name", "").lower()
            if artist.lower().split()[0] in result_artist or result_artist.split()[0] in artist.lower():
                chosen = result
                break
        if not chosen:
            chosen = (hits[0] or {}).get("result")
        if not chosen:
            return None

        song_url = chosen.get("url")
        song_id = str(chosen.get("id") or "")
        if not song_url:
            return None

        # Scrape the lyrics page
        async with self._semaphore:
            await asyncio.sleep(REQUEST_DELAY)
            try:
                page_resp = await self.client.get(
                    song_url,
                    headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
                    follow_redirects=True,
                    timeout=30.0,
                )
                if page_resp.status_code != 200:
                    return None
            except Exception:
                return None

        lyrics = self._extract_lyrics_from_html(page_resp.text)
        if not lyrics:
            return None

        features = self._analyze_lyrics(lyrics)
        features["lyrics_text"] = lyrics
        features["genius_url"] = song_url
        features["genius_song_id"] = song_id
        return features

    def _extract_lyrics_from_html(self, html: str) -> str | None:
        soup = BeautifulSoup(html, "html.parser")
        containers = soup.find_all("div", {"data-lyrics-container": "true"})
        if not containers:
            containers = soup.find_all("div", class_=re.compile(r"Lyrics__Container"))
        if not containers:
            return None
        lines = []
        for container in containers:
            for br in container.find_all("br"):
                br.replace_with("\n")
            lines.append(container.get_text())
        text = "\n".join(lines).strip()
        return text if text else None

    def _analyze_lyrics(self, lyrics: str) -> dict[str, Any]:
        clean = re.sub(r"\[.*?\]", "", lyrics).strip()
        lines = [l.strip() for l in clean.split("\n") if l.strip()]
        words = clean.lower().split()
        word_count = len(words)
        unique_words = len(set(words))
        vocab = unique_words / word_count if word_count > 0 else 0

        sections_raw = re.findall(r"\[(.*?)\]", lyrics)
        sections = []
        for s in sections_raw:
            sl = s.lower()
            if "verse" in sl: sections.append("verse")
            elif "chorus" in sl or "hook" in sl: sections.append("chorus")
            elif "bridge" in sl: sections.append("bridge")
            elif "intro" in sl: sections.append("intro")
            elif "outro" in sl: sections.append("outro")
            elif "pre" in sl: sections.append("pre-chorus")
            else: sections.append("other")

        lyrics_lower = clean.lower()
        themes = {}
        for theme, kws in THEME_KEYWORDS.items():
            cnt = sum(lyrics_lower.count(kw) for kw in kws)
            if cnt > 0:
                themes[theme] = cnt
        sorted_themes = sorted(themes.items(), key=lambda x: x[1], reverse=True)
        top_themes = [t[0] for t in sorted_themes[:3]]
        primary_theme = top_themes[0] if top_themes else None

        common_english = {"the", "and", "is", "in", "to", "of", "a", "i", "you", "it"}
        english_count = sum(1 for w in words[:50] if w in common_english)
        language = "en" if english_count > 3 else "other"

        return {
            "word_count": word_count,
            "line_count": len(lines),
            "vocabulary_richness": round(vocab, 3),
            "section_structure": sections,
            "themes": top_themes,
            "primary_theme": primary_theme,
            "language": language,
            "features_json": {
                "theme_scores": dict(sorted_themes[:5]),
                "section_count": len(sections),
                "verse_count": sections.count("verse"),
                "chorus_count": sections.count("chorus"),
                "has_bridge": "bridge" in sections,
            },
        }

    # ---- Bulk persistence ----

    async def _flush_buffer(self) -> None:
        if not self._buffer:
            return
        url = f"{self.api_base_url}{BULK_INGEST_ENDPOINT}"
        while self._buffer:
            chunk = self._buffer[: BULK_BATCH_SIZE]
            self._buffer = self._buffer[BULK_BATCH_SIZE :]
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
                        "[genius] bulk: received=%d inserted=%d skipped=%d errors=%d",
                        body.get("received", 0), body.get("inserted", 0),
                        body.get("skipped", 0), body.get("errors", 0),
                    )
                else:
                    logger.error(
                        "[genius] bulk HTTP %d: %s",
                        resp.status_code, resp.text[:200],
                    )
            except httpx.HTTPError as exc:
                logger.error("[genius] bulk error: %s", exc)
