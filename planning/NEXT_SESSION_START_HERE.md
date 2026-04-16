# START HERE — next session entry point

> Last handoff: **2026-04-15 20:09** — end of session `7224c6fe`.
> Point the next model at this file first. Read it top-to-bottom before touching code.

---

## 1. What the human wants next (load-bearing)

**Build `task #109`: Per-genre song structure rules.** Inject universal, genre-specific section-tag structures into every Suno/Kie song-generation prompt so the output has predictable bar counts per section. Editable via Settings.

This is **the pivot from a DTW-alignment rabbit-hole.** The human explicitly dropped DTW after realising that structural mismatches (e.g., Suno writing a 4-bar intro when the human instrumental has a 20-bar intro) can't be solved by time-warping — DTW only helps when both sequences contain the same content with different timing. Fix at the source by prompting Suno with an explicit structure.

---

## 2. Design decisions already locked (do not re-litigate)

| # | Question | Answer |
|---|---|---|
| 1 | Genre granularity | **Primary genre only** (not subgenre) — simpler, avoids combinatorial explosion |
| 2 | Storage | **DB table** (not JSON file on disk) — editable from Settings UI without a redeploy |
| 3 | Structure spec per entry | **Minimum:** `[{name, bars, vocals: bool}]` list — add tempo/energy fields later only if needed |
| 4 | Coverage | **Top 20 genres** — cross-check keys against `shared/genre_taxonomy.py` (or wherever the canonical taxonomy lives) before seeding |
| 5 | Settings UI placement | **New dedicated subtab** in `/settings` (not shoehorned into an existing tab) |
| 6 | Version history | **Not for MVP** — only `updated_at` and `updated_by` columns. Add history later if A/B testing matters |
| 7 | Artist template interaction | **Blend by default**; per-artist checkbox `genre_structure_override` (default `FALSE`) skips the blend and uses the artist template as-is |

---

## 3. The ONE open question (ask before writing code)

**Blend semantic confirmation.** I proposed:

> For each section name (Intro, Verse, Chorus, …) take the artist's bar count and vocals flag if the artist specified it; otherwise keep the genre's. Artist-only sections are inserted in the order they appear in the artist template; genre-only sections stay in place.

**Rationale for this rule:** it lets an artist shorten/lengthen a named section, drop a section they never use, or add a signature section (e.g., `Outro: 16 bars with voicemail sample`) without redefining the whole structure. Rejected alternative: weighted averages on bar counts — musically meaningless.

**Ask the user to confirm this blend rule before starting Phase 2.** If they pick something different, the resolver in Phase 2 changes shape, so confirmation must come first.

---

## 4. Six-phase execution plan (TDD — failing test first in every phase)

### Phase 1 — Schema + seed (backend)

Two Alembic migrations:

**`alembic/versions/033_genre_structures.py`** — new table:
```sql
CREATE TABLE genre_structures (
  primary_genre TEXT PRIMARY KEY,
  structure JSONB NOT NULL,               -- list[{name, bars, vocals}]
  notes TEXT,                             -- 1-line rationale
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_by TEXT
);
```

**`alembic/versions/034_artist_structure_fields.py`** — two new columns on `ai_artists`:
```sql
ALTER TABLE ai_artists
  ADD COLUMN structure_template JSONB,           -- null = artist has no custom structure
  ADD COLUMN genre_structure_override BOOLEAN NOT NULL DEFAULT FALSE;
```

**Seed 20 genres in the 033 migration's `upgrade()`** with research-backed structures. Cross-check the 20 keys against `shared/genre_taxonomy.py` first — rename any that don't match the canonical spelling.

Target initial 20 (in priority order based on likely label output):
```
pop, k-pop, hip-hop, rap, r&b, dance-pop, edm, house, techno, trap, drill,
afrobeats, amapiano, latin-pop, reggaeton, indie-pop, rock, country,
lo-fi, ambient
```

Each seed row's `notes` should carry a 1-line justification (e.g., `"trap: 4-bar intro, 16-bar verse, 8-bar hook — ATL / 808 Mafia template"`).

**Tests (written first):**
- `tests/test_genre_structures_crud.py`:
  - upsert succeeds
  - lookup by primary_genre
  - fallback to `pop` when genre not in table
  - validation rejects `bars <= 0`
  - validation rejects empty `structure` array

### Phase 2 — Prompt injection (the load-bearing change)

New helper **`services/song_gen/structure_resolver.py`**:
```python
def resolve_structure_for_song(artist, primary_genre):
    genre_struct = lookup_genre_structure(primary_genre) or lookup_genre_structure("pop")
    if artist.structure_template is None:
        return genre_struct
    if artist.genre_structure_override:
        return artist.structure_template
    return blend(genre_struct, artist.structure_template)

def blend(genre_struct, artist_template):
    """Section-name merge. Artist wins on named matches; artist-only
    sections are inserted in artist-declared order; genre-only sections
    stay in place."""
    # implementation per the confirmed blend rule from §3 above
```

New helper **`services/song_gen/structure_prompt.py`**:
```python
def format_structure_for_suno(structure: list) -> str:
    """Turn [{"name":"Intro","bars":8,"vocals":false}, ...] into
    Suno section tag block:
        [Intro: 8 bars, instrumental]
        [Verse 1: 16 bars]
        [Pre-chorus: 4 bars]
        ...
    """
```

**Modify the song generation orchestrator** (likely `services/song_gen/orchestrator.py` — find via grep) to call the resolver, format, and prepend the tag block to `generation_prompt` before calling the Suno/Kie adapter.

**Tests (written first):**
- `tests/test_song_gen_structure_injection.py`:
  - resolver: genre-only path returns genre struct
  - resolver: artist + override → artist struct, genre ignored
  - resolver: artist + no override → blend runs
  - blend: artist shortens `Verse` → result has artist's bar count
  - blend: artist adds `Outro: 16` → appended at artist-declared position
  - blend: genre-only `Bridge` stays when artist omits it
  - prompt format: every section renders as `[Name: N bars{, instrumental}]`
  - full orchestrator: primary_genre='pop' → Suno adapter receives prompt starting with the tag block

### Phase 3 — Admin API

**`api/routers/admin_genre_structures.py`** (CRUD) wired into the admin router:
- `GET  /api/v1/admin/genre-structures` — list all
- `GET  /api/v1/admin/genre-structures/{primary_genre}` — one
- `PUT  /api/v1/admin/genre-structures/{primary_genre}` — upsert (validated via the Phase 1 validators)
- `DELETE /api/v1/admin/genre-structures/{primary_genre}` — remove

**Artist patch endpoint** (extend existing artist update route) — accept the two new fields: `structure_template` and `genre_structure_override`.

**Tests (written first):**
- `tests/test_admin_genre_structures_api.py`: CRUD, validation, 404 on unknown
- `tests/test_artist_structure_patch.py`: set template, toggle override

### Phase 4 — Settings UI + Artist profile UI

**New Settings subtab "Genre Structures":**
- Route it under the existing `/settings` page — new tab alongside existing ones
- Table view: one row per genre showing a compact section-chain summary, e.g., `Intro 8 → Verse 16 → Chorus 8 → Verse 16 → Chorus 8 → Bridge 8 → Chorus 16 → Outro 4`
- Click a row → inline or modal editor:
  - section list with add / remove / drag-reorder
  - per-section: name (text), bars (number), vocals (checkbox)
  - save / cancel buttons

**Artist profile additions:**
- New "Song Structure" section in the artist editor
- Checkbox: `Use artist template only (ignore genre blending)` — maps to `genre_structure_override`
- Tooltip on the checkbox (exact copy to ship):
  > When unchecked, this artist's song structure is blended with their primary genre's template — genre sets the skeleton, the artist can shorten/lengthen or add/remove named sections. When checked, the genre template is ignored entirely and the artist's custom structure is used as-is.
- Structure editor for the artist's own `structure_template` (reuse the genre editor component)

**New hooks in `frontend/src/hooks/useSoundPulse.js`:**
- `useGenreStructures()`, `useGenreStructure(primary_genre)`, `useUpdateGenreStructure()`

**Tests (written first):**
- Vitest + RTL:
  - Settings subtab renders 20 rows
  - Editor: add section → state includes it; remove → gone; drag reorder → new order persisted
  - Artist profile: checkbox toggles override; tooltip shows on hover
  - Save fires the expected mutation

### Phase 5 — Seed the 20 genres (runs inside Phase 1)

Do the research pass against well-documented pop / hip-hop / EDM / k-pop / Afrobeats / Latin song-form norms. Each of the 20 rows gets:
- A plausible default structure (length-realistic — pop ~3:30 after BPM=120 math, trap ~2:45, techno ~6:00 etc.)
- A `notes` line with the one-line rationale so the human can see why we picked it.

### Phase 6 — Regenerate Y3K with the new pipeline + measure compliance

- Re-run Y3K song generation via the orchestrator (now structure-injected)
- Fetch the new Suno output, run `librosa.beat` + duration math, verify each section's detected boundary lands within ±1 bar of the requested bar count
- Compare side-by-side against the old Y3K mix
- If structural compliance on Y3K is < 70 %, flag it and try: BPM pinning in the prompt, explicit bar-count-as-numbers phrasing (`16 bars` not `long`), `[Drop]` / `[Build]` style extra keywords, or a retry loop

**Gate:** only promote to pipeline default after Y3K hits ≥ 70 % compliance AND sounds better than the pre-change mix on an A/B listen.

---

## 5. What also landed this session (do not redo)

- **Commit `e3e4a9e`** — orange scratch pin `e.stopPropagation()` on keydown. Root cause: pin is a DOM child of the green voice block, so arrow keydown events bubbled up to the block's `onKeyDown` and both `setOrangePin` AND `setVoiceEntry` fired at the same time. Verified fix on REAL Y3K data via a full Playwright harness with mocked API.
- **Commit `f283959`** — `<meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">` added to `frontend/index.html`. Root cause of "I still see the old UI": Railway served the HTML shell with no cache-control headers, so Chrome's heuristic freshness cached it and the cached HTML kept pointing to stale bundle hashes even after rebuilds.
- **Commit `528230f`** — orange pin nested INSIDE the green voice block (was a sibling). `-top-1 -bottom-1` was getting clipped by the scroll wrapper's `overflow-y-hidden`. Knob is now fully inside the block vertically, spawn position is near the block's left edge so it's visible at any zoom level, + auto-scrolls into view on spawn.
- **Commit `b1ddfbc`** — added 7x and 10x zoom levels to the VocalEntryStudio timeline cycler.

**Task status updates in this session:**
- `#107` VocalEntryStudio UI → completed
- `#108` DTW vocal alignment prototype on Y3K → **deleted** (superseded by #109 — DTW can't fix structural mismatch, fix at source instead)
- `#109` Per-genre song structure rules → **pending** — this is what the next session picks up

---

## 6. Files the next session will touch (cheat sheet)

**Backend:**
- `alembic/versions/033_genre_structures.py` (new)
- `alembic/versions/034_artist_structure_fields.py` (new)
- `api/models/genre_structure.py` (new)
- `api/schemas/genre_structure.py` (new)
- `api/models/ai_artist.py` (add two columns)
- `api/routers/admin_genre_structures.py` (new)
- `api/routers/admin.py` (extend artist patch)
- `services/song_gen/structure_resolver.py` (new)
- `services/song_gen/structure_prompt.py` (new)
- `services/song_gen/orchestrator.py` (add injection call — find exact file via `grep -rn "generation_prompt" services/song_gen/`)

**Frontend:**
- `frontend/src/hooks/useSoundPulse.js` (add 3 hooks)
- `frontend/src/pages/Settings.jsx` (new subtab) — confirm actual page file name before editing
- `frontend/src/pages/Artists.jsx` (add structure section + checkbox + tooltip)
- New components: `frontend/src/components/GenreStructureEditor.jsx` (reusable for both genre and artist editors)

**Tests:**
- `tests/test_genre_structures_crud.py`
- `tests/test_song_gen_structure_injection.py`
- `tests/test_admin_genre_structures_api.py`
- `tests/test_artist_structure_patch.py`
- Vitest specs alongside the new React components

**Docs:**
- Add a section to `planning/PRD/SoundPulse_PRD_v3.md` describing the feature
- Update `planning/schema.md` with the two new migration additions
- Update `planning/tasks.md` to break `#109` into the 6 phases

---

## 7. Things to NOT do

- Do not implement DTW vocal alignment. The human explicitly dropped it in favour of structural prompting.
- Do not hardcode genre names anywhere outside the seed migration + `shared/genre_taxonomy.py`. Treat `primary_genre` strings as data, not constants.
- Do not build a version-history table for genre_structures. Explicitly out of scope for MVP.
- Do not touch the orange-pin code again — it's fixed and verified with a Playwright harness.
- Do not remove the cache-control meta tags from `frontend/index.html`.

---

## 8. Read-on-arrival

Before writing code, run:
1. `git log --oneline -20` — see recent commits
2. Read `planning/tasks.md` for the canonical backlog
3. Read `planning/lessons.md` latest entries (L012, L013, L014 from this session) — these prevent redoing mistakes
4. Read `planning/output.md` last 100 lines for this session's full context
5. Read `planning/PRD/SoundPulse_PRD_v3.md` section on per-genre structure rules (added this session)
6. Read `shared/genre_taxonomy.py` to confirm canonical genre keys before seeding

Then confirm the blend-semantic question from §3 with the user, then start Phase 1 tests.
