"""
Structure resolver — combines a per-genre default (from `genre_structures`)
with optional per-artist overrides on `ai_artists.structure_template` /
`genre_structure_override`. Output feeds `structure_prompt.format_structure_for_suno`
which prepends the [Section: N bars{, instrumental}] tag block to the
final Suno generation prompt.

Locked blend semantics (planning/NEXT_SESSION_START_HERE.md §3, confirmed
by user 2026-04-15 22:28):

  For each section name (Intro, Verse, Chorus, ...) take the artist's
  bar count + vocals flag if the artist specified it; otherwise keep
  the genre's. Artist-only sections are inserted in the order they
  appear in the artist template; genre-only sections stay in place.

The override is applied to ALL occurrences of a name in the genre row.
Pop's three Choruses with bar counts [8, 8, 16] all become 12 if the
artist says {Chorus: 12} — that matches "an artist's Chorus is 12 bars"
intent. If you ever want per-occurrence overrides we'd need to add a
positional key (Chorus 1, Chorus 2) — out of scope for MVP.
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from api.services.genre_structures_service import resolve_genre_structure

logger = logging.getLogger(__name__)


def blend(genre_struct: list[dict], artist_template: list[dict] | None) -> list[dict]:
    """Apply the locked blend rule. Pure function, no I/O.

    Returns a fresh list of new section dicts — does not mutate inputs.
    """
    if not artist_template:
        # Defensive: caller should already short-circuit when there's no
        # template, but if they don't, return the genre struct verbatim.
        return [dict(s) for s in genre_struct]

    # Map artist section name -> {bars, vocals} for the override lookup.
    # If the artist lists the same name twice, the LAST entry wins for
    # the override values, but ALL artist-only entries are tracked for
    # the append step below.
    artist_overrides: dict[str, dict[str, Any]] = {}
    for sec in artist_template:
        artist_overrides[sec["name"]] = {"bars": sec["bars"], "vocals": sec["vocals"]}

    # Apply overrides to genre sections in place.
    blended: list[dict] = []
    genre_section_names: set[str] = set()
    for gsec in genre_struct:
        name = gsec["name"]
        genre_section_names.add(name)
        if name in artist_overrides:
            override = artist_overrides[name]
            blended.append({
                "name": name,
                "bars": override["bars"],
                "vocals": override["vocals"],
            })
        else:
            blended.append(dict(gsec))

    # Append artist-only sections in artist-declared order. Skip names
    # the genre already covers (those were applied as overrides above).
    for asec in artist_template:
        if asec["name"] not in genre_section_names:
            blended.append({
                "name": asec["name"],
                "bars": asec["bars"],
                "vocals": asec["vocals"],
            })

    return blended


async def resolve_structure_for_song(
    db: AsyncSession,
    *,
    artist: dict | Any,
    primary_genre: str,
) -> list[dict]:
    """Resolve the final structure for a (artist, genre) pair.

    Order:
      1. Look up the genre row via genre_structures_service (handles
         dotted-chain fallback, falls back to 'pop').
      2. If artist has no structure_template, return genre struct.
      3. If artist has override=True, return artist template as-is.
      4. Otherwise blend per the locked rule.

    Accepts `artist` as either a dict or an ORM row — read-only access
    via the helper below so this function works in both call paths
    (admin route loading ORM rows vs unit tests passing dicts).
    """
    template = _artist_attr(artist, "structure_template")
    override = bool(_artist_attr(artist, "genre_structure_override"))

    resolved = await resolve_genre_structure(db, primary_genre)
    genre_struct = resolved.structure

    if not template:
        return genre_struct
    if override:
        return [dict(s) for s in template]
    return blend(genre_struct, template)


def _artist_attr(artist: dict | Any, key: str) -> Any:
    if isinstance(artist, dict):
        return artist.get(key)
    return getattr(artist, key, None)
