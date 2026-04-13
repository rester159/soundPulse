# SoundPulse Task Decomposition — PRD v3 Execution Checklist

**North star for every session.** Read this at session start. Check off tasks as they complete. When a task's scope expands, split it rather than growing it.

## Legend

- `[x]` done + verified in production
- `[~]` in progress
- `[ ]` pending
- `[!]` blocked (dependency or external factor)
- **Depends:** prior task IDs that must be `[x]` before this can start
- **Acceptance:** how we know it's really done

Every task references the PRD section(s) it implements. When you finish a task, also mark the corresponding row in PRD §59 (“What's already built”) if that column exists.

---

## Phase 0 — Already shipped ✅

These are complete as of 2026-04-12. Listed here so the "what's built" story reads cleanly in one place.

### Intelligence & Data (Part II)
- [x] **T-001** [§7] Data collection layer — scraper framework + 7 active sources (Chartmetric, Spotify, Shazam, Radio, Kworb, Tunebat via BlackTip)
- [x] **T-002** [§8] Song DNA feature set — audio_features column + Tunebat enrichment
- [x] **T-003** [§9] Genre intelligence — 959-genre taxonomy + classifier
- [x] **T-004** [§10 L1] Breakout detection sweep + breakout_events table (migration 007)
- [x] **T-005** [§10 L2] Feature delta analysis + genre_feature_deltas (migration 009 part)
- [x] **T-006** [§10 L3] Gap finder (K-means clustering)
- [x] **T-007** [§10 L4] Genius lyrics pipeline + track_lyrics (migration 008)
- [x] **T-008** [§10 L5] Lyrical analysis LLM (migration 009)
- [x] **T-009** [§10] Opportunity Score v2
- [x] **T-010** [§11] Opportunity quantification ($ projections + 6-factor confidence) + breakout_quantifications
- [x] **T-011** [§12] Smart prompt v2 — LLM synthesis of all layers
- [x] **T-012** [§10] Breakout resolution math fix — `unresolvable` label, detection-peak-relative thresholds
- [x] **T-013** [§10] Historical backfill walker (78-week window, limited by ingestion depth)
- [x] **T-014** Scheduler cadences cranked to Chartmetric safe limits
- [x] **T-015** llm_calls logging mandate (migration 006)

### Workflow, Entities, and Tables (Part III §17)
- [x] **T-020** [§17] ceo_profile (migration 010)
- [x] **T-021** [§17] agent_registry + tools_registry + agent_tool_grants (migration 011)
- [x] **T-022** [§17] music_generation_calls (migration 012)
- [x] **T-023** [§17] song_blueprints + ai_artists + ceo_decisions + genre_config (migration 013)

### Artist Spine (Part IV §22–23, partial)
- [x] **T-030** [§22] Assignment engine with 4 live dimensions (genre_match, voice_fit, lyrical_fit, audience_fit) + 6 labeled stubs + 15 unit tests
- [x] **T-031** [§22] POST /admin/blueprints, POST /admin/artists, POST /admin/blueprints/{id}/assign
- [x] **T-032** [§23] CEO decision gate backend (approve / reject with side-effect on blueprint status)
- [x] **T-033** [§23] CEO gate UI — Pending Decisions panel in Settings with scoring breakdown + approve/reject inline

### Song Production (Part V §24, partial)
- [x] **T-040** [§24] Music provider abstraction (`api/services/music_providers/`) with adapter interface
- [x] **T-041** [§24] MusicGen via Replicate — **live** at $0.064/run
- [x] **T-042** [§24] Suno via EvoLink/MusicAPI — scaffolded, key-gated
- [x] **T-043** [§24] Udio adapter stubbed (licensing transition)
- [x] **T-044** [§24] Generation persistence — music_generation_calls + list endpoint + Recent Generations strip in SongLab

### Platform & Infra (Part X)
- [x] **T-050** [§48] AI Assistant chat (Groq llama-3.3-70b)
- [x] **T-051** [§49] CEO Profile settings UI + table
- [x] **T-052** [§50] Tools & Agents registry UI with by-tool/by-agent pivot + grant management
- [x] **T-053** [§51] SongLab UI with blueprint cards, provider picker, generate button, Recent Generations strip
- [x] **T-054** Data Pipeline diagnostic page (live scraper status)
- [x] **T-055** DB Stats page with hydration dashboard
- [x] **T-056** Version badge in layout (deploy identity)
- [x] **T-057** PRD v3 merged + consistency audit pass (2969 lines, 16 items enumerated)
- [x] **T-058** Layout.jsx Settings icon crash fix

---

## Phase 1 — MVP-1 (Core Production Pipeline)

**Goal:** a blueprint with an approved artist actually becomes a released song on DSPs with rights registered. Targeted sequencing below.

### P1.A — Core entity DDL (PRD §17)

These are tables referenced by §24–47 logic that still need schema + models.

- [x] **T-100** [§17] `songs_master` migration (~80 fields per PRD DDL) + SQLAlchemy model + admin endpoints
      **Acceptance:** `POST /admin/songs` inserts a row, `GET /admin/songs/{id}` returns it, every field from PRD DDL present, unique constraint on ISRC. ✓ shipped 2026-04-12 commit cc82211
- [ ] **T-101** [§17] `releases` migration + model
      **Depends:** T-100
- [ ] **T-102** [§17] `release_track_record` migration + model
      **Depends:** T-100, T-101
- [ ] **T-103** [§17] `audio_assets` migration + model (provider, format, sample_rate, bitrate, duration, storage_url, checksum, is_master_candidate)
      **Depends:** T-100
- [ ] **T-104** [§17] `song_qa_reports` migration + model
      **Depends:** T-100, T-103
- [ ] **T-105** [§17] `reference_artists` migration + model
- [ ] **T-106** [§17] `artist_visual_assets` migration + model
- [ ] **T-107** [§17] `artist_voice_state` migration + model
- [ ] **T-108** [§17] `song_submissions` migration + model
      **Depends:** T-100, T-101
- [ ] **T-109** [§17] `royalty_registrations` migration + model (6 lane values per §37–41)
      **Depends:** T-100
- [ ] **T-110** [§17] `marketing_campaigns` migration + model
      **Depends:** T-100
- [ ] **T-111** [§17] `social_accounts` + `social_posts` migration + models
- [ ] **T-112** [§17] `revenue_events` migration + model

### P1.B — Full artist creation pipeline (PRD §18–21)

- [ ] **T-120** [§19] Reference artist research service — BlackTip scrape of top N Chartmetric artists in target genre, sorted by momentum (90-day window). Writes `reference_artists` rows.
      **Depends:** T-105
- [ ] **T-121** [§19] Reference artist enrichment — factual fields from Chartmetric + Wikipedia/BlackTip scrape for bio
      **Depends:** T-120
- [ ] **T-122** [§19] Visual reference enrichment — 10–20 public images → Claude Vision → `visual_dna` shape with confidence_report
      **Depends:** T-120
- [ ] **T-123** [§19] Voice reference enrichment — Essentia/Librosa analysis of 3–5 top tracks → `voice_dna` shape (timbre, range, breathiness, vocal range, speech-vs-sung ratio, phrasing density)
      **Depends:** T-120
- [ ] **T-124** [§19] Lyrical reference enrichment — LLM theme extraction from reference artist's top 10 lyrics
      **Depends:** T-120
- [ ] **T-125** [§19] Social voice enrichment — BlackTip scrape of recent posts from official handles → `social_dna`
      **Depends:** T-120
- [ ] **T-126** [§19] Copy-risk validator — fail if >0.75 similarity to any reference artist on key features
      **Depends:** T-121, T-122, T-123
- [ ] **T-127** [§18] Persona blender — LLM combines reference artists into A/B/C candidate personas, with deterministic rule clamps
      **Depends:** T-121, T-126
- [ ] **T-128** [§18] Artist finalization service — persists `ai_artists` row after CEO approval
      **Depends:** T-127, T-032
- [ ] **T-129** [§20] Visual reference sheet generator — 8-view composite via the `openai_cli_proxy` tool (preferred path, broker for DALL-E 3 / gpt-image-1), with locked seed/embedding across views. Fallback to Flux via fal.ai or Stable Diffusion + IP-Adapter if OpenAI path rejects face-locking.
      **Depends:** T-106, T-128
- [ ] **T-130** [§20] Facial consistency QA via embedding similarity — kill and retry if any view drifts
      **Depends:** T-129
- [ ] **T-131** [§20] Canonical `visual_dna.reference_sheet_asset_id` set on artist row after pass
      **Depends:** T-129, T-130
- [ ] **T-132** [§21] `artist_voice_state` bootstrap — initialize with null seed on artist creation
      **Depends:** T-107, T-128
- [ ] **T-133** [§21] `build_voice_state_reference_block(artist_id)` helper returning None (song_count==0) or Jinja-rendered reference block (song_count≥1)
      **Depends:** T-107

### P1.C — Assignment engine maturation (PRD §22)

- [ ] **T-140** [§22] Wire `release_cadence_fit` — query `ai_artists.last_released_at`, penalize <14 days since last release
      **Depends:** T-023 (already done)
- [ ] **T-141** [§22] Wire `momentum_fit` — aggregate recent stream delta from `revenue_events`, reward rising curves
      **Depends:** T-112
- [ ] **T-142** [§22] Wire `visual_brand_fit` — cosine similarity between blueprint visual descriptors and artist `visual_dna`
      **Depends:** T-106, T-131
- [ ] **T-143** [§22] Wire `cannibalization_risk` — count artist's tracks in same sub-genre within last 60 days
- [ ] **T-144** [§22] Wire `brand_stretch_risk` — distance between blueprint theme/tone and artist `persona_dna`
- [ ] **T-145** [§22] Wire `strategic_diversification` — portfolio-level heuristic based on current roster genre coverage

### P1.D — CEO gate delivery (PRD §23, §49)

- [ ] **T-150** [§23] Telegram bot delivery — send formatted message with inline approve/reject buttons
      **Depends:** T-032
- [ ] **T-151** [§23] Email delivery via SMTP (SendGrid) with signed action links
      **Depends:** T-032
- [ ] **T-152** [§23] Decision timeout worker (default 24h → `timed_out` status, escalate)
      **Depends:** T-032
- [ ] **T-153** [§23] Re-engagement on stale pending (nudge CEO every N hours before timeout)
      **Depends:** T-150

### P1.E — Song production pipeline (PRD §24–27)

- [x] **T-160** [§24] Blueprint → generation orchestrator — reads `blueprint.assigned_artist_id`, fetches artist + optional `artist_voice_state`, builds full prompt (`voice_dna_summary` + optional `voice_state_reference_block` + `blueprint.smart_prompt_text`), calls music provider via registry, persists `songs_master` row in `draft` status bound to blueprint+artist, persists `music_generation_calls` linked via new `song_id` FK. Poll handler flips `songs_master` to `qa_pending` + creates `audio_assets` row on terminal success. **Does NOT create a `releases` row** — that binding happens in T-183 per PRD §24 explicit decision.
      ✓ shipped 2026-04-12 commit 78b1cfa
- [ ] **T-161** [§24] Regeneration retry policy — up to 3 QA-failed attempts, then escalate to CEO via T-150
      **Depends:** T-160, T-104, T-150
- [ ] **T-162** [§25] Audio QA service — Essentia/Librosa checks for tempo, key, energy, silence, clipping, loudness normalization, lyric intelligibility, vocal prominence
      **Depends:** T-104
- [ ] **T-163** [§25] Duplication risk check — cosine similarity vs catalog audio embeddings, reject >0.85
      **Depends:** T-162
- [ ] **T-164** [§25] Loudness auto-normalization — target −14 LUFS ±1 (no regen required)
      **Depends:** T-162
- [ ] **T-165** [§26] Lyric extraction from Suno response → `songs_master.lyric_text` + `track_lyrics` cross-reference
      **Depends:** T-100
- [ ] **T-166** [§26] Genius cross-reference on post-release index (T+7-14d) via existing `genius_lyrics` scraper
- [ ] **T-167** [§27] Metadata strategy service — project `songs_master` into lane-specific payloads (DSP delivery, PRO, sync, social)
      **Depends:** T-100
- [ ] **T-168** [§24] Provider selection heuristic — MusicGen for instrumental, Suno for lyric-driven (when key lands)

### P1.F — Music provider unblocks

- [!] **T-170** Suno vendor signup — pick one of PiAPI / apiframe.ai / MusicAPI.ai and provision a key
      **Blocked by:** user decision + vendor auth
- [ ] **T-171** Rewrite `suno_evolink.py` adapter shape to match the chosen vendor's REST contract
      **Depends:** T-170
- [ ] **T-172** [§21] Wire `reference_audio_url` flow through Suno for two-phase voice rule
      **Depends:** T-171, T-133
- [ ] **T-173** Generation cost ceiling guard — hard stop if monthly MusicGen+Suno spend >$X, escalate via CEO gate

### P1.G — Distribution (PRD §28–30)

- [ ] **T-180** [§28] Submission classes registry — seed `submission_types` table with every lane + dependencies
- [ ] **T-181** [§29] Submission ordering DAG — enforce "distribution → identifiers → rights → marketing"
- [ ] **T-182** [§30] LabelGrid distribution connector — OAuth setup, metadata push, submission polling
      **Blocked by:** LabelGrid account provisioning
- [x] **T-183** [§30] Release assembly service — bundle song(s) into a release row + release_track_record. **This is the sole place `releases` rows get created** per the §24 deliberate separation — generation never does it. Flips `songs_master.status` from `qa_passed` to `assigned_to_release` and populates `release_id`. Endpoints: POST/GET /admin/releases, GET /admin/releases/{id} detail, POST/DELETE /admin/releases/{id}/tracks, plus POST /admin/songs/{id}/mark-qa-passed manual bypass until T-162 lands.
      ✓ shipped 2026-04-12 commit fba0772
- [ ] **T-184** [§29] ISRC/UPC ingestion — on distributor ACK, pull identifiers and update `songs_master.isrc` + `releases.upc`
      **Depends:** T-182, T-183
- [ ] **T-185** [§29] Submission status poll worker — 30-min interval for non-terminal submissions
      **Depends:** T-108, T-182

### P1.H — Rights (Fonzworth/ASCAP first, per MVP-1 priority)

- [ ] **T-190** [§31] Fonzworth ASCAP integration — HTTP client for submission service at `fonzworth` project URL
      **Blocked by:** Fonzworth service URL + API key from user
- [ ] **T-191** [§31] ASCAP payload builder from `songs_master` — title, writers, publishers, ISRC, duration
      **Depends:** T-100, T-190
- [ ] **T-192** [§37] PRO lane scheduler — submit to ASCAP after distributor accepts + identifiers land
      **Depends:** T-184, T-191
- [ ] **T-193** [§37] ISWC ingestion from ASCAP response → `royalty_registrations.external_id` + `songs_master.iswc`
      **Depends:** T-192, T-109
- [ ] **T-194** [§31] Fonzworth retry + error recovery (manual review escalation if >3 failures)
      **Depends:** T-190

### P1.I — Song spine verification

- [ ] **T-195** End-to-end integration test: breakout → blueprint → assignment → CEO approve → artist → song generation → QA → audio_assets → release → LabelGrid submit → ASCAP register → songs_master final state
      **Depends:** T-100 through T-193
      **Acceptance:** one test song progresses through every status transition in a single test run against a staging DB

---

## Phase 2 — MVP-2 (Rights expansion + Marketing core)

### P2.A — Remaining rights lanes (PRD §32–36)

- [ ] **T-200** [§32] BMI portal automation — Fonzworth-pattern service (separate repo if needed)
      **Blocked by:** BMI publisher membership
- [ ] **T-201** [§33] MLC DDEX feed builder — mechanical lane XML payload
      **Blocked by:** MLC publisher membership
- [ ] **T-202** [§34] SoundExchange portal automation
- [ ] **T-203** [§35] YouTube Content ID workflow — asset upload + reference file registration
      **Blocked by:** YouTube CMS partnership
- [ ] **T-204** [§36] Sync marketplace submission (Lickd, Songtradr, etc.)
- [ ] **T-205** [§39] Neighboring rights lane scheduler
- [ ] **T-206** [§40] UGC monetization lane

### P2.B — Marketing phase engine (PRD §42, §44)

- [ ] **T-210** [§42] Marketing phase state machine — M0 → M5 lifecycle with transition rules
      **Depends:** T-110
- [ ] **T-211** [§42] Phase gate check cron — evaluate metrics, advance/kill/extend
- [ ] **T-212** [§44] Metrics collector per phase — streams, saves, follows, UGC uses, press hits
- [ ] **T-213** [§45] 0→3K streams playbook — automated task queue per phase

### P2.C — Marketing agents (PRD §43, 14 agents minus ones already built)

- [ ] **T-220** [§43.A] Artist Identity Agent — persona drift detection, voice evolution proposals
- [ ] **T-221** [§43.B] Content Strategy Agent — content calendar generator from `social_dna` template
- [ ] **T-222** [§43.C] Video Generation Agent — Veo integration for TikTok/Reels
- [ ] **T-223** [§43.D] Copy/Caption Agent — LLM copy per post with platform-specific constraints
- [ ] **T-224** [§43.E] Social Posting Agent — scheduled publish across connected `social_accounts`
- [ ] **T-225** [§43.F] Community Agent — comment reply automation (first 50 per post per `social_dna.engagement_style`)
- [ ] **T-226** [§43.G] Playlist Outreach Agent — SubmitHub / Playlist Push / Groover integration
- [ ] **T-227** [§43.H] Micro-Influencer Seeding Agent — outreach tracker
- [ ] **T-228** [§43.I] UGC Trigger Agent — TikTok hashtag/sound monitoring
- [ ] **T-229** [§43.K] Analytics Agent — metric aggregation + feedback loop into blueprint generation
- [ ] **T-230** [§43.L] Editorial/PR Agent — press release generation + outreach
- [ ] **T-231** [§43.N] Submissions Agent — distribution/rights orchestration (currently scaffolded in §43 catalog only)

### P2.D — Social integrations (platform APIs)

- [ ] **T-240** TikTok Content Posting API — draft mode first (audit-gated for auto-publish)
- [ ] **T-241** Instagram Graph API publishing (needs `instagram_content_publish` scope)
- [ ] **T-242** YouTube Data API upload
- [ ] **T-243** X (Twitter) API v2 posting
- [ ] **T-244** Facebook Graph API posting

### P2.E — Revenue & reconciliation (PRD §46–47)

- [ ] **T-250** [§46] Revenue event ingestion from LabelGrid / distributor reports → `revenue_events`
- [ ] **T-251** [§46] Per-platform per-stream rate table + territory breakdown
- [ ] **T-252** [§47] Reconciliation cron — match expected vs actual royalty receipts, flag discrepancies
- [ ] **T-253** Revenue dashboard page in UI

---

## Phase 3 — MVP-3 (Scale + Optimization)

- [ ] **T-300** [§43.J] Paid Growth Agent — Meta Ads integration, budget management, creative tests
- [ ] **T-301** [§43.L] PR distribution via press release services (PRWire, PressKitHero, etc.)
- [ ] **T-302** Cross-catalog compounding logic — re-use proven sonic/lyrical patterns across future blueprints
- [!] **T-303** [§13] ML hit predictor training pipeline — XGBoost on resolved breakouts
      **Blocked by:** data depth (~45 consecutive days of dense forward-window coverage)
- [ ] **T-304** [§13] Feature engineering for ML training — audio features + lyrical themes + platform metadata
      **Depends:** T-303
- [ ] **T-305** [§13] Prediction endpoint + SongLab integration — show predicted_success_score per blueprint
      **Depends:** T-303
- [ ] **T-306** Model validation + backtesting pipeline for the hit predictor
- [ ] **T-307** [§14] Backtest UI already scaffolded — wire to ML model once trained

---

## Cross-Cutting / Infrastructure

- [ ] **T-400** Scheduler health checks — heartbeat + missed-run alerting
- [ ] **T-401** Alembic migration reconciliation — currently relying on manual DDL via Neon MCP, should move to proper `alembic upgrade head` in a deploy hook
- [ ] **T-402** Celery background worker for long-running tasks (enrichment pipelines, backfills)
- [ ] **T-403** Observability — structured logging + Prometheus metrics + Grafana dashboards
- [ ] **T-404** Cost tracking rollup — aggregate `llm_calls` + `music_generation_calls` + API usage into `costs_daily` view
- [ ] **T-405** Integration test suite for critical paths (every test from T-195 pattern)
- [ ] **T-406** CI pre-push hooks — run `pytest` + `vite build` before every push
- [ ] **T-407** Railway environment parity — match staging and production env vars + secrets
- [ ] **T-408** Database backup strategy — daily Neon dumps, verified restores
- [ ] **T-409** Rate-limit governors for all external APIs (Chartmetric already has one, extend to Replicate / Suno / etc.)
- [ ] **T-410** Secrets rotation procedure — document + automate for every entry in `tools_registry`

---

## Standing Blockers

| ID | Blocker | Owner | Status |
|---|---|---|---|
| B-01 | Suno vendor key | User | MusicAPI.ai auth broken; user picking alternative |
| B-02 | Replicate billing | User | ✓ Resolved (Apr 12) |
| B-03 | ML training data depth | System | Need late May 2026 before T-303 unblocks |
| B-04 | LabelGrid account | User | Required for T-182 |
| B-05 | ASCAP publisher membership | User | Required for T-192 ($50 one-time + IPI app) |
| B-06 | BMI publisher membership | User | Required for T-200 |
| B-07 | MLC publisher membership | User | Required for T-201 |
| B-08 | YouTube CMS partnership | User | Required for T-203 (likely never for indie) |
| B-09 | TikTok Content Posting audit | User | Required for T-240 auto-publish mode |
| B-10 | Genius API key | User | Required for lyrics pipeline to run (currently idle) |

---

## Execution rules (applied per session)

1. **Pick the smallest unblocked task closest to the current critical path.** Critical path for MVP-1 is: T-100 (songs_master) → T-160 (generation orchestrator) → T-162 (QA) → T-183 (release assembly) → T-182 (LabelGrid) → T-192 (ASCAP) → T-195 (E2E verification).
2. **Test-first per CLAUDE.md.** Write failing tests before implementation for any non-trivial service.
3. **Never mark a task `[x]` without verification.** Production deploy + smoke test + the stated acceptance criteria.
4. **When an external blocker hits, pivot to the next critical-path task that doesn't depend on it.** Don't wait.
5. **When a task grows beyond one session's scope, split it.** Append child tasks with letter suffixes (T-100a, T-100b).
6. **Every finished task appends a one-line entry to the end of this file** under a "Completion log" section so session-to-session memory is durable.

---

## Completion log

- 2026-04-12: T-001 through T-058 marked done (Phase 0 snapshot)
- 2026-04-12: T-100 `songs_master` migration 014, model, 4 admin endpoints (commit cc82211)
- 2026-04-12: T-100 6/6 smoke test verified + 409 polish on ISRC conflict (commit 0034434)
- 2026-04-12: T-101..T-112 entity batch — migration 015, 13 tables + songs_master deferred FKs (commit feb152e)
- 2026-04-12: Audio self-hosting fix — migration 016 music_generation_audio sidecar, streaming endpoint, Classical song marked expired (commit feb152e)
- 2026-04-12: PRD §24 clarified — release assembly is a SEPARATE step, not bundled into generation. Status lifecycle enumerated: draft → qa_pending → qa_passed → assigned_to_release → submitted → live.
- 2026-04-12: T-160 song generation orchestrator — POST /admin/blueprints/{id}/generate-song + generation_orchestrator service + music_generation_calls.song_id FK + poll handler _materialize_song_audio helper (commit 78b1cfa)
- 2026-04-12: T-183 release assembly — 5 endpoints for releases + tracks + manual qa-pass bypass (commit fba0772)
