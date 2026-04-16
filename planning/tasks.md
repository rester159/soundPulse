# SoundPulse Tasks

> Single source of truth for backlog and progress. All agents must follow the protocol in `CLAUDE.md` (claim → execute → mark done).
>
> **Status values:** `todo` · `in_progress` · `blocked` · `done`
> **Phases:** P1 = Data Foundation closeout · P2 = Prediction + Song DNA · P3 = Autonomous Pipeline · O = Ops/Quality (cross-cutting)
> **Granularity:** each task is sized to fit one focused session. If a task balloons mid-execution, split it and update this file.

---

## 🟢 Live top-of-backlog — next session starts here

- **`#109` Per-genre song structure rules: config + Suno prompt injection + Settings UI** — `pending`. Plan written, awaiting blend-semantic confirmation from user before Phase 1. Full briefing in `planning/NEXT_SESSION_START_HERE.md`.

Six phases (TDD — failing test first each phase):
1. Schema + seed — migrations 033 (`genre_structures` table), 034 (two new `ai_artists` cols) + seed 20 genres
2. Prompt injection — `structure_resolver.py` + `structure_prompt.py` wired into song gen orchestrator
3. Admin API — `/api/v1/admin/genre-structures` CRUD + artist-patch extension
4. Settings subtab + artist-profile "Song Structure" section with override checkbox + tooltip
5. (rolls into 1) — research-backed structures for the top 20 genres
6. Y3K regeneration + structural-compliance measurement

Related:
- **`#106` Add admin retry-stem-job endpoint + Songs UI button** — `pending`, deferred. Nice-to-have; not blocking `#109`.
- **`#107` Build VocalEntryStudio UI with draggable pins + two-track preview** — `done`. Four commits pushed 2026-04-15 (`b1ddfbc`, `528230f`, `e3e4a9e`, `f283959`). Orange scratch pin verified on real Y3K data via Playwright harness.
- **`#108` DTW vocal alignment prototype on Y3K** — `deleted` (2026-04-15). Superseded by `#109` after human observed structural mismatches can't be fixed by time-warping (see L014 in `planning/lessons.md`).

---

---

## Counts at a glance

| Phase | Open | In-progress | Blocked | Done |
|---|---|---|---|---|
| P1 — Data Foundation closeout | 35 | 1 | 0 | 17 |
| P2 — Prediction + Song DNA | 30 | 0 | 0 | 8 |
| P3 — Autonomous Pipeline (stubs) | 28 | 0 | 0 | 0 |
| O — Ops & Quality | 8 | 0 | 0 | 0 |
| AUDIT — 2026-04-11 deep code audit | 30 | 0 | 0 | 11 |
| **Total** | **131** | 1 | 0 | 36 |

---

## Phase 1 — Data Foundation closeout

### P1.A — `spotify_audio` scraper (broken: enabled but never runs; 121/2,146 tracks have audio features)

| ID | Title | Status | Assigned | Depends on | Notes |
|---|---|---|---|---|---|
| P1-001 | Confirm `spotify_audio` row exists in `scraper_configs` and `enabled=true` | todo | — | — | Run a SELECT against prod DB or admin endpoint |
| P1-002 | Audit `scrapers/scheduler.py`: does it iterate scraper_configs or hardcode a list? | todo | — | — | If hardcoded, that's the root cause |
| P1-003 | Reproduce the scraper run manually via `python -m scrapers.spotify_audio` and capture stdout/exception | todo | — | P1-001 | |
| P1-004 | Fix the actual root cause (scheduler wiring / auth / silent exception) | todo | — | P1-002, P1-003 | **Audit finding (AUD-011): root cause is API schema mismatch in `scrapers/spotify_audio.py:119-139`. `_fetch_tracks_needing_enrichment()` calls `/api/v1/trending` expecting `entity_identifier`+`signals` keys, but the trending GET returns `entity`+`scores`. Always returns 0 → exits early.** Also see AUD-004 (duplicate `spotify_audio` key in `scheduler.py:183/185` — line 183 silently overwritten). |
| P1-005 | Add `--backfill --top N` CLI flag to populate audio features for the top-N trending tracks | todo | — | P1-004 | Run for top 200 once it works |
| P1-006 | Unit test: mocked Spotify API response → assert `tracks.audio_features` is populated | todo | — | P1-004 | TDD: write test first |
| P1-007 | Document the fix in `planning/lessons.md` with root cause + prevention | todo | — | P1-004 | Per CLAUDE.md learn-from-mistakes rule |

### P1.B — Genre classifier sparse output (102/2,146 tracks classified)

| ID | Title | Status | Assigned | Depends on | Notes |
|---|---|---|---|---|---|
| P1-010 | Read `api/services/genre_classifier.py` end-to-end and document required input signals | todo | — | — | |
| P1-011 | Identify why ~95% of tracks fail classification — likely classifier expects structured `signals.spotify_genres` but Chartmetric provides comma-string `signals.genres` | done | claude | P1-010 | Confirmed: classifier iterated `metadata_json.chartmetric_genres` as a list but Chartmetric ships `signals.genres` as comma-string. Walked char-by-char, matching nothing. Fixed by P1-012. |
| P1-012 | Add a parser path: when structured genre arrays are empty, split `signals.genres` comma-string → normalize → match to taxonomy | done | claude | P1-011 | New `GenreClassifier._normalize_label_list()` staticmethod accepts list OR comma/semicolon/slash/pipe-separated string. Applied to all 4 source lists. Also trending ingest now copies `signals.genres`/`signals.track_genre` into `metadata_json.chartmetric_genres` as fallback. Classifier also reads `meta.get("genres")` directly as a secondary key. Commit 190e953. |
| P1-013 | Add classification quality metric to `metadata_json`: `{quality: high|medium|low, source: structured|comma_string|fallback}` | done | claude | P1-012 | Extended `ClassificationResult` dataclass with `signal_sources`, `taxonomy_matched_count`, `top_candidate_score`, `platform_hit_count`. `classify_and_save()` writes `classification_details` dict into `metadata_json` alongside existing `classification_quality`. Surfaces in DB Stats and enables debugging why classification succeeded or failed. Commit 190e953. |
| P1-014 | Backfill script: re-run classifier on all 2,146 existing tracks | todo | — | P1-012 | Idempotent — safe to re-run |
| P1-015 | Expose classification coverage % in admin dashboard (e.g. "1,847 / 2,146 tracks classified — 86%") | todo | — | P1-014 | |
| P1-016 | Document the fix in `planning/lessons.md` | todo | — | P1-014 | |

### P1.C — `POST /api/v1/trending` ingest timeout on Neon

| ID | Title | Status | Assigned | Depends on | Notes |
|---|---|---|---|---|---|
| P1-020 | Profile the handler with a representative Chartmetric payload — log query count + total time | todo | — | — | Use SQLAlchemy event listeners or explicit timing |
| P1-021 | Identify N+1 patterns in `entity_resolution.py` (per-row SELECTs) | todo | — | P1-020 | **Audit finding (AUD-002): the genre classifier runs synchronously inside the async ingest endpoint (`api/routers/trending.py:82-87`). It does 6+ DB queries per entity. Defer to a background task or batch at end of scraper run.** |
| P1-022 | Add `POST /api/v1/trending/bulk` taking arrays — single transaction, batched upserts | todo | — | P1-021 | |
| P1-023 | Replace per-row INSERTs with `INSERT ... ON CONFLICT DO UPDATE` (upsert) | todo | — | P1-021 | |
| P1-024 | Update Chartmetric scraper to use the new bulk endpoint | todo | — | P1-022 | |

### P1.D — Scheduler reliability on Railway

| ID | Title | Status | Assigned | Depends on | Notes |
|---|---|---|---|---|---|
| P1-030 | Verify all enabled scrapers ran in the last 24h (admin endpoint or DB query) | todo | — | — | |
| P1-031 | Decide: APScheduler-in-FastAPI-lifespan vs Celery beat — pick one. The dual setup is fragile and confusing | todo | — | — | Architectural decision; needs a 1-page write-up before execution. See O-002. |

### P1.E — Chartmetric coverage expansion (NEW — answers user question 2026-04-11 "why so few records?")

**Diagnosis:** Current scraper queries 6 chart endpoints (4 in backfill scripts), all US-only, top ~200 each. Addressable scope is ~300–600 unique tracks/day after dedup. Currently consuming <2% of Chartmetric's 170K/day rate budget. PRD §7 has the full scope clarification.

**P1.E.1 — Multi-country expansion (deferred per user direction 2026-04-11)**

User direction: go super deep on US first instead of multi-country. The original multi-country tasks are kept here as backlog but moved behind P1.E.2 in priority.

| ID | Title | Status | Assigned | Depends on | Notes |
|---|---|---|---|---|---|
| P1-040 | Document the current import scope inline in `scrapers/chartmetric.py` (the 6 endpoints, US-only, ~200 each) so future devs don't have to re-derive it | todo | — | — | Doc-only — superseded by PRD §7.2 |
| P1-041 | Lift `country_code` from hardcoded `"us"` to a list parameter on the scraper config; default `["us"]` | todo | — | — | `chartmetric.py:203`, `backfill_*.py:93/97` — deferred per user direction |
| P1-042 | Add 7 additional countries to scraper config: GB, DE, JP, BR, MX, FR, KR, IN — runs after every 4h tick | todo | — | P1-041, AUD-002 | **Deferred per user direction** — US-deep first |
| P1-043 | Add Apple Music + TikTok chart endpoints to the backfill scripts (currently only spotify+shazam) | done | — | — | Done as part of P1.E.2 — `chartmetric_deep_us.py` covers Apple Music + TikTok in the backfill matrix |
| P1-044 | Investigate Chartmetric API: does the `/charts/spotify` endpoint support a `limit` param for top-1000 instead of top-200? Document and use if available | in_progress | probe | — | Probe script `scripts/chartmetric_probe.py` tests `limit/size/count/max` × `500/1000` and reports |
| P1-045 | Investigate Chartmetric per-genre Spotify charts (`/api/charts/spotify/genres/{genre_id}` or similar) for long-tail discovery; gate on plan tier | todo | — | — | Speculative endpoint included in `ENDPOINT_MATRIX` — probe will discover |
| P1-046 | Add Billboard verticals (Hot 100, country, R&B, dance, rock) via Chartmetric `/api/charts/billboard` if available | in_progress | — | — | All 8 Billboard verticals are in `ENDPOINT_MATRIX` as speculative — confirmation depends on probe |
| P1-047 | Re-run `backfill_deep.py --days 365` against the expanded scope after P1-042 + ingest fix lands | todo | — | P1-042, P1-022, P1-023 | Replaced by P1-058 below for the US-deep path |
| P1-048 | Decide whether the daily Chartmetric scraper should also run on a per-country basis (chunked across the day) to spread load | todo | — | P1-042 | Deferred per user direction |
| P1-049 | Add a "scope dashboard" to the admin UI showing entries fetched per chart × country × day, so coverage gaps are visible | todo | — | P2-090 | Cross-ref P2.I (DB stats view) |

**P1.E.2 — US-deep expansion (NEW — user direction 2026-04-11 "exhaust the chartmetric subscription")**

Goal: pull every chart, every chart type, every US city, max depth, full historical backfill. PRD §7.2 has the complete MECE definition. Implementation = `scrapers/chartmetric_deep_us.py` + `scripts/chartmetric_probe.py` + `scripts/backfill_chartmetric_deep_us.py` + bulk ingest endpoint.

| ID | Title | Status | Assigned | Depends on | Notes |
|---|---|---|---|---|---|
| P1-050 | Add bulk ingest endpoint `POST /api/v1/trending/bulk` taking up to 1000 items in one transaction, ON CONFLICT DO NOTHING for snapshot dedup, deferred classification | done | — | — | Implemented in `api/routers/trending.py` + `api/schemas/trending.py`. Tags entities `needs_classification: true` in metadata_json |
| P1-051 | Define the MECE space for the deep US pull (every platform × chart type × geo × date × depth) in PRD §7.2 | done | — | — | Done — see PRD §7.2 |
| P1-052 | Build `scrapers/chartmetric_deep_us.py` — `ChartmetricDeepUSScraper` with `ENDPOINT_MATRIX`, `US_CITIES_TIER1`, bulk-buffer flushing, `backfill()` entry point | done | — | P1-050 | Confirmed + speculative endpoints. City pulls gated on `CITY_PARAM_NAME` discovery |
| P1-053 | Build `scripts/chartmetric_probe.py` — probes every speculative endpoint, every city-param candidate (`city_id/city_code/cityId/city/city_slug`), every depth-param candidate (`limit/size/count/max` at 500/1000), and 7 artist endpoint patterns | done | — | P1-052 | Reports working endpoints + city param + depth param + artist paths |
| P1-054 | Build `scripts/backfill_chartmetric_deep_us.py` — date range CLI, `--confirmed-only` flag, calls `ChartmetricDeepUSScraper.backfill()` | done | — | P1-052 | Estimated ~3.5 hours confirmed-only @ 730 days, ~12 hours full |
| P1-055 | **RUN THE PROBE** — `python scripts/chartmetric_probe.py` and capture the output | done | claude | P1-053 | Ran twice (first at 0.55s/req hit rate-limit token bucket, second at 2.0s/req gave clean results). 17 confirmed endpoints, 13 TIER-blocked, 13 with wrong params. Output captured in lessons.md L004. |
| P1-056 | Update `scrapers/chartmetric_deep_us.py` based on probe output: promote confirmed-OK speculative endpoints to `confirmed=True`, mark TIER and 400-error endpoints as `confirmed=False` with diagnostic notes | done | claude | P1-055 | Promoted apple_music/albums_per_genre and itunes/videos. Marked all 13 TIER endpoints (TikTok×6, Radio×5, Twitch×2) as confirmed=False with `notes="401 TIER"`. Marked all 13 param-error endpoints (Spotify artists×5, Apple Music tracks×2, Amazon×4, SoundCloud×2) as confirmed=False with diagnostic notes for each. |
| P1-057 | **RUN THE CONFIRMED-ONLY BACKFILL** — `python scripts/backfill_chartmetric_deep_us.py --confirmed-only --days 90` (chunked) | todo | — | P1-056 | **User must execute against Railway/Neon prod.** 90 days × 79 calls = ~7,100 calls = ~70 minutes per chunk. Run in 8 chunks of 90 days to cover 2 years. |
| P1-058 | **RUN THE FULL BACKFILL** — `python scripts/backfill_chartmetric_deep_us.py --days 730` (includes any newly fixed endpoints) | todo | — | P1-057, P1-072..P1-075 | Run after the param fixes land. Will add ~30% more endpoints. |
| P1-059 | Add the deep refresh to the scheduler — runs once per day pulling yesterday across the full ENDPOINT_MATRIX. **Continuous ingestion path.** | done | claude | P1-056 | Added `chartmetric_deep_us` to `scrapers/scheduler.py` `_run_scraper_job` (instantiates `ChartmetricDeepUSScraper`) and to `DEFAULT_CONFIGS` with `interval_hours=24, enabled=True`. Once deployed, runs automatically every 24h via APScheduler. |
| P1-072 | Investigate Spotify artists 400 error — `interval=daily` is invalid for `/api/charts/spotify/artists`. Try `interval=weekly` and `interval=monthly` | todo | — | P1-055 | All 5 type variants (monthly_listeners, popularity, followers, playlist_count, playlist_reach) returned 400. Apidoc says interval is required but doesn't specify per-type validity. |
| P1-073 | Investigate Apple Music tracks 400 — `?insight=top` and `?insight=daily` both 400. Try sub-resource paths `/api/charts/applemusic/tracks/top` and `/api/charts/applemusic/tracks/daily` | todo | — | P1-055 | Currently we only get Apple Music albums per genre (24 endpoints). Tracks per genre would add another 48 endpoints if this works. |
| P1-074 | Investigate Amazon 400 — try `code2=US` (uppercase) instead of `code2=us`, also try `country_code` instead of `code2`. Per the apidoc, Amazon uses `code2` but case may matter | todo | — | P1-055 | All 4 insight variants (popular_track/new_track/popular_album/new_album) returned 400. Worth ~96 endpoints if fixed. |
| P1-075 | Investigate SoundCloud 400 — `kind=top` and `kind=trending` both failed. Try without `country_code` (SoundCloud may be global only), or try different genre values | todo | — | P1-055 | 20 endpoints if fixed. Apidoc lists supported countries: GLOBAL, US, CA, DE, GB, IE, FR, NL, AU, NZ. |
| P1-076 | Fix probe parser to handle artist endpoint response shapes — currently reports artist `/stat/{platform}` and `/where-people-listen` as EMPTY because the response shape doesn't have a `data` key array | todo | — | P1-055 | Probe bug, not API bug. Artist endpoints almost certainly work — just need to teach the probe how to parse them. |
| P1-077 | Investigate `/api/cities?country_code=US` discovery — returned 200 but EMPTY. Try `code2=US`, try `/api/search?type=cities&q=US`, try checking if cities is a separate paid resource | todo | — | P1-055 | Without working city IDs we can't add per-city Apple Music charts (P1-070) or per-city Shazam (P1-071). |
| P1-078 | Investigate `/api/artist/list?code2=US` 400 — `sortColumn=sp_monthly_listeners` is probably wrong. Try `cm_artist_score`, `sp_followers`, etc. | todo | — | P1-055 | Long-tail US artist crawl. Worth pursuing for exhaustive coverage. |
| P1-079 | **Email hi@chartmetric.com** to confirm which Chartmetric plan unlocks: TikTok charts (all 6 endpoints), Radio/Airplay (5 endpoints), Instagram/YouTube audience demographics. Get pricing for the upgrade | todo | — | P1-055 | TikTok especially is high-value for our use case. Worth knowing the upgrade cost vs value. |
| P1-060 | Background sweep: process `metadata_json.needs_classification = true` entities — runs the genre classifier in a Celery task batch, clears the flag | done | — | P1-050 | `api/services/classification_sweep.py` + Celery task `run_classification_sweep` + APScheduler job `sweep_classification` (15-min interval) + admin endpoint `POST /api/v1/admin/sweeps/classification`. Per-entity error logging, 3-strike retry-with-skip-sentinel. **L003 in lessons.md** |
| P1-061 | Background sweep: recompute composite scores for entities ingested via bulk path — runs `recalculate_composite_for_entity` on a queue, pulls from rows with `normalized_score=0` and `created_at > last_run` | done | — | P1-050 | `api/services/composite_sweep.py` + Celery task `run_composite_sweep` + APScheduler job `sweep_composite` (15-min interval) + admin endpoint `POST /api/v1/admin/sweeps/composite`. Uses `signals_json->>'normalized_at'` as the idempotency marker |
| P1-062 | Test: `tests/test_api/test_trending_bulk.py` — POST a batch of 100 records, assert: ingested=100 first call, duplicates=100 on retry, errors=0, entities_created>0 | done | — | P1-050 | 9 tests written: happy path, dedup on retry, invalid platform 400, no identifier 422, empty batch 422, oversize batch 422, needs_classification marker, normalized_score=0 marker, classification sweep clears flag, composite sweep clears `normalized_score=0` |
| P1-063 | Add artist enrichment lane: `scrapers/chartmetric_artist_enrichment.py` pulling `/stat/{platform}` × 6 platforms + `/where-people-listen` for each unique artist | todo | — | P1-058 | PRD §7.2 axis 5 — separate execution lane with its own rate budget |
| P1-064 | Add track enrichment lane: pull `/api/track/{id}` for every unique track on first appearance | todo | — | P1-058 | Lifetime one-shot per track |
| P1-065 | Per-city US ENDPOINT_MATRIX additions — once probe seeds city IDs from `/api/cities?country_code=US`, add `/api/charts/applemusic/tracks?city_id={id}` and `/api/city/{id}/{tracks,artists}` per US city | todo | — | P1-055 | Documented in PRD §7.2 axis 3 |
| P1-066 | Long-tail crawl lane: `/api/artist/list?code2=US&sortColumn=sp_monthly_listeners&limit=100` paginated by offset for exhaustive US artist enumeration | todo | — | P1-058 | PRD §7.2 axis 7 |
| P1-067 | Long-tail crawl lane: `/api/track/list?code2=US` paginated for exhaustive US track enumeration | todo | — | P1-058 | PRD §7.2 axis 7 |
| P1-068 | Long-tail crawl lane: `/api/playlist/spotify/lists?code2=US&tags={genre_id}` per-genre US playlist crawl | todo | — | P1-058 | PRD §7.2 axis 7 |
| P1-069 | **Fix existing `scrapers/chartmetric.py` line 60-65: `type=plays` is NOT a valid value for `/api/charts/spotify`** — only `regional` and `viral` are valid. Remove the `plays` chart endpoint from `CHART_ENDPOINTS` and from `backfill_chartmetric.py:57-62` and `backfill_deep.py:62-67` | done | — | — | Removed from all 3 files with explanatory comments referencing P1-069 / L001. **L001 in lessons.md** |
| P1-070 | Add per-city Apple Music chart fetcher: `/api/charts/applemusic/tracks?city_id={id}` once city IDs are seeded — Apple is the only platform that supports per-city tracks directly | todo | — | P1-065 | |
| P1-071 | Add per-city Shazam chart fetcher: `/api/charts/shazam?city={city_name}` (uses NAME, not ID) — enumerate via `/api/charts/shazam/US/cities` | todo | — | P1-055 | |

---

## Phase 2 — Prediction + Song DNA

### P2.A — Training subprocess cwd bug

| ID | Title | Status | Assigned | Depends on | Notes |
|---|---|---|---|---|---|
| P2-001 | Find the call site of `subprocess.run([sys.executable, "scripts/train_model.py"])` | todo | — | — | **Audit finding (AUD-017): confirmed at `scrapers/tasks.py:116-120`. The `cwd=project_root` is redundant because `script_path` is already absolute via `os.path.join(project_root, ...)`. Plus stderr only captures last 500 chars on failure — losing context. AUD-013: same file lines 92-94, 143-144 use `asyncio.new_event_loop()` instead of idiomatic `asyncio.run()`.** |
| P2-002 | Replace subprocess with a direct function call to `ml.train.train()` (preferred) or pass explicit `cwd=settings.PROJECT_ROOT` | todo | — | P2-001 | Direct call is cleaner — no subprocess needed |
| P2-003 | Verify the change works in local docker compose AND on Railway | todo | — | P2-002 | |

### P2.B — First successful LightGBM training run

| ID | Title | Status | Assigned | Depends on | Notes |
|---|---|---|---|---|---|
| P2-010 | Read `ml/train.py` end-to-end and document the data pipeline | todo | — | — | |
| P2-011 | Verify `min_samples` threshold matches reality (config: 30 dev / 500 prod). Lower if needed for first run | todo | — | P2-010 | |
| P2-012 | Run training manually against current DB; capture errors | todo | — | P1-030, P2-002 | Needs stable scraper data first |
| P2-013 | Persist trained model to `ml/saved_models/meta_learner.pkl` | todo | — | P2-012 | |
| P2-014 | Test: mocked DB rows → train → assert model file exists and predicts deterministically | todo | — | P2-012 | |
| P2-015 | Wire daily 3am Celery beat task to call `ml.train.train()` directly | todo | — | P2-002, P2-013 | |

### P2.C — Predictions populate

| ID | Title | Status | Assigned | Depends on | Notes |
|---|---|---|---|---|---|
| P2-020 | Locate or build the predictions generation script (per PRD: every 6h, top 50 entities) | todo | — | — | |
| P2-021 | Wire to Celery beat (every 6h, :45 past) | todo | — | P2-020, P2-015 | |
| P2-022 | Verify rows land in `predictions` table after first run | todo | — | P2-021 | |
| P2-023 | Confirm `GET /api/v1/predictions?horizon=7d` returns non-empty results | todo | — | P2-022 | |

### P2.D — Backtesting populate + Model Validation page

| ID | Title | Status | Assigned | Depends on | Notes |
|---|---|---|---|---|---|
| P2-030 | Read `api/services/backtest_service.py` — confirm monthly-slice iteration logic | todo | — | — | |
| P2-031 | Run a manual backtest run: `POST /api/v1/backtesting/run` → confirm rows in `backtest_results` | todo | — | P2-013 | |
| P2-032 | Wire daily 4:30am beat task | todo | — | P2-031 | |
| P2-033 | Verify ModelValidation page renders real timeline + metric cards (recent commit fixed nesting) | todo | — | P2-032 | |
| P2-034 | Add empty-state UI: "No backtest data yet — runs after first model train" | todo | — | P2-033 | |
| P2-035 | Wire genre filter dropdown to `/api/v1/backtesting/breakdown` | todo | — | P2-033 | |

### P2.E — Genius lyrics scraper

| ID | Title | Status | Assigned | Depends on | Notes |
|---|---|---|---|---|---|
| P2-040 | Enable `genius_lyrics` row in `scraper_configs` | todo | — | — | Currently disabled per PRD |
| P2-041 | Verify the scraper runs end-to-end and populates `signals_json.themes` | todo | — | P2-040 | |
| P2-042 | Surface themes in the trending API response so SongLab can use them | todo | — | P2-041 | |

### P2.F — Song Lab UI completion

| ID | Title | Status | Assigned | Depends on | Notes |
|---|---|---|---|---|---|
| P2-050 | Confirm Song Lab page hits `/api/v1/blueprint/genres` correctly | todo | — | — | |
| P2-051 | Render genre opportunity list with momentum labels (rising/stable/declining) | todo | — | P2-050 | |
| P2-052 | Render blueprint card: sonic profile (tempo/key/energy/mood) + lyrical profile (themes) | todo | — | P2-051 | Needs P1.B fix to have meaningful data |
| P2-053 | Add prompt-output panel with copy-to-clipboard | todo | — | P2-052 | |
| P2-054 | Add model selector (Suno / Udio / SOUNDRAW / MusicGen) wired to `POST /blueprint/generate` | todo | — | P2-052 | |

### P2.G — Hideable Assistant panel (NEW — see PRD §21.1)

| ID | Title | Status | Assigned | Depends on | Notes |
|---|---|---|---|---|---|
| P2-060 | Create `frontend/src/contexts/AssistantVisibilityContext.jsx` with hook that reads/writes `localStorage['soundpulse.assistant.visible']` | todo | — | — | TDD: write Vitest test first |
| P2-061 | Wrap app root in `<AssistantVisibilityProvider>` (in `main.jsx` or `App.jsx`) | todo | — | P2-060 | |
| P2-062 | Update `Layout.jsx` to conditionally render the Assistant `<aside>` based on context | todo | — | P2-061 | |
| P2-063 | Add collapse arrow button to `AssistantPanel.jsx` header (left of "Assistant" label) | todo | — | P2-061 | |
| P2-064 | Add floating re-open button on the right edge when panel is hidden (icon: `MessageSquare`) | todo | — | P2-062 | |
| P2-065 | Add `Cmd/Ctrl + .` keyboard shortcut handler at the layout level | todo | — | P2-061 | |
| P2-066 | Vitest: toggling persists to localStorage; remount reads it back | todo | — | P2-060 | |
| P2-067 | Manual UI test: hide/show smooth, no layout jump, main content reflows | todo | — | P2-062, P2-063, P2-064 | Follow CLAUDE.md "Verification before done" |

### P2.H — LLM call logging (NEW — CLAUDE.md mandates this; not yet implemented)

| ID | Title | Status | Assigned | Depends on | Notes |
|---|---|---|---|---|---|
| P2-070 | Create alembic migration 006 for `llm_calls` table per `schema.md` Part II | todo | — | — | |
| P2-071 | Build `api/services/llm_logger.py` — context manager / decorator that logs every call | todo | — | P2-070 | |
| P2-072 | Wrap the Groq call in `api/services/assistant_service.py` | todo | — | P2-071 | |
| P2-073 | Add `GET /api/v1/admin/llm-usage` returning aggregates by action_type and day | todo | — | P2-072 | |
| P2-074 | Test: mock Groq response → assert one row in `llm_calls` with correct token counts | todo | — | P2-072 | TDD |

### P2.I — DB stats view (NEW — user request 2026-04-11 #3)

A diagnostic view answering "what's actually in the database, and how is it growing?" Backend endpoint + frontend page. PRD §22.2 has the full spec.

| ID | Title | Status | Assigned | Depends on | Notes |
|---|---|---|---|---|---|
| P2-090 | Build `GET /api/v1/admin/db-stats` returning current totals across all tables (tracks, artists, snapshots, predictions, backtest_results, scraper_configs, api_keys) with key sub-counts (e.g. tracks.with_audio_features, with_genres, with_isrc) | done | — | — | `api/services/db_stats.py` `get_current_stats()`. Uses `COUNT(*) FILTER (WHERE ...)` for sub-counts in one pass per table. Also returns `trending_snapshots_per_platform` and `_per_source` breakdowns. Bonus: includes pending_classification, classification_skipped, pending_normalization counts. |
| P2-091 | Build `GET /api/v1/admin/db-stats/history?days=N` returning daily new-row counts per table for the last N days, derived from `created_at` timestamps | done | — | P2-090 | `get_history()` groups by `DATE(created_at)` per table, fills missing days with 0, computes cumulative running totals using a `pre_period_total` baseline. Capped at 365. |
| P2-092 | Test: insert known fixtures, assert endpoint counts match | todo | — | P2-090, P2-091 | TDD verification — needs to be added to `tests/test_api/test_admin.py` (which doesn't exist yet — see AUD-031). Functional verification pending user running the page against real data. |
| P2-093 | Build new frontend page `frontend/src/pages/DbStats.jsx` at route `/db-stats` — top section: cards for current state | done | — | P2-090 | 8 stat cards (tracks, artists, snapshots, genres, predictions, backtest_runs, scrapers) + sweep panel. Color-coded health badges (`<50%` yellow, `<10%` red). |
| P2-094 | DbStats page middle section: stacked bar chart of daily additions per table, last 90 days (recharts) | done | — | P2-091, P2-093 | Stacked bars for snapshots/tracks/artists/predictions per day. |
| P2-095 | DbStats page bottom section: line chart of cumulative totals per table over time | done | — | P2-091, P2-093 | 4 lines, pre-period baseline included so the curve doesn't start at 0. |
| P2-096 | DbStats date range filter (7d / 30d / 90d / custom) | done | — | P2-094, P2-095 | 7d / 30d / 90d / 1y selector at the top of the growth section. |
| P2-097 | Color-coded warnings on cards when sub-counts are <50% of total (e.g. classification coverage <50% → yellow, <10% → red) | done | — | P2-093 | `HealthBadge` component with thresholds at 10/50%. Applied to audio_features coverage, classification coverage, composite scoring coverage. |
| P2-098 | Sweep control panel embedded in DbStats — shows queue depth + Run buttons that hit `/admin/sweeps/{classification,composite}` | done | — | P2-090, P1-060, P1-061 | Bonus — wires the deferred sweeps directly into the diagnostic page. Click "Run sweep" → see updated queue depth in 30s. |

---

## Phase 3 — Autonomous Pipeline (stubs)

### P3.A — Schema migrations for Phase 3

| ID | Title | Status | Assigned | Depends on | Notes |
|---|---|---|---|---|---|
| P3-001 | Alembic 007: `ai_artists` table | todo | — | — | Per `schema.md` Part II |
| P3-002 | Alembic 008: `ai_artist_releases` table | todo | — | P3-001 | |
| P3-003 | Alembic 009: `revenue_events` table | todo | — | P3-002 | |
| P3-004 | Alembic 010: `social_posts` table | todo | — | P3-001, P3-002 | |
| P3-005 | Alembic 011: `generation_logs` table | todo | — | P3-002 | |

### P3.B — Song generation pipeline (Suno)

| ID | Title | Status | Assigned | Depends on | Notes |
|---|---|---|---|---|---|
| P3-010 | Sign up for EvoLink or CometAPI Suno wrapper (manual, ~$0.11–0.14/song) | todo | — | — | PRD §13 recommends EvoLink |
| P3-011 | Build `services/song_generation/suno_client.py` — auth, generate, poll, download | todo | — | P3-010 | |
| P3-012 | Build `services/song_generation/quality_check.py` — tempo ±10%, energy ±0.15, duration 90–300s, no >3s silence | todo | — | P3-011 | |
| P3-013 | Build orchestrator: blueprint + artist DNA → prompt → Suno → QA → persist to `ai_artist_releases` + `generation_logs` | todo | — | P3-002, P3-005, P3-012 | |

### P3.C — Artist creation pipeline

| ID | Title | Status | Assigned | Depends on | Notes |
|---|---|---|---|---|---|
| P3-020 | Build `services/artist_creation/persona_generator.py` (Groq-driven full persona from genre opportunity) | todo | — | P3-001, P2-070 | LLM call must be logged |
| P3-021 | Build `services/artist_creation/portrait_6angle.py` (Stable Diffusion + IP-Adapter) | todo | — | — | |
| P3-022 | Build `services/artist_creation/artist_decision.py` — assign-to-existing vs create-new (PRD §15.2) | todo | — | P3-001 | |
| P3-023 | Manual platform-account creation runbook (TikTok/Instagram/YouTube) | todo | — | P3-020 | Documented per-artist; cannot be automated |

### P3.D — Distribution

| ID | Title | Status | Assigned | Depends on | Notes |
|---|---|---|---|---|---|
| P3-030 | Decision: Revelator vs LabelGrid — write a 1-pager comparing pricing, API quality, royalty integration | todo | — | — | Architectural decision |
| P3-031 | Build `services/distribution/client.py` for the chosen provider | todo | — | P3-030 | |
| P3-032 | DALL-E cover-art generation (3000x3000, mood + brand colors) | todo | — | P3-002 | |
| P3-033 | Metadata assembly + ISRC/UPC handling | todo | — | P3-031 | |
| P3-034 | Wire to orchestrator: post-QA pass → distribute → record `distributed_at`, `isrc`, `upc` | todo | — | P3-013, P3-031, P3-032, P3-033 | |

### P3.E — Marketing & Social

| ID | Title | Status | Assigned | Depends on | Notes |
|---|---|---|---|---|---|
| P3-040 | TikTok hook extraction: 15-sec clip from chorus (using Spotify Audio Analysis sections) | todo | — | P1-005 | |
| P3-041 | TikTok Content Posting API integration (developer-access required) | todo | — | — | Apply for access — takes weeks |
| P3-042 | Instagram Graph API integration | todo | — | — | |
| P3-043 | YouTube Data API v3 integration | todo | — | — | |
| P3-044 | Performance monitoring + boost logic (likes acceleration → 2x baseline → boost) | todo | — | P3-041 | |
| P3-045 | Social content calendar runner (per PRD §18 weekly schedule) | todo | — | P3-041, P3-042, P3-043 | |

### P3.F — Rights & Royalties

| ID | Title | Status | Assigned | Depends on | Notes |
|---|---|---|---|---|---|
| P3-050 | Establish SoundPulse Records LLC + obtain IPI numbers (manual, legal) | todo | — | — | |
| P3-051 | TuneRegistry Business account + CSV export pipeline from `ai_artist_releases` | todo | — | P3-002, P3-050 | |
| P3-052 | SoundExchange direct integration (request API access) | todo | — | P3-050 | |
| P3-053 | MLC bulk upload pipeline (300-row limit per upload) | todo | — | P3-050 | |
| P3-054 | YouTube Content ID claim setup | todo | — | P3-043 | |

### P3.G — Revenue ingestion

| ID | Title | Status | Assigned | Depends on | Notes |
|---|---|---|---|---|---|
| P3-060 | Revelator revenue report puller → `revenue_events` | todo | — | P3-003, P3-031 | |
| P3-061 | SoundExchange report puller | todo | — | P3-003, P3-052 | |
| P3-062 | ASCAP/BMI quarterly statement parser (TuneRegistry-mediated) | todo | — | P3-003, P3-051 | |
| P3-063 | Reconciliation logic across sources (dedupe, currency normalization) | todo | — | P3-060, P3-061, P3-062 | |
| P3-064 | Reinvestment allocator (PRD §9.3 — generation 40% / marketing 30% / infra 20% / reserve 10%) | todo | — | P3-063 | |

---

## O — Ops & Quality (cross-cutting)

| ID | Title | Status | Assigned | Depends on | Notes |
|---|---|---|---|---|---|
| O-001 | Populate `planning/lessons.md` with at least L001 (Flint reference in CLAUDE.md was wrong repo — caught 2026-04-11) and a header entry per CLAUDE.md format | todo | — | — | Start the lessons log proper |
| O-002 | Decision write-up: APScheduler vs Celery beat — pick one. Currently both exist and it's confusing | todo | — | — | Affects P1-031, every scheduled task |
| O-003 | Add CI: GitHub Actions workflow that runs `pytest` + `npm run build` on every push to `main` | todo | — | — | Currently no CI, no quality gates |
| O-004 | Increase backend test coverage to >50% for `api/services/` (currently ~112 lines total) | todo | — | — | Bias toward integration tests via WebApplicationFactory equivalent (FastAPI TestClient) |
| O-005 | Add frontend tests via Vitest + RTL — start with `AssistantPanel`, `TrendingTable`, `useSoundPulse` hooks | todo | — | — | |
| O-006 | Audit `frontend/src/components/` for dead components | todo | — | — | |
| O-007 | Move `audio_features` and `signals_json` JSON columns to JSONB in a new migration to enable indexing | todo | — | — | Significant perf win for genre filters |
| O-008 | Add scraper failure alerting (persistent error log table or webhook) | todo | — | P1-031 | Without this, scrapers fail silently |

---

---

## AUDIT — 2026-04-11 deep code audit

> Generated by a subagent code audit on 2026-04-11. **9 BROKEN, 8 STUB, 17 BUG, 24 IMPROVEMENT, 5 SECURITY, 3 DATABASE.** Items marked **(verify)** in notes have a non-zero chance of being false positives or already-fixed; confirm before acting.
>
> Where an audit finding gives a more specific cause for an existing P1/P2 task, the existing task's Notes column has been updated with a back-reference (e.g. AUD-011 → P1-004).

### AUD.A — BROKEN (blocks features)

| ID | Title | File:line | Status | Notes |
|---|---|---|---|---|
| AUD-001 | Genre classifier exception swallowing — add logging before the silent `except Exception: pass` | api/routers/trending.py:88 | done | Now logs warning with entity id, type, name, classifier exception, and signal keys. Will surface why ~95% of tracks fail classification. |
| AUD-002 | Defer sync genre classification out of `POST /trending` to a background task or end-of-scraper batch | api/routers/trending.py:82-87 | done | Solved by the bulk endpoint + classification sweep (P1-050 + P1-060). Per-record path remains for the legacy 4h scraper but is no longer the bottleneck. |
| AUD-003 | Fix file-handle leak in backfill subprocess; use `subprocess.DEVNULL` or context-managed log file. Also fix relative `scripts/backfill_deep.py` path (use absolute, like `train_model.py:114`) | api/routers/admin.py:951 | done | Absolute script_path; explicit `log_file.close()` after `Popen` (child dup'd FD); `close_fds=True`; cwd set. |
| AUD-004 | Remove duplicate `"spotify_audio"` key in `DEFAULT_CONFIGS` — line 183 is silently overwritten by line 185 | scrapers/scheduler.py:183, 185 | done | Fixed in `scrapers/scheduler.py` — single definition with comment. Both copies were identical so behavior is unchanged. |
| AUD-011 | Fix `spotify_audio` scraper API schema mismatch — `_fetch_tracks_needing_enrichment()` calls `/api/v1/trending` expecting `entity_identifier`+`signals` keys; the endpoint returns `entity`+`scores` | scrapers/spotify_audio.py:119-139 | done | Built new purpose-built admin endpoint `GET /api/v1/admin/tracks/needing-audio-features` that queries the DB directly for `WHERE spotify_id IS NOT NULL AND audio_features IS NULL` with limit/offset. Rewrote `_fetch_tracks_needing_enrichment()` to consume it. Commit 190e953. |
| AUD-012 | Implement exponential backoff in `_rate_limited_request()` — currently retries immediately on 429 | scrapers/base.py:~57 | todo | (verify) MAX_RETRIES=5 BASE_DELAY=1.0 are defined but the loop body needs to actually `await asyncio.sleep(BASE_DELAY * 2**attempt)`. Read the file to confirm. |
| AUD-017 | Replace `subprocess.run` train invocation with direct call to `ml.train.train()`; capture full stderr to file on failure | scrapers/tasks.py:116-120 | todo | Cross-ref P2-001. The `cwd=project_root` is redundant because script_path is already absolute. |
| AUD-019 | Implement (or remove) `_build_sequence()` for LSTM in the ensemble — currently undefined, so LSTM predictions never run | ml/predictor.py:95, ml/ensemble.py | todo | If LSTM isn't ready for Phase 2, remove it from the active ensemble path so the rule-based fallback isn't masked by silent LSTM None-returns. |
| AUD-021 | Implement Blueprint endpoints `/blueprint/opportunities` and `/blueprint/generate` — SongLab UI consumes hooks for these but the router is stubbed | api/routers/blueprint.py | todo | (verify — recent commits suggest this may be partially built) Cross-ref P2-050..P2-054. |

### AUD.B — STUB (incomplete)

| ID | Title | File:line | Status | Notes |
|---|---|---|---|---|
| AUD-022 | Add error display to ModelValidation page — `runBacktest.isError` is currently silent | frontend/src/pages/ModelValidation.jsx:142-150 | todo | Cross-ref P2-034. Show `runBacktest.error?.message` near line 150. |
| AUD-031 | Create `tests/test_api/test_admin.py` — admin router has zero tests, handles scraper config / model train / backfill | tests/test_api/ | todo | Cross-ref O-004. |
| AUD-032 | Create `tests/test_api/test_predictions.py` — predictions endpoint untested incl. rule-based fallback | tests/test_api/ | todo | |
| AUD-033 | Create `tests/test_api/test_search.py`, `test_assistant.py`, `test_backtesting.py` — 6/9 routers untested | tests/test_api/ | todo | |
| AUD-034 | Create scraper tests for chartmetric, shazam, spotify_audio, apple_music, musicbrainz, kworb, radio (only spotify is tested) | tests/test_scrapers/ | todo | |
| AUD-044 | Decide and document: predictions are persisted vs compute-on-demand. Currently `generate_predictions` Celery task does NOT INSERT into the table; the GET endpoint returns rule-based fallback | scrapers/tasks.py:153, api/routers/predictions.py | todo | Cross-ref P2-020..P2-023. **Architectural decision** — write a 1-pager. |
| AUD-045 | Verify `run_backtest()` Celery task commits atomically; expose `GET /backtesting/results` if missing | api/services/backtest_service.py:84, api/routers/backtesting.py | todo | (verify — PRD says the route exists; audit may be wrong) Cross-ref P2-030..P2-033. |
| AUD-016 | Decide: enable `genius_lyrics` properly (with tests + integration) or remove the scraper + config row | scrapers/genius_lyrics.py, scrapers/scheduler.py:184 | todo | Cross-ref P2-040..P2-042. |

### AUD.C — BUG (works but wrong)

| ID | Title | File:line | Status | Notes |
|---|---|---|---|---|
| AUD-005 | Fix neighbor-inference query: it compares track UUIDs against artist UUIDs in the artists table. Set `entity_id = artist.id` consistently before line 507 | api/services/genre_classifier.py:508-514 | done | **Correction:** the audit's specific claim was already fixed at lines 502-507. But real adjacent bugs existed: silent `logger.debug` swallowing → promoted to warning; `entity.artist` MissingGreenlet risk → explicit try/except with FK fallback load; fallback to track UUID when artist can't be resolved → now returns {} early. Shipped in commit 190e953. |
| AUD-006 | Add logging in `_signal_artist_inheritance` exception handler before returning `{}` | api/services/genre_classifier.py:402-404 | done | Promoted from `logger.debug` (invisible) to `logger.warning` with track id, artist id, exception. |
| AUD-007 | Per-genre prediction targets — currently 4 hardcoded US targets only; `?genre=...` filter is ignored | api/services/prediction_service.py:46-67 | todo | Either extend `PREDICTION_TARGETS` or filter results in the route. |
| AUD-008 | Backtest service transaction-boundary check: ensure each period's results are an atomic unit | api/services/backtest_service.py:84-92 | todo | Currently rollback at line 92 loses all progress for the period. |
| AUD-013 | Replace `asyncio.new_event_loop()` with `asyncio.run()` in Celery task wrappers | scrapers/tasks.py:92-94, 143-144 | todo | Pending futures get abandoned on close. Idiomatic fix. |
| AUD-014 | Fallback chain should accumulate exceptions from all members, not just re-raise the last one | scrapers/fallback.py | todo | (verify file path) Improves debuggability when all sources fail. |
| AUD-018 | Surface cold-start metadata in prediction response: `{is_cold_start: true, confidence_reason: "only N days of history"}` | ml/predictor.py, api/routers/predictions.py | todo | The `0.5` cap is currently invisible to API consumers. |
| AUD-023 | Pass current `baseUrl` to `generateCurl()` instead of re-reading via `getBaseUrl()` — stale cURL after settings change | frontend/src/hooks/useSoundPulse.js:9-13, 59 | todo | |
| AUD-024 | RequestBuilder should distinguish path/query/body params for POST endpoints; validate body schema | frontend/src/pages/ApiPlayground.jsx:82-83 | todo | |
| AUD-027 | Add FK or CHECK constraint on `trending_snapshots.entity_type` and entity_id (polymorphic) | api/models/trending_snapshot.py:16 | todo | Currently orphans possible. Polymorphic FK is awkward — at minimum a CHECK constraint that entity_type ∈ {track, artist}. |
| AUD-028 | Either separate `predictions.entity_id` into `track_or_artist_id (UUID)` + `genre_id (String)`, or document the polymorphism explicitly | api/models/prediction.py:16 | todo | (verify) String(200) accommodates both UUIDs and dot-notation genre IDs. Mixing types is error-prone. |
| AUD-029 | Add indexes on frequently-filtered columns: `trending_snapshots.entity_type`, `predictions.entity_type`, `backtest_results.evaluation_date` (standalone) | api/models/*.py | todo | Migration 006 candidate. |
| AUD-041 | Filter API keys from request logs (`if "x-api-key" in headers: headers["x-api-key"] = "***"`) | api/middleware/auth.py or dependencies.py | todo | (verify path) |
| AUD-043 | Audit DB session lifecycle in `POST /trending` — same session passed to resolve_track / classifier / recalculate. Use savepoints or fresh sessions | api/routers/trending.py:27-104 | todo | After classifier rollback, refetched entity may be stale by the time `recalculate_composite_for_entity` runs. |

### AUD.D — IMPROVEMENT (quality / refactor)

| ID | Title | File:line | Status | Notes |
|---|---|---|---|---|
| AUD-009 | Remove unused imports `and_`, `case` | api/routers/trending.py:6 | done | Removed `and_`, `case`, and `text` (also unused) from the SQLAlchemy import line. |
| AUD-010 | Validate `audio_profile` shape before indexing — check `range_key in audio_profile and len(audio_profile[range_key]) == 2` | api/services/genre_classifier.py:355-356, 365 | todo | |
| AUD-015 | Validate scraper credentials non-empty at scheduler level before instantiation | scrapers/scheduler.py:60-129 | todo | Fail fast instead of mid-`authenticate()`. |
| AUD-020 | Validate LightGBM hyperparams: assert `max_depth > 0` if `num_leaves` is high | config/model.json:33-40, ml/ensemble.py | todo | Prevent memory blow-up at training time. |
| AUD-025 | Wrap `AssistantPanel` in an ErrorBoundary | frontend/src/components/AssistantPanel.jsx | todo | Currently a Groq exception crashes the entire app. |
| AUD-026 | TrendingCard genres always empty until P1.B fix lands — cosmetic note, no separate task | frontend/src/components/TrendingCard.jsx | done | Tracked under P1-014 (backfill). |
| AUD-030 | Add GIN indexes on `audio_features` and `signals_json` JSON columns for filtering by JSON keys; consider migrating to JSONB | api/models/track.py:27-28, api/models/trending_snapshot.py | todo | Cross-ref O-007. |
| AUD-035 | Add error-path tests to `tests/test_api/test_trending.py` (duplicate snapshot 409, invalid platform, missing identifiers, classifier failure) | tests/test_api/test_trending.py | todo | |
| AUD-038 | Cache model config — currently re-parsed from `config/model.json` on every admin request | api/routers/admin.py:967-972 | todo | Load once at startup, invalidate on PUT. |
| AUD-039 | `scripts/start.py` should `check=True` on migrations + seed_genres so failures abort startup | scripts/start.py:8, 11 | done | Both subprocess.run() calls now `check=True` and exit with the failed return code so Railway restarts the container instead of running on broken state. |
| AUD-042 | Apply rate-limit middleware to public GET endpoints (trending, search, predictions) — currently middleware exists but isn't applied | api/middleware/rate_limiter.py, api/main.py | todo | (verify which routes are excluded) |
| AUD-046 | Move hardcoded thresholds (e.g. `velocity / 10.0` clamp at `prediction_service.py:119-162`, `test_split=0.2` at `ml/train.py:103`) to `config/model.json` | api/services/prediction_service.py, ml/train.py | todo | |
| AUD-047 | Replace plain `@dataclass` `GenreCandidate` / `ClassificationResult` with Pydantic models or add `__post_init__` validation | api/services/genre_classifier.py:113-125 | todo | Validate `confidence ∈ [0,1]`, `depth ≥ 0`. |

### AUD.E — SECURITY

| ID | Title | File:line | Status | Notes |
|---|---|---|---|---|
| AUD-036 | Require `API_ADMIN_KEY` env var; raise `ValueError` if missing or equal to the documented default `sp_admin_0000...dead` | api/config.py:9 | done | `Settings.assert_secure_in_production()` raises `InsecureDefaultError` at startup if env=production AND admin_key is unset/default. Called from `get_settings()`. Local dev unaffected. |
| AUD-037 | Require `API_SECRET_KEY` env var; reject the literal default `"change-me-in-production"` | api/config.py:10 | done | Same `assert_secure_in_production()` checks both keys together and reports all problems in one error. |
| AUD-040 | Verify CORS middleware is configured with explicit allow-list (not `*`). Recent commit `fce5a34` added CORS — confirm scope | api/main.py | todo | (verify — likely already done; audit may be stale) |

