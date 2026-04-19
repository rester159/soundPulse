# Approved Database Schema

> Canonical schema reference. Mirrors `alembic/versions/` migrations 001–005 (current state) and documents the proposed Phase 3 additions.
>
> **Rule:** when a migration is added or changed, update this file in the same commit. Drift here = bugs later.

---

## Conventions

- All UUID PKs use `uuid-ossp` extension (enabled in 001).
- All timestamps are `TIMESTAMPTZ` with `server_default = NOW()`.
- `pg_trgm` extension enabled in 001 for fuzzy name search via gist trgm indexes.
- JSON columns use `postgresql.JSON` (not JSONB) — flagged as a candidate for migration to JSONB later.

---

## Migration timeline

| Rev | Date | What it added |
|---|---|---|
| 001 | 2026-03-21 | Initial schema: genres, artists, tracks, trending_snapshots, predictions, feedback, api_keys + extensions + `genre_status` enum |
| 002 | 2026-03-22 | `scraper_configs` table + seeds `spotify` row |
| 003 | — | `scraper_configs.last_record_count` column |
| 004 | — | `tracks`: shazam_id, tiktok_sound_id, billboard_id, chartmetric_id columns + unique indexes (incl. apple_music_id which was previously not indexed) |
| 005 | 2026-04-03 | `backtest_results` table |
| … | … | (historical migrations 006–032 — see `alembic/versions/` for authoritative list) |
| 033 | 2026-04-15 | `genre_structures` table + 20-genre seed — per-genre song structure templates for Suno prompt injection (task #109, PRD §70) |
| 034 | 2026-04-15 | `ai_artists.structure_template` JSONB + `ai_artists.genre_structure_override` BOOLEAN — per-artist structure overrides (task #109) |
| 035 | 2026-04-16 | `chartmetric_global_bucket` singleton table — Postgres-coordinated cross-replica rate-limit governor (task #8 / Chartmetric Phase B fix for L016 multi-replica fan-out, PRD §7.3) |
| 036 | 2026-04-18 | `rights_holders` polymorphic table — canonical publishers / writers / composers (kind discriminator + IPI / PRO / contact / split fields). Backs the new Rights tab in the UI; songs reference these by id instead of duplicating contact info on every `songs_master.writers` blob. |

Head: `036` (file describes 001–005 + 033–036 in detail — migrations 006–032 are authoritative in `alembic/versions/`. Update this file in the same commit when adding new tables.)

---

## `genre_structures` (migration 033) — task #109

Per-genre song-form skeleton injected into Suno prompts as a `[Section: N bars{, instrumental}]` tag block. Resolved by `api/services/genre_structures_service.resolve_genre_structure()` which walks the dotted-genre chain (`pop.k-pop` → `pop`) before falling back to the `pop` row.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| primary_genre | `Text` | PK | Canonical taxonomy id (e.g. `pop.k-pop`). Cross-checked against `shared/genre_taxonomy.py`. |
| structure | `JSONB` | NOT NULL | `list[{name: str, bars: int (>0), vocals: bool}]`. Validated app-side in `validate_structure()`; DB-side `ck_genre_structures_nonempty` checks `jsonb_array_length > 0`. |
| notes | `Text` | NULL | One-line rationale per row (BPM hint + reference template). |
| updated_at | `TIMESTAMPTZ` | NOT NULL, default NOW() | Bumped on every write. |
| updated_by | `Text` | NULL | `seed_033` for migration seeds, `CEO` / agent name for later edits. |

**Seeded keys (20):** `pop`, `pop.k-pop`, `pop.dance-pop`, `pop.indie-pop`, `pop.latin-pop`, `hip-hop`, `hip-hop.trap`, `hip-hop.trap.drill`, `r-and-b`, `electronic.edm`, `electronic.house`, `electronic.techno`, `electronic.lo-fi-electronic`, `electronic.ambient`, `african.afrobeats`, `african.amapiano`, `latin.reggaeton`, `rock`, `country`, `caribbean.reggae`. (Plan originally listed `rap`; substituted `caribbean.reggae` because `rap` isn't in the taxonomy — rap subgenres live under `hip-hop.*`.)

---

## `ai_artists` additions (migration 034) — task #109

Two columns added so an artist can deviate from the per-genre default:

| Column | Type | Constraints | Notes |
|---|---|---|---|
| structure_template | `JSONB` | NULL | Same shape as `genre_structures.structure`. NULL = artist follows the genre row as-is. |
| genre_structure_override | `Boolean` | NOT NULL, default FALSE | When TRUE, the artist's `structure_template` is used as-is and the genre row is ignored. When FALSE (default), the resolver blends the artist template with the genre row using the section-name merge rule from NEXT_SESSION_START_HERE.md §3 (artist wins on named matches; artist-only sections insert in artist-declared order; genre-only sections stay in place).

---

## `chartmetric_global_bucket` (migration 035) — task #8 / Chartmetric Phase B

Singleton row table coordinating dispatch rate across all Railway replicas. Replaces the in-process `TokenBucket` as the authoritative budget. `ChartmetricQuota.acquire()` consumes from this row FIRST (via `SELECT ... FOR UPDATE`), then the in-process bucket. Solves the L016 multi-replica fan-out gap (N replicas × 1.0 req/s no longer combine to N req/s globally).

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | `Integer` | PK | Pinned to 1 via `ck_chartmetric_global_bucket_singleton CHECK (id = 1)` so accidental second rows fail at the DB. |
| tokens | `Float` | NOT NULL | Current bucket level. Mutated per acquire(). |
| last_refill_at | `TIMESTAMPTZ` | NOT NULL, default NOW() | Anchor for elapsed-time refill math. Always written via `clock_timestamp()` (real wall time per statement) — using `NOW()` would return transaction-start time and poison the math. |
| rate_per_sec | `Float` | NOT NULL | Refill rate. Seeded 1.0 (matches Phase A's BASE_RATE). |
| burst | `Float` | NOT NULL | Bucket capacity. Seeded 1.0 (no microbursts allowed; mirrors Phase A's BURST=1 — see L016). |
| updated_at | `TIMESTAMPTZ` | NOT NULL, default NOW() | Bumped on every write. |

`ck_chartmetric_global_bucket_positive` enforces `rate_per_sec > 0 AND burst > 0 AND tokens >= 0`.

Wrapper class: `chartmetric_ingest/global_bucket.py::GlobalChartmetricBucket` with `acquire`, `snapshot`, `drain`, `set_rate`. Lock window is one DB roundtrip; sleeps happen OUTSIDE the lock so other replicas advance.

---

# Part I — Current schema (live)

## `genres`

Static taxonomy of 906 genres (12 root categories), seeded by `scripts/seed_genres.py` from `shared/genre_taxonomy.py`.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | `String(200)` | PK | Dot-notation, e.g. `pop.dance-pop.electropop` |
| name | `String(200)` | NOT NULL | Human-readable |
| parent_id | `String(200)` | FK → genres.id, NULL | NULL for roots |
| root_category | `String(50)` | NOT NULL | One of 12 roots: pop, rock, electronic, hip-hop, r-and-b, latin, country, jazz, classical, african, asian, caribbean |
| depth | `Integer` | NOT NULL, default 0 | 0 = root, 1 = category, 2+ = subcategory |
| spotify_genres | `ARRAY(String)` | default `{}` | Platform mapping |
| apple_music_genres | `ARRAY(String)` | default `{}` | Platform mapping |
| musicbrainz_tags | `ARRAY(String)` | default `{}` | Platform mapping |
| chartmetric_genres | `ARRAY(String)` | default `{}` | Platform mapping |
| audio_profile | `JSON` | NULL | `{tempo_range, energy_range, valence_range, danceability_range}` |
| adjacent_genres | `ARRAY(String)` | default `{}` | Cross-branch genre IDs |
| status | `genre_status` ENUM | default `'active'` | `active | deprecated | proposed` |
| created_at | `TIMESTAMPTZ` | default NOW() | |
| updated_at | `TIMESTAMPTZ` | default NOW() | |

**Indexes:** `idx_genre_parent (parent_id)`, `idx_genre_root (root_category)`

---

## `artists`

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | `UUID` | PK | |
| name | `String(500)` | NOT NULL | |
| spotify_id | `String(100)` | UNIQUE, NULL | Cross-platform key |
| apple_music_id | `String(100)` | UNIQUE, NULL | |
| tiktok_handle | `String(200)` | NULL | |
| chartmetric_id | `Integer` | NULL | |
| musicbrainz_id | `String(100)` | NULL | |
| image_url | `String(1000)` | NULL | |
| genres | `ARRAY(String)` | default `{}` | Populated by genre classifier |
| metadata_json | `JSON` | default `{}` | `{classification_quality, ...}` |
| canonical | `Boolean` | default `true` | Entity dedup flag |
| created_at | `TIMESTAMPTZ` | default NOW() | |
| updated_at | `TIMESTAMPTZ` | default NOW() | |

**Indexes:** `idx_artist_name (name)`, `idx_artist_spotify (spotify_id) WHERE spotify_id IS NOT NULL`, `idx_artist_name_trgm (name gist_trgm_ops)`

---

## `tracks`

| Column | Type | Constraints | Migration | Notes |
|---|---|---|---|---|
| id | `UUID` | PK | 001 | |
| title | `String(500)` | NOT NULL | 001 | |
| artist_id | `UUID` | FK → artists.id, NOT NULL | 001 | |
| isrc | `String(20)` | UNIQUE, NULL | 001 | International Standard Recording Code — best cross-platform key |
| spotify_id | `String(100)` | UNIQUE, NULL | 001 | |
| apple_music_id | `String(100)` | NULL (UNIQUE INDEX added in 004) | 001 / 004 | |
| duration_ms | `Integer` | NULL | 001 | |
| release_date | `Date` | NULL | 001 | |
| genres | `ARRAY(String)` | default `{}` | 001 | Populated by classifier — **only 102/2,146 populated as of 2026-04-11** |
| audio_features | `JSON` | NULL | 001 | `{tempo, energy, valence, danceability, key, mode, ...}` — **only 121/2,146 populated as of 2026-04-11** |
| metadata_json | `JSON` | default `{}` | 001 | `{classification_quality, ...}` |
| shazam_id | `String(100)` | NULL (UNIQUE INDEX in 004) | 004 | |
| tiktok_sound_id | `String(100)` | NULL (UNIQUE INDEX in 004) | 004 | |
| billboard_id | `String(200)` | NULL (UNIQUE INDEX in 004) | 004 | |
| chartmetric_id | `Integer` | NULL (UNIQUE INDEX in 004) | 004 | |
| created_at | `TIMESTAMPTZ` | default NOW() | 001 | |
| updated_at | `TIMESTAMPTZ` | default NOW() | 001 | |

**Indexes:**
- `idx_track_title (title)`
- `idx_track_isrc (isrc) WHERE isrc IS NOT NULL`
- `idx_track_spotify (spotify_id) WHERE spotify_id IS NOT NULL`
- `idx_track_title_trgm (title gist_trgm_ops)` — fuzzy search
- `idx_track_fts USING gin(to_tsvector('english', title))` — full-text search
- `ix_tracks_apple_music_id (apple_music_id) UNIQUE`
- `ix_tracks_shazam_id (shazam_id) UNIQUE`
- `ix_tracks_tiktok_sound_id (tiktok_sound_id) UNIQUE`
- `ix_tracks_billboard_id (billboard_id) UNIQUE`
- `ix_tracks_chartmetric_id (chartmetric_id) UNIQUE`

---

## `trending_snapshots`

One row per (entity, platform, date). The hot table — most queries hit this.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | `UUID` | PK | |
| entity_type | `String(10)` | NOT NULL | `'artist'` or `'track'` |
| entity_id | `UUID` | NOT NULL | FK is implicit (no DB-level constraint) |
| snapshot_date | `Date` | NOT NULL | |
| platform | `String(20)` | NOT NULL | `chartmetric | spotify | shazam | apple_music | kworb | radio | tiktok` |
| platform_rank | `Integer` | NULL | Rank from source |
| platform_score | `Float` | NULL | Raw score from source |
| normalized_score | `Float` | NOT NULL, default 0 | Normalized 0–100 across entities/dates (`api/services/normalization.py`) |
| velocity | `Float` | NULL | Score change vs same entity 7 days prior |
| signals_json | `JSON` | default `{}` | Full payload: `{spotify_genres, apple_music_genres, audio_features, playlist_genres, primary_theme, themes, ...}` — **genre data currently lives here as raw strings, not in `tracks.genres`** |
| composite_score | `Float` | NULL | Weighted avg across platforms (`api/services/aggregation.py`) |
| created_at | `TIMESTAMPTZ` | default NOW() | |
| updated_at | `TIMESTAMPTZ` | default NOW() | |

**Constraints:** `uq_snapshot UNIQUE(entity_type, entity_id, snapshot_date, platform)`

**Indexes:**
- `idx_trending_entity_date (entity_id, snapshot_date DESC)`
- `idx_trending_platform_date (platform, snapshot_date DESC)`
- `idx_trending_snapshot_date (snapshot_date)`

**Note (not enforced):** no FK on `entity_id` because it can reference either `artists.id` or `tracks.id` depending on `entity_type`. Polymorphic FK — pay attention when joining.

---

## `predictions`

ML model outputs. **Currently 0 rows** — model has never trained successfully.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | `UUID` | PK | |
| entity_type | `String(10)` | NOT NULL | `artist | track | genre` |
| entity_id | `String(200)` | NOT NULL | UUID for artist/track, dot-notation for genre |
| horizon | `String(5)` | NOT NULL | `7d | 30d | 90d` |
| predicted_score | `Float` | NOT NULL | |
| confidence | `Float` | NOT NULL | 0–1, isotonic-calibrated |
| model_version | `String(20)` | NOT NULL | Tag of ensemble |
| features_json | `JSON` | default `{}` | `{top_features, temporal_info, ...}` |
| predicted_at | `TIMESTAMPTZ` | NOT NULL | |
| resolved_at | `TIMESTAMPTZ` | NULL | When prediction was validated |
| actual_score | `Float` | NULL | |
| error | `Float` | NULL | |
| created_at | `TIMESTAMPTZ` | default NOW() | |
| updated_at | `TIMESTAMPTZ` | default NOW() | |

**Indexes:** `idx_prediction_horizon (horizon, predicted_at DESC)`, `idx_prediction_entity (entity_id, horizon)`

---

## `feedback`

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | `UUID` | PK | |
| prediction_id | `UUID` | FK → predictions.id, NOT NULL | |
| actual_score | `Float` | NOT NULL | |
| notes | `Text` | NULL | |
| submitted_by | `String(100)` | NULL | |
| created_at | `TIMESTAMPTZ` | default NOW() | |

---

## `api_keys`

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | `UUID` | PK | |
| key_hash | `String(64)` | UNIQUE, NOT NULL | SHA-256 of full key |
| key_prefix | `String(20)` | NOT NULL | e.g. `sp_admin_` for display |
| key_last4 | `String(4)` | NOT NULL | For display |
| tier | `String(10)` | NOT NULL, default `'free'` | `free | pro | admin` |
| owner | `String(200)` | NULL | |
| last_used_at | `TIMESTAMPTZ` | NULL | |
| created_at | `TIMESTAMPTZ` | default NOW() | |
| updated_at | `TIMESTAMPTZ` | default NOW() | |

**Indexes:** `idx_api_key_hash (key_hash)`

**Rate limits** (from `shared/constants.py`, enforced in middleware): free=100/min, pro=1000/min, admin=unlimited.

---

## `scraper_configs`

Added in migration 002. Seeded only with `'spotify'` row by the migration; other scrapers (chartmetric, shazam, apple_music, ...) are auto-created on first scheduler tick.

| Column | Type | Constraints | Migration |
|---|---|---|---|
| id | `String(100)` | PK | 002 — e.g. `'spotify'`, `'chartmetric'`, `'shazam'` |
| enabled | `Boolean` | NOT NULL, default `true` | 002 |
| interval_hours | `Float` | NOT NULL, default `6.0` | 002 |
| last_run_at | `TIMESTAMPTZ` | NULL | 002 |
| last_status | `String(50)` | NULL | 002 — `success | error | running` |
| last_error | `String(2000)` | NULL | 002 |
| config_json | `JSON` | NOT NULL, default `{}` | 002 — source-specific options |
| last_record_count | `Integer` | NULL | 003 |
| created_at | `TIMESTAMPTZ` | default NOW() | 002 |
| updated_at | `TIMESTAMPTZ` | default NOW() | 002 |

---

## `backtest_results`

Added in migration 005. **Currently 0 rows** — backtest job has never produced output.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | `String(36)` | PK | UUID as string |
| run_id | `String(36)` | NOT NULL | Batch identifier |
| evaluation_date | `Date` | NOT NULL | Period being scored |
| entity_type | `String(10)` | NULL | `artist | track` filter |
| genre_filter | `String(200)` | NULL | Genre ID filter |
| horizon | `String(5)` | NOT NULL, default `'7d'` | |
| mae | `Float` | NULL | |
| rmse | `Float` | NULL | |
| precision_score | `Float` | NULL | |
| recall_score | `Float` | NULL | |
| f1_score | `Float` | NULL | |
| auc_roc | `Float` | NULL | |
| sample_count | `Integer` | default 0 | |
| positive_count | `Integer` | default 0 | |
| predicted_avg | `Float` | NULL | |
| actual_rate | `Float` | NULL | |
| model_version | `String(20)` | NULL | |
| status | `String(20)` | default `'running'` | `running | completed | failed` |
| details_json | `JSON` | NULL | |
| created_at | `TIMESTAMPTZ` | default NOW() | |

**Indexes:** `idx_backtest_run_date (run_id, evaluation_date)`, `idx_backtest_genre_date (genre_filter, evaluation_date)`

---

# Part II — Phase 3 target schema (PROPOSED, not yet migrated)

These tables come from `planning/PRD/SoundPulse_PRD_v2.md` §15 and `TECHNICAL_SPEC.md` §5–7. They have not been migrated yet — Phase 3 work is gated on Phase 2 closing out.

## `ai_artists` (proposed)

Persistent virtual artist personas. Each has a distinct identity, voice, visuals, and grows a discography over time.

| Column | Type | Notes |
|---|---|---|
| id | `UUID` PK | |
| stage_name | `VARCHAR(200)` NOT NULL | Public name |
| legal_name | `VARCHAR(200)` | For PRO registration |
| age | `Integer` | |
| gender | `VARCHAR(20)` | |
| ethnicity | `VARCHAR(100)` | |
| provenance | `VARCHAR(500)` | e.g. "Atlanta, raised in Seoul" |
| languages | `TEXT[]` | |
| voice_dna | `JSONB` NOT NULL default `{}` | `{timbre, vocal_range, delivery_style, accent, autotune_level, ad_libs, suno_persona_id}` |
| visual_dna | `JSONB` NOT NULL default `{}` | `{face_description, fashion_style, color_palette, art_direction, tattoos, reference_image_id (6-angle portrait)}` |
| genre_home | `TEXT[]` NOT NULL | Primary genre IDs |
| adjacent_genres | `TEXT[]` | |
| influences | `TEXT[]` | |
| anti_influences | `TEXT[]` | Negative tags for generation |
| production_signature | `JSONB` default `{}` | "always uses 808s, spacey reverb" |
| lyrical_voice | `JSONB` default `{}` | `{themes, vocabulary_level, perspective, recurring_motifs}` |
| backstory | `Text` | |
| personality_traits | `TEXT[]` | |
| social_voice | `JSONB` default `{}` | `{posting_style, caption_format, emoji_usage, controversy_stance}` |
| spotify_artist_id | `VARCHAR(100)` | Claimed after first release |
| tiktok_handle | `VARCHAR(100)` | |
| instagram_handle | `VARCHAR(100)` | |
| youtube_channel_id | `VARCHAR(100)` | |
| status | `VARCHAR(20)` default `'active'` | `active | growth | mature | retired` |
| portfolio_role | `VARCHAR(20)` default `'growth'` | `growth | cash_cow | experimental` |
| content_rating | `VARCHAR(10)` default `'mild'` | `clean | mild | explicit` — controls profanity |
| created_at, updated_at | `TIMESTAMPTZ` | |

**Indexes:** `idx_ai_artist_status (status)`, `idx_ai_artist_genre_home GIN (genre_home)`

---

## `ai_artist_releases` (proposed)

| Column | Type | Notes |
|---|---|---|
| id | `UUID` PK | |
| artist_id | `UUID` FK → ai_artists.id | |
| track_title | `VARCHAR(500)` | |
| song_dna | `JSONB` NOT NULL | Full blueprint used for generation |
| generation_model | `VARCHAR(50)` | `suno | udio | soundraw | musicgen` |
| generation_prompt | `Text` | The exact prompt sent |
| audio_file_url | `VARCHAR(1000)` | Object storage path |
| cover_art_url | `VARCHAR(1000)` | |
| distributed_at | `TIMESTAMPTZ` | NULL until distribution success |
| distribution_service | `VARCHAR(50)` | `revelator | labelgrid` |
| isrc | `VARCHAR(20)` | Assigned by distributor |
| upc | `VARCHAR(20)` | |
| released_at | `TIMESTAMPTZ` | Public release date |
| total_streams | `BigInt` default 0 | Updated by scrapers |
| spotify_streams | `BigInt` default 0 | |
| apple_streams | `BigInt` default 0 | |
| tiktok_creates | `Integer` default 0 | UGC count |
| shazam_lookups | `Integer` default 0 | |
| revenue_cents | `BigInt` default 0 | Aggregated from `revenue_events` |
| created_at | `TIMESTAMPTZ` | |

**Indexes:** `idx_release_artist (artist_id, released_at DESC)`, `idx_release_isrc (isrc)`

---

## `revenue_events` (proposed)

Append-only royalty events. Reconciled from Revelator, SoundExchange, ASCAP, distributor reports.

| Column | Type | Notes |
|---|---|---|
| id | `UUID` PK | |
| release_id | `UUID` FK → ai_artist_releases.id | |
| artist_id | `UUID` FK → ai_artists.id | Denormalized for aggregation queries |
| platform | `VARCHAR(50)` | spotify, apple_music, youtube, ... |
| territory | `VARCHAR(10)` | ISO country code |
| period_start | `Date` | |
| period_end | `Date` | |
| stream_count | `BigInt` default 0 | |
| revenue_cents | `BigInt` default 0 | USD cents |
| royalty_type | `VARCHAR(20)` | `streaming | mechanical | performance | sync` |
| source | `VARCHAR(50)` | `revelator | soundexchange | ascap | bmi | distributor` |
| created_at | `TIMESTAMPTZ` | |

**Indexes:** `idx_revenue_release_period (release_id, period_start)`, `idx_revenue_artist_period (artist_id, period_start)`

---

## `social_posts` (proposed)

| Column | Type | Notes |
|---|---|---|
| id | `UUID` PK | |
| artist_id | `UUID` FK → ai_artists.id | |
| release_id | `UUID` FK → ai_artist_releases.id NULL | Some posts aren't tied to a specific release |
| platform | `VARCHAR(20)` | `tiktok | instagram | youtube | x` |
| content_type | `VARCHAR(30)` | `mood_photo | teaser | release_announcement | lyric_video | ...` |
| caption | `Text` | |
| media_url | `VARCHAR(1000)` | Image/video |
| scheduled_for | `TIMESTAMPTZ` | |
| posted_at | `TIMESTAMPTZ` NULL | Set after API confirmation |
| platform_post_id | `VARCHAR(200)` | Returned by platform API |
| status | `VARCHAR(20)` default `'scheduled'` | `scheduled | posted | failed | cancelled` |
| likes | `Integer` default 0 | |
| views | `Integer` default 0 | |
| shares | `Integer` default 0 | |
| ugc_creates | `Integer` default 0 | TikTok sound adoptions |
| created_at, updated_at | `TIMESTAMPTZ` | |

**Indexes:** `idx_social_artist_scheduled (artist_id, scheduled_for)`, `idx_social_status (status)`

---

## `generation_logs` (proposed)

| Column | Type | Notes |
|---|---|---|
| id | `UUID` PK | |
| release_id | `UUID` FK → ai_artist_releases.id NULL | NULL on failed attempts that never produced a release |
| attempt_number | `Integer` | 1-indexed; max 3 per blueprint |
| model | `VARCHAR(50)` | suno, udio, ... |
| prompt | `Text` | Full prompt sent |
| audio_url | `VARCHAR(1000)` NULL | Output file (NULL on failure) |
| quality_check_passed | `Boolean` | tempo/energy/duration checks |
| quality_check_details | `JSONB` | `{tempo_actual, tempo_target, energy_actual, ...}` |
| cost_cents | `Integer` | API cost in cents |
| latency_ms | `Integer` | Generation time |
| error | `Text` NULL | If generation failed |
| created_at | `TIMESTAMPTZ` | |

**Indexes:** `idx_genlog_release (release_id)`

---

## `llm_calls` (proposed — supports CLAUDE.md "every LLM call must be logged")

CLAUDE.md mandates that every LLM call is logged with model, tokens, cost, timestamp, action type. Currently no such table exists. Proposed:

| Column | Type | Notes |
|---|---|---|
| id | `UUID` PK | |
| model | `VARCHAR(100)` | e.g. `llama-3.3-70b-versatile` (Groq) |
| provider | `VARCHAR(50)` | `groq | openai | anthropic | replicate` |
| action_type | `VARCHAR(50)` | `assistant_chat | lyrics_generation | persona_generation | blueprint_assist | ...` |
| input_tokens | `Integer` | |
| output_tokens | `Integer` | |
| cost_cents | `Integer` | Estimated cost in USD cents |
| latency_ms | `Integer` | |
| caller | `VARCHAR(200)` | Function or service name |
| context_id | `VARCHAR(200)` NULL | e.g. release_id, artist_id, prediction_id |
| metadata_json | `JSON` default `{}` | Anything else worth keeping |
| created_at | `TIMESTAMPTZ` default NOW() | |

**Indexes:** `idx_llm_call_action_date (action_type, created_at DESC)`, `idx_llm_call_model_date (model, created_at DESC)`

---

## `reference_artists` (proposed — supports artist creation pipeline §19)

Per-reference enrichment row written by the `reference_artist_lookup` service. Powers the persona blender (§18.1 step 4) by giving the LLM clean, structured fields per real-world reference artist. **Currently a planned table — code path exists in `api/services/reference_artist_lookup.py`; full DDL not yet shipped via alembic. Schema below is the target spec.**

| Column | Type | Source | Notes |
|---|---|---|---|
| reference_artist_id | `UUID` PK | system | |
| canonical_name | `Text` | Chartmetric / web | Stage name |
| source_urls | `JSONB` | scraper | URLs used during enrichment |
| age | `Integer` NULL | web | Exact if found |
| age_confidence | `Float` | parser | 0-1 |
| gender_presentation | `Text` NULL | web / inferred | Only if publicly stated or strongly represented |
| nationality | `Text` NULL | web | |
| provenance | `Text` NULL | web | City / region / origin |
| early_life_summary | `Text` NULL | web summary | Concise |
| relationship_status | `Text` NULL | web | Only if public + relevant |
| languages | `Text[]` | web / lyrics data | |
| genres | `Text[]` | Chartmetric + web | |
| influences | `Text[]` | web | Explicit influences only |
| aesthetic_summary | `Text` | vision + LLM | Short style descriptor |
| fashion_style_summary | `Text` | vision + LLM | Key signature |
| color_palette | `Text[]` | vision extraction | Hex or named colors |
| textures_materials | `Text[]` | vision extraction | leather, denim, satin, etc. |
| cultural_style_refs | `Text[]` | vision + LLM | e.g. Y2K, corridos streetwear |
| face_description | `Text` | vision + LLM | For generation |
| body_presentation | `Text` | vision | |
| hair_signature | `Text` | vision | |
| tattoos_piercings | `Text[]` | vision | |
| voice_timbre_description | `Text` | audio / LLM | Crucial |
| voice_range_guess | `Text` | audio / LLM | tenor / alto etc. |
| delivery_style | `Text[]` | audio / LLM | e.g. whispery, clipped, melodic rap |
| accent_pronunciation | `Text` | audio / LLM | |
| autotune_processing | `Text` | audio / LLM | none / light / heavy |
| adlib_signature | `Text[]` | audio / LLM | |
| lyrical_perspective | `Text` | lyric analysis | First person, narrative, etc. |
| lyrical_themes | `Text[]` | lyric analysis | |
| social_voice | `Text` | web / social scrape | |
| confidence_report | `JSONB` | system | Per-field confidence |
| created_at | `TIMESTAMPTZ` default NOW() | system | |

---

## `audio_assets` (proposed — supports song generation §24)

Provider-agnostic asset row produced when a Suno/Udio/MusicGen call lands a playable file. Normalizes provider-specific output shapes into one schema so downstream QA + storage is provider-blind. **Currently a planned table — referenced by §24 + §25 + the songs_master FKs but full DDL not yet shipped.**

| Column | Type | Notes |
|---|---|---|
| asset_id | `UUID` PK | |
| song_id | `UUID` FK → songs_master.song_id | |
| provider | `Text` | `suno_evolink` / `suno_kie` / `udio` / `musicgen` |
| provider_job_id | `Text` | Provider's task ID for traceability |
| format | `Text` | `mp3` / `wav` / `flac` |
| sample_rate | `Integer` NULL | Hz |
| bitrate | `Integer` NULL | kbps |
| duration_seconds | `Integer` | |
| storage_url | `Text` | Object-storage or self-hosted URL |
| checksum | `Text` | SHA-256 of file bytes |
| is_master_candidate | `Boolean` | TRUE for the post-QA winner; provider may return multiple takes |
| created_at | `TIMESTAMPTZ` default NOW() | |

---

## `song_qa_reports` (proposed — supports audio QA §25)

QA verdict per `audio_assets` row. One row per QA pass. **Currently a planned table — referenced by §25 + songs_master.qa_report_id FK but full DDL not yet shipped.**

| Column | Type | Notes |
|---|---|---|
| qa_report_id | `UUID` PK | |
| song_id | `UUID` FK → songs_master.song_id | |
| asset_id | `UUID` FK → audio_assets.asset_id | |
| tempo_match_score | `Float` | 0-1, vs blueprint target |
| key_match_score | `Float` | 0-1 |
| energy_match_score | `Float` | 0-1 |
| silence_score | `Float` | Fraction of non-silent audio |
| clipping_score | `Float` | Fraction of peak-clipped samples |
| duplication_risk_score | `Float` | Cosine similarity to nearest existing-catalog audio embedding (MFCC). >0.85 fails. |
| pass_fail | `Boolean` | Aggregate verdict; FALSE triggers regen up to 3x then CEO escalation |
| report_json | `JSONB` | Full per-check result with reasons (loudness LUFS, lyric intelligibility, vocal prominence, etc.) |
| created_at | `TIMESTAMPTZ` default NOW() | |

---

## `rights_holders` (migration 036) — publishers / writers / composers

Polymorphic single-table design. `kind` discriminator pins each row to one of `publisher | writer | composer` via a CHECK constraint. Backs the Rights tab in the UI. `songs_master.writers` / `publishers` / `composers` JSONB blobs reference these by id (rather than duplicating contact + IPI + PRO info on every song).

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | `UUID` | PK, default `gen_random_uuid()` | |
| kind | `Text` | NOT NULL, CHECK in {publisher, writer, composer} | Fixed at create time, not editable on PATCH. |
| legal_name | `Text` | NOT NULL | Registered legal entity / person name. |
| stage_name | `Text` | NULL | Pen name / DBA / alias. |
| ipi_number | `Text` | NULL | 11-digit Interested Parties Information ID. Required for ASCAP/BMI registration. |
| isni | `Text` | NULL | International Standard Name Identifier. |
| pro_affiliation | `Text` | NULL | `ASCAP` / `BMI` / `SESAC` / `GMR` / `PRS` / `SOCAN` / `GEMA` / `SACEM` / `JASRAC` / `APRA AMCOS` / `SIAE` / `SUISA` / Other. |
| publisher_company_name | `Text` | NULL | For writers/composers signed to a publisher. |
| email | `Text` | NULL | |
| phone | `Text` | NULL | |
| address | `Text` | NULL | For W-9 / W-8 mailings. |
| tax_id | `Text` | NULL | EIN / SSN / VAT reference. |
| default_split_percent | `Float` | NULL, CHECK 0-100 | Typical % this party gets on a song; the songs_master.writers blob can override per-song. |
| notes | `Text` | NULL | Admin id, contract reference, signing date, etc. |
| created_at | `TIMESTAMPTZ` | NOT NULL, default NOW() | |
| updated_at | `TIMESTAMPTZ` | NOT NULL, default NOW() | Onupdate via SQLAlchemy. |

Indexes: `idx_rights_holders_kind_name (kind, legal_name)` for the per-kind list queries the Rights tab runs.
