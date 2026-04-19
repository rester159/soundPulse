"""
Wikipedia inline research for genre blueprints (#30).

Hits the Wikipedia REST + search APIs directly (no browser needed) to
ground the LLM's blueprint-research call in real article text. Free,
zero auth, ~500ms latency.

Two-step:
  1. /api/rest_v1/page/summary or /w/api.php opensearch — find the
     best-matching article title for the genre id.
  2. /api/rest_v1/page/summary/{title} — fetch the lead-section extract
     (~1-2 paragraphs of clean prose).

For genre ids like "hip-hop.boom-bap.east-coast" we transform to a
human search query like "East Coast hip hop" before searching, then
also try the parents ("Boom bap", "Hip hop") so deeper subgenres still
get useful grounding even if their exact article doesn't exist.

Returns a single concatenated string the caller passes to the LLM as
context. Empty string if Wikipedia has nothing useful.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Iterable

import httpx

logger = logging.getLogger(__name__)

WP_BASE = "https://en.wikipedia.org"
WP_SUMMARY_PATH = "/api/rest_v1/page/summary/{title}"
WP_SEARCH_PATH = "/w/api.php"

# Words we strip when turning a genre id into a human query — hyphens,
# dots, and common qualifiers don't help search relevance.
def _genre_id_to_queries(genre_id: str) -> list[str]:
    """Yield candidate Wikipedia search queries for the genre, ordered
    most-specific first.

    For "hip-hop.boom-bap.east-coast":
      → ["east coast hip hop", "boom bap hip hop",
         "east coast boom bap hip hop", "boom bap", "east coast",
         "hip hop", "east coast music genre"]

    The pattern that works best is "<level> + <root>" — Wikipedia
    titles articles "East Coast hip hop" and "Boom bap", not the
    SoundPulse dotted form.
    """
    if not genre_id:
        return []
    parts = [p.strip().replace("-", " ") for p in genre_id.split(".") if p.strip()]
    if not parts:
        return []
    root = parts[0]
    leaf = parts[-1]
    queries: list[str] = []

    # 1. Each non-root level paired with the root: "east coast hip hop",
    #    "boom bap hip hop". This is the search Wikipedia handles best.
    for level in parts[1:]:
        q = f"{level} {root}".strip()
        if q and q not in queries:
            queries.append(q)
    # 2. Full reversed chain: "east coast boom bap hip hop"
    full = " ".join(reversed(parts))
    if full not in queries:
        queries.append(full)
    # 3. Each level by itself, leaf to root.
    for level in reversed(parts):
        if level not in queries:
            queries.append(level)
    # 4. Music-disambiguating qualifier on the leaf (handles "garage",
    #    "house", "trance" etc that have non-music meanings)
    if len(parts) > 1 and f"{leaf} music genre" not in queries:
        queries.append(f"{leaf} music genre")
    # Dedup preserving order
    seen = set()
    out = []
    for q in queries:
        ql = q.lower()
        if ql in seen:
            continue
        seen.add(ql)
        out.append(q)
    return out


async def _wp_search(client: httpx.AsyncClient, query: str, limit: int = 3) -> list[str]:
    """Return a list of candidate article titles for `query`."""
    try:
        r = await client.get(
            f"{WP_BASE}{WP_SEARCH_PATH}",
            params={
                "action": "opensearch",
                "search": query,
                "limit": limit,
                "namespace": 0,
                "format": "json",
            },
        )
        r.raise_for_status()
        data = r.json()
        # OpenSearch returns [query, [titles...], [descs...], [urls...]]
        titles = data[1] if isinstance(data, list) and len(data) > 1 else []
        return [t for t in titles if isinstance(t, str)]
    except Exception:
        logger.exception("[wp-research] search failed for %r", query)
        return []


_GENRE_MARKERS = (
    "genre of", "music genre", "subgenre", "style of",
    "musical style", "musical movement", "form of music",
    "is a genre", "music originated", "music developed",
    "originated in", "music characterized", "characterized by a",
    "is characterized by", "music that emerged", "music emerged",
    "music played", "music performed", "tempo of", "beats per minute",
    "music scene",
)
# Hard reject — pages that LOOK musical but are about a person, band,
# album, song, or place rather than a genre.
_NON_GENRE_MARKERS = (
    "is a band", "is an american musical duo", "is a british musical duo",
    "is a duo", "is a singer", "is a rapper", "is a songwriter",
    "is a record producer", "is a music producer", "is a dj",
    "is an album", "is a song",
)


async def _wp_summary(client: httpx.AsyncClient, title: str) -> str:
    """Return the lead-section extract for `title`, or '' if the page
    doesn't look like a music genre / style article."""
    try:
        r = await client.get(
            f"{WP_BASE}/api/rest_v1/page/summary/{title.replace(' ', '_')}",
        )
        if r.status_code == 404:
            return ""
        r.raise_for_status()
        data = r.json()
        if data.get("type") == "disambiguation":
            return ""
        extract = (data.get("extract") or "").strip()
        if not extract:
            return ""
        low = extract.lower()
        # Hard rejects first — bands, artists, songs, albums, places.
        if any(m in low for m in _NON_GENRE_MARKERS):
            return ""
        # Otherwise accept if any genre marker is present, OR if the
        # title itself contains 'music' (e.g. "House music", "Bluegrass
        # music") which is the canonical Wikipedia naming pattern for
        # music-genre articles.
        title_low = title.lower()
        if (any(m in low for m in _GENRE_MARKERS)
                or " music" in title_low or title_low.endswith("music")):
            return f"[{title}]\n{extract}"
        return ""
    except Exception:
        logger.exception("[wp-research] summary failed for %r", title)
        return ""


async def fetch_wikipedia_context(
    genre_id: str,
    *,
    max_articles: int = 3,
    timeout_s: float = 6.0,
) -> str:
    """Look up `genre_id` on Wikipedia, return up to `max_articles`
    article extracts concatenated as context for an LLM call. Empty
    string if nothing music-relevant is found."""
    if not genre_id or not genre_id.strip():
        return ""
    queries = _genre_id_to_queries(genre_id)
    seen_titles: set[str] = set()
    extracts: list[str] = []

    timeout = httpx.Timeout(timeout_s)
    async with httpx.AsyncClient(
        timeout=timeout,
        headers={"User-Agent": "SoundPulse-Research/1.0 (https://soundpulse.app)"},
    ) as client:
        for q in queries:
            if len(extracts) >= max_articles:
                break
            titles = await _wp_search(client, q, limit=2)
            for t in titles:
                if t in seen_titles or len(extracts) >= max_articles:
                    continue
                seen_titles.add(t)
                summary = await _wp_summary(client, t)
                if summary:
                    extracts.append(summary)

    if not extracts:
        return ""
    return "\n\n".join(extracts)
