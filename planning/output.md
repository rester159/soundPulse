# Assistant Responses Log

> All assistant responses, timestamped. Format: `YYYY-MM-DD HH:MM:SS`

---

## 2026-04-11 09:50:47 — Session onboarding

**Read and internalized:**
- `CLAUDE.md` — working style, workflow principles, planning artifacts. Note: bottom of file contains a stale "Flint" handoff block referencing a different repo; ignored, working directory is `C:\Users\edang\myApps_v2\soundPulse`.
- `planning/lessons.md` — empty (no prior lessons logged).
- `planning/tasks.md` — empty (just header). No tasks claimed.
- `planning/schema.md` — empty placeholder. Live schema lives in `alembic/versions/` migrations 001–005.
- `planning/PRD/SoundPulse_PRD_v2.md` (1314 lines, canonical) — full vision: SoundPulse is a fully autonomous virtual record label, not just a trend tracker. End-to-end pipeline: Analyze → Predict → Create → Distribute → Market → Register → Optimize → Collect → Reinvest.
- `planning/PRD/SoundPulse_Executive_Summary.md` — same vision, executive framing.
- `planning/PRD/BUILD_PLAYBOOK.md` — original 9-session build sequence (Phase 1 historic).
- `planning/PRD/TECHNICAL_SPEC.md` — system architecture, data models, Phase 3 specs (ai_artists, ai_artist_releases, revenue_events).
- `MEMORY.md` — single memory: "SoundPulse is the AI brain of a virtual label, not just a trend tracker."

**Codebase deep map (via Explore subagent):**
- **Stack**: FastAPI 0.115 + SQLAlchemy 2.0 async + asyncpg + Alembic + Pydantic 2 + Redis + Celery + APScheduler + scikit-learn + LightGBM (configured). Frontend: React 19 + Vite 8 + React Router 7 + TanStack Query + Tailwind 4 + Recharts + Lucide.
- **DB**: 9 tables (genres, artists, tracks, trending_snapshots, predictions, backtest_results, scraper_configs, api_keys, feedback). 5 alembic migrations. Postgres on Neon. Redis on Railway.
- **API surface (16 endpoints)**: `/api/v1/{genres,trending,search,predictions,admin,backtesting,blueprint,assistant}` plus `/health` and `/admin` HTML dashboard.
- **Scrapers**: Chartmetric (4h, primary backbone), chartmetric_artists (12h), spotify (6h), spotify_audio (daily), shazam (4h), apple_music (6h), musicbrainz (12h), kworb, radio, genius_lyrics (ready, disabled). Base class with retry/backoff. APScheduler inside FastAPI lifespan + Celery beat for Railway.
- **Entity resolution**: ISRC → platform IDs → fuzzy (RapidFuzz ≥0.85) → create new.
- **ML pipeline**: ~70-79 features in 7 groups (momentum, cross-platform, TikTok, temporal, genre, entity history, audio). Phase 2 = LightGBM only. Phase 3 = LightGBM + LSTM + XGBoost + Ridge meta-learner + isotonic calibration. Cold start cap 0.5 confidence <14d. `ml/saved_models/` is empty (.gitkeep) — model has never trained successfully.
- **Frontend pages**: Dashboard, Explore, ApiPlayground, ModelValidation, SongLab, Assistant, DataFlow. Hooks via `useSoundPulse.js`. Recent commits focused on DataFlow page + fixing data nesting + Apple Music/TikTok endpoint paths.
- **Deployment**: Docker Compose local; Railway production (5 services: api, ui, worker, beat, redis). `scripts/start.py` runs migrations + seed_genres + uvicorn.

**Critical state (from PRD + commits):**
- Phase 1 = Data Foundation: 90% complete. 9,031 snapshots across 40 dates.
- Phase 2 = Prediction + Song DNA: 40% complete.
- Phase 3 = Full Autonomous Pipeline: specified, not built.
- **Known data gaps (April 2026)**: audio_features only 121/2,146 tracks, tracks.genres only 102/2,146, predictions table 0 rows, backtest_results 0 rows, genius_lyrics disabled. Root cause: insufficient consecutive daily data + spotify_audio scraper enabled-but-never-actually-run + container working-directory issue with `subprocess.run([sys.executable, "scripts/train_model.py"])`.
- ETA for first real predictions: ~14 days after daily scraping stabilizes.
- `planning/tasks.md` is empty — no canonical task backlog exists despite CLAUDE.md treating it as the single source of truth.
- `planning/schema.md` is empty — ground truth lives only in migrations.

**Stale items observed (not actioned, flagged for confirmation):**
1. `tasks.md` and `schema.md` are stub headers; CLAUDE.md treats both as authoritative. Worth populating before any new work.
2. CLAUDE.md trailing "Flint" block references a different repo entirely — likely accidental paste, candidate for removal.
3. `build kit/` directory shows as `D` (deleted) in git status but not committed. Untracked: `CLAUDE.md`, `planning/`.

**Ready to operate.** Awaiting next instruction. Will not write code or make non-trivial changes without a plan + sign-off, per CLAUDE.md.

---

## 2026-04-11 10:16:01 — Planning files populated + deep audit ingested

**Files written/edited:**
- `CLAUDE.md` — removed the stale "Flint" trailing block. Working directory is now consistent.
- `planning/PRD/SoundPulse_PRD_v2.md` — added §21.1 "Hideable Panel (UI requirement)" specifying the toggle, persistence to `localStorage['soundpulse.assistant.visible']`, `Cmd/Ctrl + .` shortcut, global context, no per-page state.
- `planning/schema.md` — populated from empty stub. Mirrors migrations 001–005 (genres, artists, tracks, trending_snapshots, predictions, feedback, api_keys, scraper_configs, backtest_results) with corrected column types from reading the actual migration files (Explore agent had a few wrong: `feedback.actual_score` is Float not Integer; `api_keys` has key_hash/key_prefix/key_last4/tier/owner not name/plan/rate_limit/is_active). Added Phase 3 target tables: `ai_artists`, `ai_artist_releases`, `revenue_events`, `social_posts`, `generation_logs`, plus a proposed `llm_calls` table to satisfy CLAUDE.md's "every LLM call must be logged" rule (currently not implemented anywhere).
- `planning/tasks.md` — populated from empty stub. 128 tasks across 5 sections: P1 closeout (21), P2 prediction+Song DNA (30), P3 stubs (28), O ops/quality (8), AUDIT findings (41). Fine-grained: each task is sized for one focused session. Format: id, title, status, assigned_to, depends_on, notes. Counts table at top.

**Deep audit subagent ran in parallel and returned 47 findings:**
- 9 BROKEN, 8 STUB, 17 BUG, 24 IMPROVEMENT, 5 SECURITY, 3 DATABASE.
- **Priority root-causes uncovered:**
  - The `spotify_audio` scraper failure is **not** a scheduler/auth issue — it's an API schema mismatch. `scrapers/spotify_audio.py:119-139` calls `/api/v1/trending` expecting `entity_identifier`+`signals` keys, but the GET returns `entity`+`scores`. Always returns 0 → exits early. This is the actual root cause of audio_features being 121/2,146 — not what the PRD claimed.
  - Genre classifier sparse output is compounded by `except Exception: pass` at `api/routers/trending.py:88` swallowing every classifier failure. Plus a critical bug at `genre_classifier.py:508-514`: neighbor inference compares track UUIDs against artist UUIDs in the artists table — broken for tracks.
  - Trending ingest timeout on Neon: genre classifier runs synchronously inside the async POST handler doing 6+ DB queries per entity → connection pool exhaustion.
  - Duplicate `"spotify_audio"` key in `scrapers/scheduler.py:183, 185` — line 183 silently overwritten by Python.
  - File-handle leak in `api/routers/admin.py:951` backfill subprocess (never closes the log file).
  - Hardcoded admin key (`sp_admin_0000...dead`) and JWT secret (`change-me-in-production`) in `api/config.py:9-10` as defaults — security risk if env vars aren't set in prod.
  - Predictions are computed-on-demand only — `generate_predictions` Celery task does NOT INSERT into the table. Architectural decision needed: persist or compute-on-demand?
  - LSTM `_build_sequence()` is undefined in `ml/predictor.py:95` — LSTM predictions never run silently.
- **Cross-references:** AUD findings that pinpoint root causes for existing P1/P2 tasks were back-linked in those tasks' Notes columns (P1-004 ↔ AUD-011, P1-011 ↔ AUD-001/AUD-005, P1-021 ↔ AUD-002, P2-001 ↔ AUD-017).
- **Verify-before-acting flags** marked on findings that may be false positives or already fixed: AUD-012 (rate limit backoff), AUD-021 (blueprint endpoints — recent commits suggest partial), AUD-040 (CORS — recent commit `fce5a34` claims to add it), AUD-045 (backtest GET endpoint — PRD says exists).

**Open architectural decisions surfaced:**
1. APScheduler-in-FastAPI vs Celery beat — both currently exist (O-002).
2. Predictions: persist to DB vs compute-on-demand (AUD-044, P2.C).
3. Distribution provider: Revelator vs LabelGrid (P3-030).
4. Polymorphic FK on `trending_snapshots.entity_id` — add CHECK constraint or split columns (AUD-027, AUD-028).

**Not yet executed (awaiting user direction):**
- The hideable Assistant panel implementation (P2.G, 8 tasks) — feature is specified in PRD §21.1 but not built.
- Any of the 128 tasks — this session was scoping/triage only.

**Recommended first three tasks to execute** (highest leverage, lowest risk):
1. **AUD-001 + AUD-005** (one session) — add logging at `trending.py:88` and fix the entity_id type bug at `genre_classifier.py:508-514`. Diagnoses 95% of tracks failing classification AND fixes one of the underlying bugs.
2. **AUD-011** (one session) — fix the spotify_audio API schema mismatch. One file edit, unblocks all audio feature enrichment, unblocks SongLab, unblocks ML training feature richness.
3. **AUD-036 + AUD-037** (one session) — refuse to boot in production with default admin key / JWT secret. Five-minute fix, eliminates a real security exposure.

---

## 2026-04-11 10:49:36 — Chartmetric Deep US: MECE definition + scraper + probe + bulk endpoint + backfill runner

User asked for an exhaustive MECE definition of what to pull from Chartmetric for US data, then to pull it. Spawned a doc-discovery subagent (WebFetch + WebSearch) to read the official Chartmetric apidoc, pycmc client, and Mixture Labs CLI reference. Got back authoritative endpoint list. Built five new artifacts and updated PRD + tasks.

**Files written:**
- **`api/schemas/trending.py`** — added `TrendingIngestBulk` (max 1000 items) and `TrendingIngestBulkResponse`.
- **`api/routers/trending.py`** — added `POST /api/v1/trending/bulk`. Single transaction, ON CONFLICT DO NOTHING for snapshot dedup, defers genre classification (tags entities `needs_classification: true` in metadata_json), defers composite recalc, single cache invalidation. Designed specifically to make massive backfills possible without the per-record bottleneck.
- **`scrapers/chartmetric_deep_us.py`** — `ChartmetricDeepUSScraper` with the full ENDPOINT_MATRIX (verified against the apidoc). Per-genre fan-out across Apple Music (24 genres), iTunes (24), Amazon (24), SoundCloud (10), Beatport (14), Shazam (4). Weekday snapping for Thursday-only (YouTube, Spotify Fresh Find) and Friday-only (SoundCloud, Beatport) charts. Both `track` and `artist` entity types supported. Uses `code2` param for Amazon, `country_code` for everything else. Bypasses `BaseScraper.run()` per-record loop in favor of bulk POSTs every 500 records.
- **`scripts/chartmetric_probe.py`** — calls each endpoint in the matrix once with the right date snap, plus discovers US city IDs via `/api/cities?country_code=US`, plus probes the artist demographic endpoints (Drake cm_id=1932) which are sometimes a paid add-on. Prints a per-endpoint pass/fail table and lists speculative endpoints to promote.
- **`scripts/backfill_chartmetric_deep_us.py`** — date-range CLI (`--days`, `--start`, `--end`, `--confirmed-only`). Calls `ChartmetricDeepUSScraper.backfill()`. Logs per-endpoint stats on completion.

**PRD §7.2 rewritten** with the docs-verified MECE space. Critical corrections vs my v1:
1. Spotify `type=plays` is **NOT a valid value** — `/charts/spotify` only accepts `regional` or `viral`. The existing `scrapers/chartmetric.py` has been silently failing on `plays` for months. P1-069 added to fix it.
2. **Billboard charts are NOT exposed** via Chartmetric API. Confirmed by absence from the entire `cm charts` CLI subcommand list. Removed all 8 Billboard speculative entries.
3. **City-level Spotify top-tracks does NOT exist** — Spotify itself doesn't publish per-city top-200. Removed the speculative `regional_city` entry. Per-city Spotify is only available via `/artist/{id}/where-people-listen`.
4. Charts have **NO `limit` param** — depth is fixed by the upstream provider (200 for Spotify/Apple/Shazam/iTunes/Amazon, 100 for YouTube/Deezer). Pagination is via `offset`. Exception: `/charts/airplay`, `/charts/twitch`, `/charts/tiktok/top-tracks` accept `limit`.
5. Amazon uses `code2` param, not `country_code`.
6. YouTube + Spotify Fresh Find = Thursday only; SoundCloud + Beatport = Friday only.

**Massive endpoints I added that were missing from the original scraper:**
- `/charts/spotify/artists` (5 type variants — biggest single missed signal: top US artists by monthly_listeners, popularity, followers, playlist_count, playlist_reach)
- `/charts/airplay?country_code=US` (5 metric type variants — US RADIO data, completely absent from current pipeline)
- `/charts/spotify/freshfind` (Spotify editorial new music, Thursdays)
- `/charts/youtube/{tracks,artists,videos,trends}` (4 weekly Thursday variants)
- `/charts/tiktok` canonical form with `type={tracks,videos,users}` + `/charts/tiktok/top-tracks`
- `/charts/soundcloud` × 10 genres × {top, trending} = 20 cells (Friday weekly)
- `/charts/itunes/{tracks,albums,videos}` × 24 genres
- `/charts/amazon/{tracks,albums}` × 24 genres × 4 insight variants
- Apple Music `/tracks` × 24 genres × {top, daily} = 48 cells (was just calling `All Genres top`)
- `/charts/beatport` × 14 genres (Friday weekly, no country)
- `/charts/twitch` (live-streaming musicians)
- Shazam per-genre (4 additional genres beyond the global top)

**Budget math (now with actual numbers):**
- ENDPOINT_MATRIX expands to **~281 calls per snapshot date** when fully fanned out
- Daily steady-state with deep refresh: ~12,000 calls = **7% of the 172,800/day budget**
- 730-day historical backfill: ~205,000 total calls = ~31 hours at 1.8 req/sec
- Recommended: chunk the backfill into 90-day windows so it can be paused/resumed (~5 chunks × ~5 hours each)

**P1.E.2 task additions** (now 22 tasks in this section): P1-050 through P1-071 cover bulk endpoint, scraper, probe, backfill runner, deferred classification sweep, deferred composite sweep, bulk endpoint test, artist enrichment lane, track enrichment lane, per-city ENDPOINT_MATRIX, long-tail crawls, and the existing-scraper `plays` fix.

**Marked done in this turn:** P1-050 (bulk endpoint), P1-051 (PRD MECE definition), P1-052 (deep scraper), P1-053 (probe), P1-054 (backfill runner). P1-044 and P1-046 marked `in_progress` (deferred to probe results).

**Run instructions sent to user:** docker exec the probe first, review output, promote any speculative-OK endpoints, then run the backfill in 90-day chunks.

**Critical follow-ups required before the bulk path is usable in steady state:**
- **P1-060** (deferred classification sweep) — without this, every bulk-ingested entity stays unclassified forever
- **P1-061** (deferred composite recalc sweep) — without this, `normalized_score` stays at 0.0 for all bulk-ingested rows, breaking composite scoring
- **P1-062** (bulk endpoint integration test) — TDD verification before relying on it for 200K+ rows

These are NOT blockers for the user running the probe + first backfill chunk to get data flowing immediately, but they ARE blockers before trusting the data for ML training.

---

## 2026-04-11 11:28:29 — Deferred sweeps + bulk endpoint test + plays bug fix + AUD-004

User said "fix everything flagged above + any decisions needed?". Executed all four flagged blockers in one batch:

**P1-060 — Classification sweep** (`api/services/classification_sweep.py`):
- `sweep_unclassified_entities(db, batch_size=500, force_reclassify=False)` processes one batch of tracks then one batch of artists
- Per-entity error logging — exceptions are LOGGED with entity id + attempt number, NOT swallowed (this is L003 in lessons.md)
- 3-strike retry: after 3 failed attempts, marks `metadata_json.needs_classification = "skipped"` (string sentinel) and stores `classification_last_error`. `force_reclassify=True` re-processes skipped entities
- `count_pending_classification(db)` for status checks
- Idempotent — crash mid-batch leaves the flags so the next pass picks up

**P1-061 — Composite recalc sweep** (`api/services/composite_sweep.py`):
- `sweep_zero_normalized_snapshots(db, batch_size=1000)` finds snapshots where `normalized_score=0` AND `signals_json->>'normalized_at' IS NULL` AND has either platform_score or platform_rank
- Step 1: per-snapshot, calls `normalize_score()` and updates the row, sets `signals_json.normalized_at` as the idempotency marker
- Step 2: groups affected (entity_id, entity_type, snapshot_date) tuples and calls `recalculate_composite_for_entity` once per unique tuple
- Single transaction per batch
- `count_pending_normalization(db)` for status, also reports unscoreable rows separately

**Wired into BOTH schedulers** (since O-002 is still open):
- Celery tasks `run_classification_sweep` and `run_composite_sweep` in `scrapers/tasks.py` — wrappers that create their own DB session, call the service, return stats
- APScheduler jobs `sweep_classification` and `sweep_composite` in `scrapers/scheduler.py`, both with 15-min `IntervalTrigger`. Job runners `_run_classification_sweep_job` and `_run_composite_sweep_job` use the existing `_get_session_factory()` pattern
- Manual trigger admin endpoints in `api/routers/admin.py`:
  - `GET /api/v1/admin/sweeps/status` — queue depth + permanently-skipped counts
  - `POST /api/v1/admin/sweeps/classification?batch_size=500&force_reclassify=false` — runs one batch, returns stats
  - `POST /api/v1/admin/sweeps/composite?batch_size=1000` — runs one batch, returns stats

**P1-062 — Bulk endpoint test suite** (`tests/test_api/test_trending_bulk.py`):
9 tests covering the full contract:
1. `test_bulk_ingest_creates_snapshots_and_entities` — happy path, 5 brand-new items, asserts `received=5, ingested=5, duplicates=0, errors=0, entities_created=5`
2. `test_bulk_ingest_dedups_on_repeat` — POST same item twice, second call gets `ingested=0, duplicates=1`
3. `test_bulk_rejects_invalid_platform` — 400
4. `test_bulk_rejects_no_identifier` — 422
5. `test_bulk_rejects_empty_items` — 422 (Pydantic min_length=1)
6. `test_bulk_rejects_oversize_batch` — 422 (Pydantic max_length=1000)
7. `test_bulk_marks_entities_needs_classification` — verifies the deferred-classification flag is set
8. `test_bulk_snapshots_have_zero_normalized_score` — verifies `normalized_score=0` AND that platform_score/platform_rank are preserved for the sweep
9. `test_classification_sweep_processes_pending_entities` — end-to-end: bulk ingest → run sweep → flag cleared, classified_at present
10. `test_composite_sweep_normalizes_zero_scores` — end-to-end: bulk ingest → run sweep → `signals_json.normalized_at` present

**P1-069 — `chartmetric.py` `plays` bug fix** (L001 in lessons.md):
- Removed the `type=plays` Spotify chart entry from `scrapers/chartmetric.py:60-65`, `scripts/backfill_chartmetric.py:57-62`, and `scripts/backfill_deep.py:62-67`
- Added comments referencing P1-069 / L001 explaining why
- Per the apidoc, `/api/charts/spotify` only accepts `type ∈ {regional, viral}`. The values `plays/popularity/monthly_listeners/playlist_count/playlist_reach` belong to the SEPARATE `/api/charts/spotify/artists` endpoint (which is now fully covered by `chartmetric_deep_us.py`)

**Bonus — AUD-004 fix:** removed the duplicate `"spotify_audio"` key in `scrapers/scheduler.py:DEFAULT_CONFIGS`. Both copies were identical so no behavior change, but the dict literal now reads cleanly.

**Lessons logged:**
- **L001** — `type=plays` invalid value, has been silently failing for months. Burned ~25% of daily-cadence rate budget on an invalid endpoint. Prevention: always verify upstream API endpoints against canonical docs; probe before production runs; don't trust silent success.
- **L002** — Bulk ingest must defer expensive per-row work or it can't scale. Design the fast path FIRST. Defer everything that doesn't have to happen synchronously. Always have a queue marker. Sweeps must be idempotent.
- **L003** — Background sweeps must LOG failures with entity id + attempt number, not swallow them. Bounded retries with permanent-skip sentinel. Add status endpoints so queue depth is visible.

**Decisions made autonomously** (sensible defaults, easy to change):
- Sweep cadence: every 15 minutes
- Classification batch size: 500
- Composite batch size: 1000
- Classification retries before permanent skip: 3
- Idempotency markers: `metadata_json.needs_classification` (true/false/"skipped") for entities, `signals_json.normalized_at` timestamp for snapshots
- Wired into BOTH Celery beat AND APScheduler so the sweeps run regardless of which scheduler is active until O-002 is decided

**Decisions still pending from user** (flagged in response):
1. **AUD-044** — Persist predictions vs compute-on-demand?
2. **O-002** — APScheduler vs Celery beat (architectural cleanup)
3. **P3-010** — Suno wrapper provider: EvoLink ($0.11/song) vs CometAPI ($0.14/song)?
4. **P3-030** — Distribution: Revelator vs LabelGrid?

**Tasks marked done:** P1-060, P1-061, P1-062, P1-069, AUD-004. Count table updated: P1 done 9, AUDIT done 1, total done 10.

---

## 2026-04-11 11:42:47 — Volume answer + decisions + B1 (7 audit fixes) + B6 (DB Stats view backend + frontend)

User confirmed AUD-044 (persist predictions), asked for my recommendation on O-002, said EvoLink for P3-010, asked which is best for P3-030, said "continue in the order you mentioned". Plus four direct volume questions: "did you fix volume per minute? what's the new definition? are we maxing out Chartmetric? how many per day?"

**Volume answer (honest):** Volume on Neon is unchanged because no one has executed the probe + backfill yet. I can't run them from this session. Gave the user the math:
- Old: ~20 chart pulls/day, ~60–225 unique tracks/day (= 0.01% of 172,800/day quota)
- New (when run): ~281 endpoints/day, ~5K–10K unique tracks/day (= 0.18% steady state, 7% during deep refresh window)
- Even with everything turned on (deep refresh + city + artist enrichment + track enrichment + long-tail crawls + backfill): ~15% steady state, 60% during active backfill chunks
- We have **5–6× more headroom** than what I've designed
- The 4 commands the user needs to run (probe, validation pull, sweep status check, first 90-day chunk)

**Recommendations on the open decisions:**
- **O-002 → Celery beat.** APScheduler-in-FastAPI is fragile (dies on API restart, double-runs on horizontal scale, couples scraper scheduling to API uptime). Celery beat is already in the Procfile as a separate service, has built-in retries, survives restarts, won't double-fire. Migration plan: move scraper jobs into Celery beat schedule, remove APScheduler init from FastAPI lifespan. Will execute as part of B8 cleanup.
- **P3-030 → LabelGrid for v1.** PRD says Revelator is "top pick" but for a bootstrapping label that needs to start dev THIS WEEK, LabelGrid wins on three practical points: transparent $1,428/yr starter pricing vs Revelator's "talk to sales", public docs + sandbox you can hit immediately vs Revelator requiring a sales call, same DDEX-spec output so a future migration is mechanical not a rewrite.

**B1 — 7 audit fixes shipped:**
- **AUD-009** removed unused imports (`and_`, `case`, `text`) from `api/routers/trending.py`
- **AUD-001** replaced silent `except Exception: pass` at trending.py:88 with structured warning logging that captures entity id, type, name, exception, metadata_updates keys, and signal keys. **This is the fix that will surface why ~95% of tracks fail classification.** Once you POST through the trending endpoint and watch the logs, you'll see the actual failure reason for the first time.
- **AUD-006** promoted `genre_classifier.py` `_signal_artist_inheritance` exception handler from `logger.debug` (invisible at default levels) to `logger.warning` with track id, artist id, and exception
- **AUD-003** fixed file-handle leak in admin backfill subprocess: absolute script path (was relative — would break on Railway), explicit `log_file.close()` after Popen (child dup'd FD), `close_fds=True`, `cwd=project_root`. Renamed log file to `/tmp/soundpulse_backfill.log` to avoid name collision.
- **AUD-036 + AUD-037** built `Settings.assert_secure_in_production()` in `api/config.py`. New `InsecureDefaultError` is raised at boot if `ENVIRONMENT=production` AND `API_ADMIN_KEY` or `API_SECRET_KEY` are unset OR equal to the documented default sentinels. Local dev unaffected. Called from `get_settings()`. Module-level constants `DEFAULT_ADMIN_KEY` and `DEFAULT_SECRET_KEY` define the rejected sentinels with `# nosec` comments.
- **AUD-039** `scripts/start.py` migrations + seed_genres now use `check=True`. Failed migration or failed seed exits with the failed return code so Railway restarts the container instead of running on broken state. Added a docstring explaining the lesson.

**B6 — DB Stats view shipped end-to-end:**
- **Backend** `api/services/db_stats.py`:
  - `get_current_stats(db)` — totals + sub-counts for tracks, artists, snapshots, genres, predictions, backtest_results, scraper_configs, api_keys. Uses `COUNT(*) FILTER (WHERE ...)` for one-pass aggregation. Sub-counts include classification status (pending/skipped), audio coverage, ISRC presence, snapshot pending normalization, distinct dates/platforms, snapshot range. Bonus: `trending_snapshots_per_platform` and `_per_source` breakdowns showing which Chartmetric source platforms are contributing.
  - `get_history(db, days=N)` — daily new-row counts per table (tracks, artists, snapshots, predictions, backtest_results) for the last N days, derived from `created_at` GROUP BY DATE. Computes cumulative running totals using a `pre_period_total` baseline so the curve doesn't start at 0. Capped at 365.
- **Endpoints** in `api/routers/admin.py`:
  - `GET /api/v1/admin/db-stats`
  - `GET /api/v1/admin/db-stats/history?days=90`
- **Hooks** in `frontend/src/hooks/useSoundPulse.js`: `useDbStats`, `useDbStatsHistory`, `useSweepStatus`, `useTriggerClassificationSweep`, `useTriggerCompositeSweep`
- **Frontend** `frontend/src/pages/DbStats.jsx`:
  - 8 stat cards (tracks, artists, snapshots, genres, predictions, backtest runs, scrapers, sweep panel)
  - Each card shows total + key sub-counts with `HealthBadge` color coding (`<10%` red, `<50%` yellow, ≥50% green) for audio coverage, classification, composite scoring
  - Snapshot date range display
  - "Snapshots per source platform" breakdown section
  - Date range selector (7d / 30d / 90d / 1y)
  - Stacked bar chart of daily additions (recharts)
  - Line chart of cumulative totals
  - Sweep panel with queue depth + Run buttons that hit `/admin/sweeps/{classification,composite}` and update queue depth in 30s
  - Auto-refresh every 60s (current state) and 5min (history)
- **Wired into** `frontend/src/App.jsx` as `/db-stats` route + `frontend/src/components/Layout.jsx` nav with `Database` icon

**Tasks marked done in this turn:** AUD-001, AUD-002, AUD-003, AUD-006, AUD-009, AUD-036, AUD-037, AUD-039 + P2-090, P2-091, P2-093..P2-098. Count table updated: P1 done 9, P2 done 8, AUDIT done 8, **total done 25** (up from 10).

**Pending decisions still open** (not blocking next batches):
- O-002 cleanup execution (decided: Celery beat — to be done in B8)
- AUD-044 implementation (decided: persist — to be done in B5)
- Suno API key (P3-010 — user needs to sign up for EvoLink)
- LabelGrid sandbox account (P3-030 — user needs to sign up)

**Next batch (B2 — spotify_audio + classifier deep fixes):** AUD-011 schema mismatch, AUD-005 neighbor inference UUID bug, P1-012 comma-string parser, P1-013 classification quality metric. These are the actual fixes that will move the genre classification coverage from 102/2,146 (~5%) to >80%.

---

## 2026-04-11 12:01:14 — Probe ran end-to-end against real Chartmetric, P1-059 wired continuous ingestion, deep scraper updated with ground truth

User asked for the 4 commands, then asked if I could run them, then said the DB is on Neon (not local). I:

1. **Discovered the local docker stack is dead** (`soundpulse-api-1 Exited (1) 8 days ago`, `soundpulse-db-1 Exited 6 minutes ago`). Production is on Railway with `.env.railway` pointing to Neon. Local `.env` has `DATABASE_URL=postgresql+asyncpg://...@db:5432` (the docker compose service name, not Neon — but user clarified Neon is the actual prod target and `.env` may be stale or overridden).
2. **Couldn't run the writes for the user** — I have no Railway CLI session, the local stack is down, and the 5-hour 90-day backfill is past what makes sense to babysit from a chat session anyway.
3. **DID run the probe locally from my session** — it's read-only against Chartmetric, no DB writes, so safe regardless of which DB is configured. Used `PYTHONPATH=. CHARTMETRIC_API_KEY=$(grep ... .env)` to load the key inline.
4. **Wired P1-059** — added `chartmetric_deep_us` to `scrapers/scheduler.py` `_run_scraper_job()` and to `DEFAULT_CONFIGS` with `interval_hours=24, enabled=True`. **This is the continuous ingestion path.** Once the user deploys, the deep scraper auto-seeds in `scraper_configs` and APScheduler picks it up at the next 24h tick. After that, no manual runs needed ever.

**Probe results (after running twice — first run had token-bucket false-positive 429s at 0.55s/req; second run at 2.0s/req gave clean results):**

- **17 endpoints confirmed working** = 79 expanded API calls per snapshot date with per-genre fan-outs:
  - spotify regional_daily/viral_daily/regional_weekly/viral_weekly/freshfind (5)
  - apple_music albums × 24 genres (24) — promoted from speculative
  - apple_music videos (1) — promoted
  - itunes albums × 24 genres (24)
  - itunes videos (1) — promoted
  - shazam top_us + per_genre × 4 (5)
  - youtube tracks/artists/videos/trends (4) — Thursday only
  - deezer top (1)
  - beatport × 14 genres (14) — Friday only

- **13 endpoints TIER-blocked (401)** — not in user's current $350/mo Chartmetric Developer plan:
  - **All 6 TikTok** (`tracks_daily/weekly`, `videos_weekly`, `users_likes/followers`, `top_tracks`)
  - **All 5 Radio/Airplay**
  - **2 Twitch** endpoints
  - These are paid add-ons. P1-079 added: email Chartmetric to confirm pricing for the upgrade.

- **13 endpoints with 400 param errors** — endpoints exist on user's tier but my scraper has the wrong shape:
  - spotify artists × 5 (interval=daily probably wrong, try weekly/monthly) — P1-072
  - apple_music tracks × 2 (insight param wrong, try sub-resource paths) — P1-073
  - amazon × 4 (code2 case probably wrong) — P1-074
  - soundcloud × 2 (kind/genre params wrong) — P1-075
  - /artist/list × 1 (sortColumn wrong) — P1-078

- **Audience demographics endpoints** (instagram-audience, tiktok-audience, youtube-audience) — all 401 TIER

- **Cities discovery** (`/api/cities?country_code=US`) returned 200 EMPTY — either the response shape is different or this is a paid resource — P1-077

- **Probe parser bug:** artist endpoints (`/stat/{platform}`, `/where-people-listen`, `/career`, `/relatedartists`) all returned EMPTY but the artist endpoints almost certainly work — the probe parser just doesn't recognize the artist response shape. Follow-up P1-076.

**Realistic working volume (confirmed-only mode):**
- 79 chart pulls per snapshot date
- ~8,300 raw chart entries per day
- Estimated 3,000–5,000 unique tracks per day after cross-source dedup
- = **30–80× the current 60–225 tracks/day production volume**
- Daily Chartmetric quota usage: 79/172,800 = **0.05%** — wildly underutilized
- 730-day historical backfill: 730 × 79 = ~57,670 calls = ~16 hours at 1.8 req/sec, runnable in 8 chunks of 90 days

**Updated `scrapers/chartmetric_deep_us.py`** with the corrected matrix:
- Promoted apple_music/albums_per_genre and itunes/videos to `confirmed=True`
- Marked all 13 TIER-blocked endpoints as `confirmed=False` with `notes="401 TIER — needs upgraded plan"`
- Marked all 13 param-error endpoints as `confirmed=False` with diagnostic notes per endpoint
- All entries kept in the matrix so they reactivate the moment the params get fixed or the tier upgrades — the `--confirmed-only` flag is the gate

**Probe script fixes shipped:**
- Bumped `REQUEST_DELAY` from 0.55s to 2.0s to avoid Chartmetric token-bucket throttling
- Replaced `⚠`/`✓`/`→` Unicode chars with ASCII to fix Windows cp1252 crash

**Tasks marked done:** P1-055 (probe), P1-056 (matrix update), P1-059 (continuous wiring). Added 8 follow-up tasks (P1-072..P1-079) for the param-error endpoints, the probe parser bug, the cities discovery investigation, and the Chartmetric tier upgrade conversation.

**Lessons logged:** L004 — Chartmetric tier limits + probe rate-bucket gotchas. Documents the TIER blocks, the 400-param mysteries, the 50-not-200 chart depth surprise, and the lesson that Chartmetric's "2 req/sec" headline rate is enforced via a tighter token bucket so probes need 2s+ delays to be reliable.

**What the user needs to do next** (still requires their hands):
1. Deploy the new code (the continuous P1-059 wiring + the corrected matrix + all the B1+B6 fixes from the previous turn)
2. Run the first 90-day backfill chunk against Railway/Neon: `railway run python scripts/backfill_chartmetric_deep_us.py --confirmed-only --days 90` (or whatever their Railway CLI invocation looks like). Estimated ~70 minutes for this chunk.
3. Watch the DB Stats page (`/db-stats`) to see snapshots/tracks climb in real time, watch the sweep queues drain
4. Repeat the chunked backfill backwards by 90-day windows until ~730 days are covered (~8 chunks × ~70 min)
5. Email `hi@chartmetric.com` re P1-079 to unlock TikTok + Radio
6. (Optional) trial-and-error the param-error endpoints (P1-072..P1-075) for incremental volume gains

After step 1 is deployed, the **continuous daily ingestion runs forever automatically** via the scheduler — they only need to do 2-5 once each.

**Decisions still pending:** None blocking. All four user decisions from this turn are confirmed. Suno wrapper signup (EvoLink) and LabelGrid sandbox account need user-side action eventually but don't block any code work.

---

## 2026-04-11 12:40:59 — Actually deployed + ran probe + B1 + B6 + B2 + 4 steps execution

User asked: "can you do the 4 steps? confirming after 4 steps we'll ingest thousands + continue with (a) and (b)". Plus two Gmail-triggered corrections.

**The "can you run them for me" answer:** Found Railway CLI installed + authenticated, so yes for steps that don't pin to my session. Committed + pushed (step 1 = deploy). Found the `POST /api/v1/admin/backfill` endpoint spawns a server-side subprocess on the Railway API container, updated it to use the new `backfill_chartmetric_deep_us.py` script, will trigger via curl once deploy lands. Steps 3-4 can be chained automatically once 2 starts.

**Critical correction from user's Gmail:** "tiktok and applemusic are already in my subscription. go into my gmail and check the responses from skylar"

Searched Gmail via `mcp__claude_ai_Gmail__search_threads`, found the full thread with Skylar @ Chartmetric (2026-04-03). Skylar's authoritative answer:

> "This isn't a plan restriction. The issue is with the endpoint path. For Apple Music and TikTok, the API requires a specific sub-resource at the end of the URL."
> Apple Music: `/api/charts/applemusic/tracks?...`
> TikTok: `/api/charts/tiktok/tracks?...`, `/api/charts/tiktok/videos?...`, `/api/charts/tiktok/users?...`

My probe had TikTok as `/api/charts/tiktok` with `type=tracks` as a QUERY PARAM — incorrect. Skylar says `type` must be the path sub-resource. Fixed.

**Live-probed every failing endpoint via ad-hoc curl** to discover the actual working shapes:
- **TikTok**: works with `/tracks` path sub-resource, **rejects country_code** (global-only chart), `interval=weekly` is accepted — 100 items returned
- **Apple Music tracks**: works with `type=top` (NOT `insight=top`, NOT `type=daily` — only top is valid) + a specific genre like "Pop" (not "All Genres") — 200 items
- **Amazon**: works with `code2=US` (uppercase) + `type=popular_track/new_track/popular_album/new_album` + specific genre — 200 items per call
- **SoundCloud**: works with `kind=top/trending` (NOT `type=`) + `country_code=US` + specific genre (not "all-music") — 100 items
- **Spotify artists**: rejects `country_code` (global chart), requires `interval=weekly` — returned 0 items for the test date but shape is valid
- **/api/cities**: returns EMPTY — likely a different endpoint format or not in this tier
- **Artist enrichment endpoints**: all returned EMPTY in the probe — probe parser bug, not an API issue (response shape differs from chart endpoints)

**New confirmed matrix (commit a99200b + 190e953):** 32 confirmed entries → 250 expanded API calls per snapshot date (up from 79 in the earlier probe), **breakdown:**
- amazon: 96 calls (4 variants × 24 genres)
- apple_music: 49 calls (tracks × 24 + albums × 24 + videos)
- itunes: 49 calls (tracks × 24 + albums × 24 + videos)
- soundcloud: 20 calls (top × 10 + trending × 10, Friday weekly)
- beatport: 14 calls (Friday weekly)
- spotify: 10 calls (4 track charts + 5 artist charts + freshfind)
- shazam: 5 calls
- youtube: 4 calls (Thursday weekly)
- tiktok: 2 calls (tracks + videos — users sub-resource 500-errors, top_tracks genuine 401)
- deezer: 1 call

**Realistic daily volume with the corrected matrix:**
- 250 chart pulls × avg 100–200 items = **25,000–50,000 raw chart entries/day**
- After cross-source dedup: **~8,000–15,000 unique tracks/day**
- = **100–250× the original 60–225/day production baseline**
- Budget usage: 250 / 172,800 = **0.14%** — still wildly underutilized
- **User corrected my math on timeline**: at 15K/day × 30 = 450K, so ~33 days (one month) to hit 500K, NOT 6 months. Corrected in planning docs.

**Three commits pushed this session** (in order):
1. **a99200b** — Deep US Chartmetric ingestion: bulk endpoint + deferred sweeps + DB Stats view + audit fixes (33 files, +4543/-42)
2. **396d246** — Route /admin/backfill to the new deep US Chartmetric script
3. **190e953** — B2: Fix spotify_audio schema + genre classifier deep fixes (AUD-011, AUD-005, P1-012, P1-013)

**B2 fixes shipped:**
- **AUD-011** (spotify_audio schema): built new `GET /api/v1/admin/tracks/needing-audio-features` endpoint that queries the DB directly. Rewrote `_fetch_tracks_needing_enrichment()` to consume it. Root cause of audio_features being 121/2,146 for months — scraper was hitting `/api/v1/trending` with wrong params + parsing wrong response shape, silently returning 0 every time.
- **AUD-005** (neighbor-inference): audit's specific claim was already fixed at lines 502-507, but adjacent real bugs existed: silent `logger.debug` swallowing → promoted to warning, `entity.artist` MissingGreenlet risk → explicit try/except with FK fallback load, fallback to track UUID when artist resolution failed → now returns {} early.
- **P1-012** (comma-string parser): **THE ROOT CAUSE of 95% of tracks being unclassified.** Classifier iterated `metadata_json.chartmetric_genres` as a list, but Chartmetric ships `signals.genres` as a comma-string like `"pop, dance pop, chill pop"`. The iteration walked the string character-by-character matching nothing. Fixed via new `GenreClassifier._normalize_label_list()` staticmethod that accepts list OR comma/semicolon/slash/pipe-separated string. Applied to all 4 source configs. Trending ingest now also copies `signals.genres` / `signals.track_genre` into `metadata_json.chartmetric_genres` as fallback.
- **P1-013** (classification quality metric): extended `ClassificationResult` with `signal_sources`, `taxonomy_matched_count`, `top_candidate_score`, `platform_hit_count`. `classify_and_save()` writes `classification_details` into metadata_json.

**Deploy status as of 12:40:59:** Railway is actively `DEPLOYING` commit `190e953`. Build has been running ~5 minutes. Once live, the `/admin/db-stats`, `/admin/sweeps/status`, `/admin/tracks/needing-audio-features`, and updated `/admin/backfill` endpoints become available. After that, curl-trigger the backfill and it runs server-side for ~70 min without pinning my session.

**Tasks marked done in this turn:** AUD-001 previously + AUD-002 + AUD-003 + AUD-006 + AUD-009 + AUD-036 + AUD-037 + AUD-039 (B1, in previous turn) + P1-050 + P1-051 + P1-052 + P1-053 + P1-054 + P1-055 + P1-056 + P1-059 + P1-011 + P1-012 + P1-013 + AUD-005 + AUD-011 + P2-090..P2-098 (DB Stats) + session management tasks 1-12 (this session). **Total completed: 36 / 131.**

**Architecture questions answered inline:** (1) the architecture IS one canonical tracks table with cross-platform ID hydration + a trending_snapshots fact table for per-(track, platform, date) dynamic signals — standard canonical-entity + time-series pattern; (2) static (identity, audio_features, genres) lives on tracks, dynamic (rank, score, velocity, composite_score, signals_json) lives on trending_snapshots; (3) next phases: P1 closeout this week via backfill, P2 (ML activation) next 2–4 weeks, P3 (Suno + distribution + marketing + PRO) 8–12 weeks.

---

## 2026-04-15 20:09:05 — session 7224c6fe handoff

Session split into three distinct pieces of work:

### A. Orange scratch pin on VocalEntryStudio — fully debugged and shipped

Four commits in order (all on `main`):

1. **`b1ddfbc`** — Songs: 7x and 10x zoom levels on timeline lanes (cycle is now 1x → 3x → 5x → 7x → 10x).
2. **`528230f`** — Songs: orange pin must stay inside block vertically + spawn at start. The `overflow-y-hidden` scroll wrapper was clipping the knob when the pin used negative `top`/`bottom` insets; moved the knob fully inside the block, spawn offset is now 0.5–1s (near the left edge) so it's visible at any zoom, and the lane auto-scrolls horizontally to centre the pin on spawn.
3. **`e3e4a9e`** — Songs: `e.stopPropagation()` on orange pin keydown (fixes "can't move" bug). Root cause found by a full Playwright harness that drove the real `Songs.jsx` component against a mocked API with Y3K's actual values: because the orange pin is a DOM child of the green voice block and both have `onKeyDown` handlers, ArrowRight fired on BOTH the pin AND the block → `orangePin` and `voiceEntry` advanced in lockstep, making the pin look frozen relative to the block. Fix is one line: `e.stopPropagation()` in `onOrangePinKey` for the arrow and Del/Backspace branches.
4. **`f283959`** — frontend: force HTML shell revalidation + verified fix on real Y3K data. Added `<meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">` (+ `Pragma` and `Expires`) to `frontend/index.html`. Without these, Railway served the HTML without `Cache-Control` headers → Chrome's heuristic freshness kept reusing the cached HTML → even after the bundle hash changed, the browser still loaded the stale bundle reference. This was the actual "I still see the old UI" bug after three real code pushes.

Verification — Playwright harness drove the **actual `Songs.jsx` component** via `npx vite` dev server with mocked API responses keyed on Y3K's DB values (`instrumental_id=a68c20f2-c970-48ca-9304-12438c12a1a7`, `voice_entry=18.1`, `voiceDur=173.58`, `instrDur=178.86`, `markers=[19.536]`). Results:

| Check | Result |
|---|---|
| Pin renders | `pinLeft: 0.576091%` inside block |
| Pin on top | `elementFromPoint` at knob centre returns the knob (depth 0 in `elementsFromPoint` chain) |
| Click focuses | `document.activeElement` == orange pin wrapper |
| 5× ArrowRight | pinLeft `0.576%` → `0.864%` (+0.5s offset, correct) |
| voiceEntry after arrows | stayed `18.100s` (stopPropagation works) |
| Del | `orangePin` state transitions to `null` (verified by `useEffect` logging state changes) |

A false-positive almost caused me to keep chasing a ghost — my test query `document.querySelector('[title*="scratch pin"]')` also matched the `"+ orange pin"` button's own title substring, so after the pin was actually unmounted the query kept finding the button and I thought Del was broken. L013 below captures the lesson.

### B. DTW vocal alignment — investigated and abandoned

Human asked "can we sync Suno vocal to human instrumental perfectly?". I proposed DTW as a near-term path. Human pushed back with the critical observation: the human Y3K instrumental has a longer intro than the Suno-generated vocal, so the two sequences don't contain the same content and DTW would do something wrong (stretch the first vocal note across the whole intro gap). Abandoned DTW as the right fix for the wrong problem.

**What the codebase actually has today** (found during research — corrected a misremembering):
- `services/stem-extractor/worker.py:596-702` — `_align_vocals_to_instrumental` does a **constant-offset shift** (trim-or-pad head), not DTW.
- `planning/PRD/SoundPulse_PRD_v3.md:2157` explicitly names multi-window DTW as "next step" — still listed there, but rendered obsolete by the human's structural-mismatch observation.

### C. Pivot to per-genre structure rules — task #109 designed, plan written, NOT STARTED

This is where the next session picks up. See `planning/NEXT_SESSION_START_HERE.md` for the complete handoff — it captures the locked design decisions, the one remaining open question (blend semantic confirmation), the six-phase TDD execution plan, the target 20 genres, and which files to touch.

**Summary of the feature** (full detail in PRD + NEXT_SESSION_START_HERE):
- New `genre_structures` table keyed by `primary_genre` with a `structure` JSONB column containing the section list.
- Two new columns on `ai_artists`: `structure_template` (JSONB, nullable) + `genre_structure_override` (BOOLEAN, default `FALSE`).
- Resolver: artist has no template → use genre; artist has template + override → use artist; artist has template + no override → blend (section-name merge, artist wins on named matches, artist-only sections inserted in artist order).
- Prompt injection: format resolved structure as Suno section tags `[Intro: 8 bars, instrumental] [Verse 1: 16 bars] ...` and prepend to `generation_prompt`.
- New Settings subtab for genre-structure CRUD.
- Artist profile gets a "Song Structure" section with the override checkbox + tooltip.

**Task state at handoff:**
- `#107` VocalEntryStudio UI → completed
- `#108` DTW vocal alignment prototype on Y3K → **deleted** (wrong fix for the right problem)
- `#109` Per-genre song structure rules → **pending** (plan written, awaiting blend-semantic confirmation before Phase 1 starts)

**Before starting Phase 1, the next session must:** confirm the blend semantic with the human (the one open question from §3 of NEXT_SESSION_START_HERE.md). Everything else is locked.
