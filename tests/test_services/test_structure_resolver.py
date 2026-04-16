"""
Structure resolver + blender tests (task #109 Phase 2, PRD §70).

Locked blend rule from planning/NEXT_SESSION_START_HERE.md §3:
  For each section name (Intro, Verse, Chorus, ...) take the artist's
  bar count + vocals flag if the artist specified it; otherwise keep
  the genre's. Artist-only sections are inserted in the order they
  appear in the artist template; genre-only sections stay in place.

The resolver is split into:
  - blend(genre_struct, artist_template) — pure function
  - resolve_structure_for_song(db, artist, primary_genre) — async DB lookup
"""
from __future__ import annotations

import pytest

from api.services.structure_resolver import blend


# --- blend (pure function, no DB) -----------------------------------------

def test_blend_artist_only_template_returns_artist_struct_unchanged():
    """When the artist template is None, blend is undefined — caller
    should never invoke blend in that case. This test asserts the
    short-circuit: empty artist template returns genre untouched."""
    genre = [{"name": "Intro", "bars": 8, "vocals": False},
             {"name": "Verse", "bars": 16, "vocals": True}]
    assert blend(genre, []) == genre


def test_blend_artist_overrides_named_section_bars_and_vocals():
    """Artist 'Verse' override changes bars + vocals for every Verse
    in the genre struct, leaves other sections untouched."""
    genre = [
        {"name": "Intro", "bars": 8, "vocals": False},
        {"name": "Verse", "bars": 16, "vocals": True},
        {"name": "Chorus", "bars": 8, "vocals": True},
    ]
    artist = [{"name": "Verse", "bars": 12, "vocals": True}]
    result = blend(genre, artist)
    assert result == [
        {"name": "Intro", "bars": 8, "vocals": False},
        {"name": "Verse", "bars": 12, "vocals": True},
        {"name": "Chorus", "bars": 8, "vocals": True},
    ]


def test_blend_artist_override_applies_to_all_occurrences_of_same_name():
    """Pop has Chorus appearing 3x. Artist 'Chorus 12' must replace
    bars/vocals for ALL three Chorus rows."""
    genre = [
        {"name": "Intro", "bars": 8, "vocals": False},
        {"name": "Verse", "bars": 16, "vocals": True},
        {"name": "Chorus", "bars": 8, "vocals": True},
        {"name": "Verse", "bars": 16, "vocals": True},
        {"name": "Chorus", "bars": 8, "vocals": True},
        {"name": "Chorus", "bars": 16, "vocals": True},
    ]
    artist = [{"name": "Chorus", "bars": 12, "vocals": True}]
    result = blend(genre, artist)
    chorus_bars = [s["bars"] for s in result if s["name"] == "Chorus"]
    assert chorus_bars == [12, 12, 12]
    # Verses untouched
    verse_bars = [s["bars"] for s in result if s["name"] == "Verse"]
    assert verse_bars == [16, 16]


def test_blend_artist_only_section_appended_in_artist_declared_order():
    """Artist adds Outro that's not in the genre — Outro is appended
    at the end. Multiple artist-only sections preserve their order."""
    genre = [{"name": "Intro", "bars": 8, "vocals": False},
             {"name": "Verse", "bars": 16, "vocals": True}]
    artist = [
        {"name": "Outro", "bars": 16, "vocals": False},
        {"name": "Tag", "bars": 4, "vocals": True},
    ]
    result = blend(genre, artist)
    assert [s["name"] for s in result] == ["Intro", "Verse", "Outro", "Tag"]
    assert result[2] == {"name": "Outro", "bars": 16, "vocals": False}
    assert result[3] == {"name": "Tag", "bars": 4, "vocals": True}


def test_blend_genre_only_section_stays_in_place():
    """Genre has Bridge that the artist doesn't mention — Bridge stays
    where the genre put it, with the genre's bars/vocals."""
    genre = [
        {"name": "Verse", "bars": 16, "vocals": True},
        {"name": "Bridge", "bars": 8, "vocals": True},
        {"name": "Chorus", "bars": 8, "vocals": True},
    ]
    artist = [{"name": "Verse", "bars": 12, "vocals": True}]
    result = blend(genre, artist)
    assert result == [
        {"name": "Verse", "bars": 12, "vocals": True},
        {"name": "Bridge", "bars": 8, "vocals": True},
        {"name": "Chorus", "bars": 8, "vocals": True},
    ]


def test_blend_combined_override_plus_addition():
    """Artist overrides Chorus AND adds an Outro — both behaviors
    compose correctly."""
    genre = [
        {"name": "Intro", "bars": 8, "vocals": False},
        {"name": "Verse", "bars": 16, "vocals": True},
        {"name": "Chorus", "bars": 8, "vocals": True},
    ]
    artist = [
        {"name": "Chorus", "bars": 16, "vocals": True},
        {"name": "Outro", "bars": 8, "vocals": False},
    ]
    result = blend(genre, artist)
    assert result == [
        {"name": "Intro", "bars": 8, "vocals": False},
        {"name": "Verse", "bars": 16, "vocals": True},
        {"name": "Chorus", "bars": 16, "vocals": True},
        {"name": "Outro", "bars": 8, "vocals": False},
    ]


# --- resolve_structure_for_song (async, DB-backed) -------------------------

@pytest.mark.asyncio
async def test_resolve_returns_genre_struct_when_artist_has_no_template(db_session):
    """artist.structure_template is None -> genre row resolves untouched
    via genre_structures_service.resolve_genre_structure (chain walks
    pop.k-pop -> pop)."""
    from api.services.structure_resolver import resolve_structure_for_song
    artist = {"structure_template": None, "genre_structure_override": False}
    resolved = await resolve_structure_for_song(
        db_session, artist=artist, primary_genre="pop",
    )
    # 'pop' is seeded with 10 sections per migration 033
    assert len(resolved) == 10
    assert resolved[0]["name"] == "Intro"


@pytest.mark.asyncio
async def test_resolve_returns_artist_template_unchanged_when_override(db_session):
    """genre_structure_override=true -> use artist template as-is, ignore genre."""
    from api.services.structure_resolver import resolve_structure_for_song
    custom = [
        {"name": "Voicemail Intro", "bars": 16, "vocals": False},
        {"name": "Verse", "bars": 8, "vocals": True},
    ]
    artist = {"structure_template": custom, "genre_structure_override": True}
    resolved = await resolve_structure_for_song(
        db_session, artist=artist, primary_genre="pop",
    )
    assert resolved == custom


@pytest.mark.asyncio
async def test_resolve_blends_when_template_present_and_override_false(db_session):
    """artist has template but override=false -> blend with genre row.
    Use 'rock' seed (which has a Solo section). Artist swaps Chorus
    bar count and adds an Outro override that already exists -> outro
    bars come from the artist."""
    from api.services.structure_resolver import resolve_structure_for_song
    artist_template = [
        {"name": "Outro", "bars": 32, "vocals": False},  # rock has Outro 8
    ]
    artist = {
        "structure_template": artist_template,
        "genre_structure_override": False,
    }
    resolved = await resolve_structure_for_song(
        db_session, artist=artist, primary_genre="rock",
    )
    # Rock seed has 9 sections; blend should preserve count (Outro is
    # in genre too, so artist override is in-place not appended)
    assert len(resolved) == 9
    # Outro bars overridden by artist
    outros = [s for s in resolved if s["name"] == "Outro"]
    assert len(outros) == 1
    assert outros[0]["bars"] == 32
    # Solo from rock genre is still there (genre-only section stays)
    assert any(s["name"] == "Solo" for s in resolved)
