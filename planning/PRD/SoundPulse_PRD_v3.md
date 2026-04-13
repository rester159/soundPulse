# SoundPulse — Master PRD v3
## A Fully Autonomous Virtual Record Label

**Version 3 — April 2026.** This is the canonical executable spec. It supersedes `SoundPulse_PRD_v2.md` and folds in `soundpulse_artist_release_marketing_spec.md`, `breakoutengine_prd.md`, `opportunity_quantification_spec.md`, and `fonzworth/ascap-submission-service.md`. Where the marketing spec conflicted with v2, the marketing spec wins. Where any source was vague, the resolution is documented inline.

*SoundPulse is a virtual record label that runs entirely on software. It analyzes what makes music succeed, generates songs that will succeed, distributes them to every platform, registers them with PROs, markets them, and collects the royalties. No humans in the loop — except the CEO, who is asked for approval on critical decisions.*

---

## Document conventions

- **BUILT** — already implemented and live in production
- **BUILT (partial)** — partially implemented; the gap is documented
- **TODO** — specified, ready to build, no external blocker
- **BLOCKED** — depends on external resource (paid plan, API partnership, manual signup, etc.)
- **NOTE** — clarification of vagueness from a source doc, with the resolution inline

Three rules govern all execution:

1. **Marketing spec wins on conflicts.** It is the most recent doc, the deepest treatment of post-blueprint operations, and the source-of-truth for the workflow downstream of opportunity detection.
2. **No stub features.** Every feature in this doc must be either BUILT, executable per a clear spec, or explicitly BLOCKED with a workaround.
3. **All vagueness is resolved.** Where the source docs conflicted or hand-waved, this doc commits to a specific implementation.

---

## Table of Contents

### Part I — Vision & Strategy
- §1 The Vision
- §2 The Complete Pipeline
- §3 Artist Portfolio Strategy
- §4 Phased Rollout (current state)
- §5 Success Metrics
- §6 Unit Economics

### Part II — Intelligence & Data (BUILT)
- §7 Data Collection Layer
- §8 Song DNA — feature set
- §9 Genre Intelligence
- §10 Breakout Analysis Engine (the discovery brain)
- §11 Opportunity Quantification ($ projections + confidence)
- §12 Smart Prompt v2 — blueprint generation
- §13 Prediction Models (current + ML hit predictor)
- §14 Model Validation & Backtesting

### Part III — Canonical Workflow & Entity Model
- §15 The 13-step orchestration sequence
- §16 Core entity relationships
- §17 Database schema (canonical)

### Part IV — Artist System
- §18 Artist creation pipeline
- §19 Artist reference research
- §20 Visual reference sheet (8-view)
- §21 Voice consistency (two-phase rule)
- §22 Assignment-vs-creation decision engine
- §23 CEO critical decision gate

### Part V — Song Production
- §24 Song generation under artist
- §25 Audio QA
- §26 Lyrics
- §27 Metadata strategy

### Part VI — Distribution & Submissions (Submissions Agent)
- §28 Submission classes
- §29 Submission ordering and dependencies
- §30 Distribution provider strategy (the API reality)
- §31 ASCAP service — Fonzworth
- §32 BMI portal automation
- §33 MLC DDEX
- §34 SoundExchange
- §35 YouTube Content ID
- §36 Sync marketplaces

### Part VII — Rights & Royalties
- §37 PRO lane
- §38 Mechanical lane
- §39 Neighboring rights lane
- §40 UGC monetization lane
- §41 Sync lane

### Part VIII — Marketing System
- §42 Marketing phases M0–M5
- §43 Marketing agent catalog (14 agents)
- §44 Metrics + triggers
- §45 0→3K streams playbook

### Part IX — Revenue & Analytics
- §46 Revenue tracking
- §47 Reconciliation

### Part X — Platform & Infrastructure
- §48 AI Assistant
- §49 CEO Profile + Action Agent
- §50 Settings UI (Tools & Agents registry)
- §51 SongLab UI
- §52 API Reference
- §53 Cron schedule
- §54 Deployment architecture
- §55 External API dependencies (validated reality)
- §56 Operating costs

### Part XI — Build Order & Rules
- §57 MVP build order
- §58 Non-negotiable implementation rules
- §59 What's already built
- §60 What's blocked

---

# Part I — Vision & Strategy

## §1. The Vision

SoundPulse is not a tool for record labels. It IS a record label — one that runs entirely on software.

The complete pipeline, end to end, with no human intervention except CEO approval on critical decisions:

1. **Analyze** — What sonic, lyrical, and release characteristics are driving success in any given micro-genre right now?
2. **Predict** — Which artist persona + song combination has the highest probability of success?
3. **Create** — Generate the artist (if new) and the song, with consistent identity across releases
4. **Distribute** — Upload the finished track to every streaming platform via distribution API
5. **Register** — Register the song with PROs for royalty collection
6. **Market** — Phase-gated marketing system that scales spend only on proven creatives
7. **Optimize** — Monitor performance, adjust future blueprints based on what's working
8. **Collect** — Royalties flow back automatically from streams, sync placements, and radio play
9. **Reinvest** — Revenue funds the next generation cycle

The output of SoundPulse is not a dashboard. It is revenue.

---

## §2. The Complete Pipeline

```
┌─────────────────────────────────────────────────────┐
│ 1. ANALYZE — What's working now?                    │
│    - Trending analysis per micro-genre              │
│    - Breakout detection vs genre baseline           │
│    - Feature delta analysis (statistical)           │
│    - Gap finder (K-means clustering)                │
│    - LLM lyrical theme analysis (when lyrics flow)  │
│    - $ + stream quantification with confidence      │
└────────────────────┬────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────┐
│ 2. PREDICT — What will succeed?                     │
│    - Smart Prompt v2 (data-driven blueprint)        │
│    - ML Hit Predictor (XGBoost on feature space)    │
│    - Combined opportunity score                     │
└────────────────────┬────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────┐
│ 3. ARTIST FIT EVALUATION — Existing or new?         │
│    - Score blueprint against current roster         │
│    - Reuse if reuse_score >= 0.68                   │
│    - Otherwise generate new artist persona          │
└────────────────────┬────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────┐
│ 4. CEO GATE — Approve assignment / new artist       │
└────────────────────┬────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────┐
│ 5. CREATE — Generate the music                      │
│    - Merge Artist DNA + Song DNA → prompt           │
│    - Suno via EvoLink → master audio                │
│    - Audio QA (tempo/key/loudness/dup risk)         │
│    - Visual: cover art + reference sheet            │
└────────────────────┬────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────┐
│ 6. SUBMISSIONS AGENT — orchestrate everything       │
│    - DSP delivery (LabelGrid/Revelator API)         │
│    - Identifier ingestion (UPC/ISRC)                │
│    - PRO registration (Fonzworth ASCAP browser)     │
│    - Mechanical (MLC DDEX)                          │
│    - Neighboring rights (SoundExchange portal)      │
│    - YouTube Content ID (where partner status)      │
│    - Logged to song_submissions for audit           │
└────────────────────┬────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────┐
│ 7. MARKETING — phase-gated (M0-M5)                  │
│    - 14 marketing agents (catalog in §43)           │
│    - Metric-gated phase transitions                 │
│    - Paid spend only on proven creatives            │
└────────────────────┬────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────┐
│ 8. PERFORMANCE INGESTION + FEEDBACK                 │
│    - Streams, revenue, social growth per song       │
│    - Outcome resolution feeds the ML model          │
│    - Reinvest → next cycle                          │
└────────────────────┬────────────────────────────────┘
                     │
                     └──── LOOP BACK TO STEP 1 ────────┘
```

### End-to-End Example

```
SoundPulse detects: r&b/soul has 17 breakouts in 30 days. Feature deltas
  show energy +12% vs baseline (p=0.001), acousticness +17% (p=0.012),
  danceability -18% (p=0.002). Top gap zone: "slow (106 BPM), medium-
  energy, moody, electronic" — 5/5 breakouts (100% rate, 5 tracks total).
  Opportunity score 0.82. Quantification: $1,500 median revenue, medium
  confidence. Surfaced 3 days ago.

Artist fit: best existing artist scores 0.41 (below 0.68 threshold).
  → Generate new artist.

CEO Action Agent sends Telegram message to CEO with proposed artist
  spec (3 alternatives). CEO approves option B.

Generate artist "VOIDBOY" — moody R&B persona, 8-view reference sheet,
  voice_dna defined.

Smart Prompt v2 produces: "STYLE: slow-burning moody R&B, 106 BPM,
  medium-low energy, acoustic guitar with electronic textures..."

Suno via EvoLink generates the track. Audio QA passes.

Submissions Agent:
  → LabelGrid create release → poll for ISRC/UPC → confirmed
  → Fonzworth ASCAP browser registers the work
  → MLC DDEX file submitted
  → SoundExchange portal entry created
  → YouTube CMS asset ingested

Marketing Phase M0 (asset readiness) → M1 (identity seeding)
  → 10 posts published, 100 followers, watch-through 18%
  → Phase M2 (song anchoring): 5K views, 1K pre-saves, 3 playlist adds
  → Phase M3 (amplification): paid spend kicked in, 25K clip views
  → Phase M4 (breakout): playlist algo pickup, 25K monthly streams

Day 30: 18,000 streams. Revenue: $72.
Outcome resolved. ML model retrained. VOIDBOY catalog: 1 song, growing.
```

---

## §3. Artist Portfolio Strategy

SoundPulse manages a roster of AI artists. Each artist is a persistent persona with a genre niche, visual identity, social presence, voice, and growing discography.

### Artist DNA vs Song DNA

**Artist DNA** (persistent — defines who the artist IS, see §17 for the `ai_artists` schema):

| Category | Fields |
|---|---|
| **Identity** | stage_name, legal_name, age, gender_presentation, ethnicity_heritage, provenance, languages |
| **Voice (`voice_dna`)** | timbre_core, brightness, thickness, breathiness, range_estimate, delivery_style[], phrasing_density, accent, autotune_profile, adlib_profile, harmony_profile, reference_song_ids[], suno_persona_id |
| **Visual (`visual_dna`)** | face_description, body_presentation, hair_signature, tattoos_piercings[], color_palette[], art_direction, reference_sheet_asset_id |
| **Fashion (`fashion_dna`)** | style_summary, core_garments[], materials[], accessories[], footwear[], cultural_style_refs[], avoid[] |
| **Lyrical (`lyrical_dna`)** | recurring_themes[], vocab_level, perspective, motifs[], content_rating |
| **Persona (`persona_dna`)** | backstory, personality_traits[], social_voice, posting_style, controversy_stance |
| **Social (`social_dna`)** | platform_handles{}, content_calendar_template, engagement_style |

**Song DNA** (varies per track):

| Category | Fields |
|---|---|
| **Sonic** | tempo, key, mode, energy, valence, danceability, acousticness, instrumentalness, liveness, speechiness, loudness |
| **Structure** | section arrangement, chorus ratio, intro length |
| **Theme** | what THIS specific song is about |
| **Lyrics** | actual lyric content (generated per song) |

**Generation = Artist DNA + Song DNA + voice prompt → unified generation prompt** (see §24).

### Artist Lifecycle

| Stage | Description | Actions |
|---|---|---|
| **Birth** | Genre opportunity detected, no suitable existing artist | Generate persona, social accounts, first 2-3 songs |
| **Growth** | First 5-10 songs, building audience | Aggressive marketing, playlist pitching, high cadence |
| **Maturity** | 10+ songs, established audience | Consistent releases, cross-promote, sync exploration |
| **Evolution** | Genre trends shift | Gradually evolve sound, or create side-project persona |
| **Retirement** | Declining audience, genre saturated | Reduce releases, let catalog generate passive revenue |

**NOTE on principle**: A genre does NOT imply only one artist forever. Multiple artists can occupy the same genre with different brand positioning, audience cuts, or release cadence. The decision is made per blueprint via the assignment engine (§22).

---

## §4. Phased Rollout — current state (April 2026)

### Phase 1 — Data Foundation 🟢 **DONE**
- Chartmetric scraper (172,800 calls/day budget, ~10% used)
- Spotify scraper (catalog + popularity)
- Genius lyrics scraper (idle until `GENIUS_API_KEY` set)
- MusicBrainz, Kworb, Radio scrapers
- Tunebat audio features crawler (BlackTip-powered, autonomous)
- 23,000+ trending snapshots, 6,400+ tracks, 2,716 artists, 1,732 with chartmetric_id, 1,727 with classified genres
- 16-endpoint API, React frontend (8 pages), Railway 5-service deployment, Neon DB, 11 alembic migrations

### Phase 2 — Intelligence 🟢 **DONE**
- Breakout Analysis Engine (6 layers, see §10)
- Opportunity Quantification (see §11)
- Smart Prompt v2 (see §12)
- Genre opportunity score v2 (replaces naive v1)
- Settings UI with CEO profile + Tools/Agents registry (see §49, §50)
- Submissions Agent (#14, see §43)
- 1,090+ tracks with full audio features (and growing autonomously)

### Phase 3 — Production Pipeline 🟢 **FRAMEWORK COMPLETE** (April 13, 2026)
- **Artist creation system (§18-21)** — ✅ Shipped with ethnicity/gender/age + edge_profile fields, fashion-editorial portraits with genre-specific references (HYBE teaser for K-pop, Dazed Caribbean for reggae, Complex for hip-hop), 8-view reference sheets with face-locked /v1/images/edits.
- **Song generation under artist (§24)** — ✅ Shipped. Blueprint → assignment engine (10 live dimensions) → CEO gate → orchestrator → suno_kie. Includes upload-instrumental + Suno add-vocals flow.
- **Edgy Themes pipeline (§10 Layer 7)** — ✅ Shipped. Edge rules + earworm rules + HOOK ISOLATION + per-artist edge_profile + pop_culture_references scraper + genre_traits multi-dimensional profile.
- **Fonzworth ASCAP service (§31, T-190..T-194)** — ⚠️ FRAMEWORK shipped. DB tracking + scraper skeleton + admin endpoints live. Playwright container image needs 3-line Dockerfile edit to enable live submissions.
- **Other rights lanes (§32-36)** — ⚠️ FRAMEWORK shipped. external_submissions table + generic dispatcher + 20 seeded targets + dependency graph. DistroKid/TuneCore/BMI/MLC/SoundExchange/YouTube Content ID all registered as stub adapters — 1-function-body replacement to go live per target as credentials land.
- **Metadata projection (§27, T-167)** — ✅ Shipped. ISRC minting, writers/publishers, LLM-backed marketing enrichment (marketing_hook, pr_angle, playlist_fit, target_audience_tags, release_strategy, mood_tags).
- **Audio QA full (§25, T-162-full)** — ✅ Shipped. Librosa-backed tempo/loudness/key/silence/peak/spectral centroid/MFCC analysis with Krumhansl key detection.
- **Marketing agents (§37, T-225+)** — ✅ Two live adapters shipped: press_release_agent (AP-style release with headline/dateline/lede/quote/boilerplate) and social_media_agent (platform-specific captions for TikTok/Instagram/X/YouTube Shorts/Threads). Both pure LLM, no external credentials required.
- **Submissions Agent downstream pipeline (T-225+)** — ✅ Shipped. sweep_downstream_pipeline() walks qa_passed songs through the dependency graph, dispatching each target in order (distributor → PRO → SoundExchange → playlists → marketing).
- **Public instrumental submission page** — ✅ Shipped. External producers get a shareable URL (`/submit/instrumental`) with rate-limited upload.
- **Multi-provider LLM resilience** — ✅ Shipped. Groq + OpenAI + Gemini all wired through config-driven llm_client. Per-provider fallback via llm.json action flip.

### Phase 4 — ML & Optimization 📋 **TODO**
- ML hit predictor training on resolved breakout outcomes (§13)
  ↳ blocked on data depth — need ~6 weeks of resolved breakout_events before XGBoost gradient boosting is viable. Target: late May 2026.
- Outcome calibration of the quantification confidence model (§11)
- Cross-platform cascade timing model
- Per-artist success predictor (Artist DNA → growth probability)
- **Duplicate detection via MFCC cosine similarity** — shipped as a computed field in song_qa_reports; the sweep that flags duplicates is a straightforward follow-up.

### What's left to go fully autonomous

The framework is end-to-end complete. The remaining work is a series of thin per-target adapter bodies that replace the `_stub_adapter` stubs registered in `api/services/external_submission_agent.py`. Each target follows the same pattern: check env credentials, call portal (httpx for API-based, Playwright for browser-driven), parse response, return (status, external_id, response_dict). The shared dispatcher handles retries, rate-limiting, state tracking, and CEO escalation.

**In approximate priority order** (based on which unblocks revenue fastest):
1. **DistroKid Playwright adapter** — unblocks everything downstream (SoundExchange, playlists, marketing sweeps all depend on distributor status). Highest ROI.
2. **MLC DDEX XML generator** — publisher-side PRO, has a real API (not browser automation).
3. **YouTube Content ID** — Google CMS partner API, needs a service account JSON.
4. **Spotify for Artists editorial pitch** — Playwright; depends on DistroKid live.
5. **Remaining distributors** (TuneCore, CD Baby, Amuse, UnitedMasters) — parallel alternatives.
6. **BMI, SoundExchange** — writer/performance royalty lanes (Playwright).
7. **Sync marketplaces** (Musicbed, Marmoset, Artlist, SubmitHub) — mostly Playwright, SubmitHub has a real API.
8. **Playlist pitching** (Groover, Playlist Push) — Playwright.
9. **TikTok upload bot** — Playwright, most fragile (TikTok hates automation).

Each adapter is a 100-300 line module with the same skeleton. Average time to implement one: 4-8 hours with portal access + manual selector tuning against the real DOM.

---

## §5. Success Metrics

### Phase 1 (DONE)
| Metric | Target | Current |
|---|---|---|
| Data freshness | <6 hours stale | ✅ |
| Entity match rate | >85% cross-platform | ✅ |
| API uptime | >99% | ✅ |

### Phase 2 (DONE)
| Metric | Target | Current |
|---|---|---|
| Breakout detection | >50 breakouts/sweep | ✅ 1,093 first sweep |
| Audio feature coverage | >90% of top 200 | 🟡 ~17% (831 tracks, growing via Tunebat) |
| Smart prompt latency | <5 sec | ✅ ~2 sec for 5 prompts in parallel |

### Phase 3 (TODO)
| Metric | Target |
|---|---|
| Songs generated per month | >50 across genre niches |
| Distribution success rate | >95% delivered to all DSPs |
| TikTok engagement | >1% avg engagement rate on teasers |
| Autonomous uptime | Full pipeline 30+ days without intervention |
| First revenue | >=1 song generating >$1/month |
| Break-even | Portfolio reaches $2K+/month within 6 months |

---

## §6. Unit Economics

### Per-song economics (researched April 2026)

| Item | Cost | Notes |
|---|---|---|
| Song generation (Suno via EvoLink) | ~$0.111/song | EvoLink REST wrapper around Suno |
| Cover art (DALL-E 3) | ~$0.04/image | OpenAI |
| Reference sheet (Stable Diffusion + IP-Adapter) | <$0.10 | via Replicate |
| Distribution (LabelGrid) | ~$0.12/song | $1,428/yr ÷ ~12K songs/yr capacity |
| ASCAP registration (Fonzworth automation) | ~$0/song | self-hosted browser automation |
| MLC mechanical | $0 | DDEX free for members |
| SoundExchange | $0 | portal-based |
| **Total — generation + distribution + rights** | **~$0.40/song** | |
| Promotion (Playlist Push campaign) | ~$300/song | optional Phase M3 |
| **Total with $300 promo** | **~$300.40** | |

**Key insight:** Generation is nearly free. Distribution is sub-dollar. The dominant cost is **promotion**, and that only fires when the data says it's worth it (gated by Marketing Phase M3).

### Per-stream payouts

| Platform | $/stream (low) | $/stream (mid) | $/stream (high) |
|---|---|---|---|
| Spotify | $0.0024 | $0.004 | $0.0084 |
| Apple Music | $0.006 | $0.008 | $0.010 |
| YouTube Music | $0.0006 | $0.0008 | $0.001 |
| Tidal | $0.011 | $0.0125 | $0.014 |
| Amazon Music | $0.003 | $0.004 | $0.005 |

These rates feed the Opportunity Quantification model (§11).

### Portfolio revenue projection

| Catalog | Hit songs (20%) | Avg streams/mo (hit) | Revenue/mo | Promo (cumulative) | Net |
|---|---|---|---|---|---|
| 50 | 10 | 3K | $120 | $15K | -$710/mo |
| 200 | 40 | 5K | $800 | $60K | -$600/mo |
| 500 | 100 | 8K | $3,200 | $150K | +$1,000/mo |
| 1,000 | 200 | 10K | $8,000 | $300K | +$4,000/mo |

**Break-even ~500 songs in catalog with 100 getting traction at 8K/mo. Path: ~12-18 months of cumulative investment.**

The entire prediction stack exists to push hit rate from 20% toward 40%+. The breakout engine + smart prompt v2 + ML hit predictor are the levers.

---

# Part II — Intelligence & Data (BUILT)

## §7. Data Collection Layer

### Active scrapers

| Scraper | Cadence | Purpose | Status |
|---|---|---|---|
| `chartmetric` | 4h | Live chart data, 6 confirmed endpoints | BUILT |
| `chartmetric_deep_us` | 3h | ENDPOINT_MATRIX (~281 calls/run, all genres × platforms) | BUILT |
| `chartmetric_artist_tracks` | 48h | Per-artist catalog crawl | BUILT |
| `chartmetric_artist_stats` | 48h | Per-artist platform stats (followers, listeners) | BUILT |
| `chartmetric_us_cities` | 12h | Top US cities × Apple Music charts | BUILT |
| `chartmetric_artists` | 12h | Per-artist platform stats (legacy) | BUILT |
| `chartmetric_audio_features` | 6h | tempo + duration_ms ONLY (CM API limitation) | BUILT |
| `chartmetric_playlist_crawler` | 72h | Top US playlists + their tracks | BUILT |
| `spotify` | 6h | Spotify catalog search | BUILT |
| `spotify_audio` | n/a | DEPRECATED — `/v1/audio-features` returns 403 for post-Nov-2024 apps | DEAD |
| `tunebat` (BlackTip) | continuous | Full 12 audio features via Cloudflare bypass scrape | BUILT (Railway service) |
| `genius_lyrics` | 24h | Lyrics + theme extraction | BUILT (idle until `GENIUS_API_KEY`) |
| `kworb` | 24h | Free public Spotify chart data | BUILT |
| `radio` | 24h | Radio airplay charts (free) | BUILT |
| `musicbrainz` | 12h | ISRC + open metadata | BUILT |

### Chartmetric as the backbone

Paid tier ($350/mo, 2 req/sec, **172,800 req/day budget**). Current usage: ~10% of quota. We have headroom for 9× more endpoints.

**Critical correction from v2** (validated against the API): the following claims in older docs are wrong, do not implement:
- Spotify `type=plays` parameter — does not exist
- Billboard charts via Chartmetric — not exposed
- Chart endpoints with a `limit` param — only `airplay`, `twitch`, `tiktok/top-tracks` accept `limit`; everything else uses `offset`
- Amazon endpoints accept `country_code` — wrong, they want `code2` (uppercase ISO2)
- Weekday-restricted endpoints: YouTube + FreshFind = Thursday only; SoundCloud + Beatport = Friday only

### Entity resolution

RapidFuzz fuzzy matching with >85% similarity threshold. Tracks resolved by ISRC > spotify_id > (title + artist_name) fuzzy. Artists resolved by spotify_id > chartmetric_id > name fuzzy. Side-effect creation in `resolve_artist()` now sets `metadata_json.needs_classification = true` so the genre classifier sweep picks them up.

---

## §8. Song DNA — feature set

### Sonic features (audio analysis — 13 fields)

Source: Tunebat scrape (BlackTip), supplemented by Chartmetric `/api/track/{id}` for tempo + duration_ms only.

| Field | Range | Source |
|---|---|---|
| tempo | BPM | Tunebat / Chartmetric |
| key | 0-11 (C..B) | Tunebat |
| mode | 0=minor, 1=major | Tunebat |
| energy | 0-1 | Tunebat |
| danceability | 0-1 | Tunebat |
| valence | 0-1 (named "happiness" on Tunebat) | Tunebat |
| acousticness | 0-1 | Tunebat |
| instrumentalness | 0-1 | Tunebat |
| liveness | 0-1 | Tunebat |
| speechiness | 0-1 | Tunebat |
| loudness | dB | Tunebat |
| duration_ms | int | Tunebat / Chartmetric |
| time_signature | int | Tunebat (when available) |

Bonus metadata from Tunebat: `camelot` notation, `popularity`, `release_date`, `explicit`, `album`.

### Lyrical features (Genius)

Stored in `track_lyrics`:
- raw `lyrics_text`
- `word_count`, `line_count`, `vocabulary_richness`
- `section_structure` array (verse/chorus/bridge/etc.)
- `themes` (10 keyword buckets) + `primary_theme`
- `language`
- For LLM analysis (Layer 6 of Breakout Engine), see §10.

### Social & cultural context (Chartmetric)

- `/api/artist/{id}/stat/{platform}` — followers, monthly listeners, video creates
- `/api/artist/{id}/where-people-listen` — top cities + countries
- `/api/artist/{id}/{platform}-audience` — demographic data
- `/api/artist/{id}/career` — career timeline + milestones

---

## §9. Genre Intelligence

959-genre taxonomy, hierarchical (12 root categories), bidirectional mappings to Spotify/Apple/MusicBrainz/Chartmetric.

### Opportunity Score v2 (BUILT, replaces naive v1)

```python
breakout_rate    = breakout_count / track_count
breakout_rate_score = min(breakout_rate * 5, 1.0)         # 20% breakout rate = max
hit_quality_score   = min(avg_composite_ratio / 8.0, 1.0) # 8x composite ratio = max
momentum_score      = min(avg_velocity_ratio / 10.0, 1.0) # 10x velocity ratio = max
competitive_gap     = unique_artists / track_count        # already in [0, 1]
confidence          = min(track_count / 20.0, 1.0)        # 20+ tracks = full confidence

opportunity =
  0.35 * breakout_rate_score +
  0.25 * hit_quality_score +
  0.20 * momentum_score +
  0.10 * competitive_gap +
  0.10 * confidence
```

Genres with zero breakouts are pushed BELOW genres with at least one (`(breakout_count > 0, opportunity_score)` sort key). This avoids the v1 problem of niche genres with 2-3 tracks scoring at the top.

Endpoint: `GET /api/v1/blueprint/genres`.

---

## §10. Breakout Analysis Engine

The discovery brain. 6 layers, all built. See `planning/PRD/breakoutengine_prd.md` for the detailed design — this section is the canonical summary for implementation reference.

### Layer 1 — Breakout Detection (BUILT)

For each genre with ≥5 tracks in a 14-day window, compute the median composite_score and median velocity. Flag any track exceeding 2× either median.

```python
composite_ratio = track_peak_composite / genre_median_composite
velocity_ratio  = track_peak_velocity / max(genre_median_velocity, 0.1)
platform_bonus  = 0.1 * (platform_count - 1)

breakout_score = (
    0.5 * min(composite_ratio / 3.0, 1.0) +
    0.3 * min(velocity_ratio / 5.0, 1.0) +
    0.2 * platform_bonus
)
# threshold: breakout_score >= 0.4 → write to breakout_events
```

Cadence: every 6 hours. Schema: `breakout_events` table (see §17). Resolution: after 30 days, the track's composite_score is checked in a ±5 day window around `detection_date + 30d`. Outcome label = `hit` (>2× genre median), `moderate` (>1× median), or `fizzle` (≤1× median).

**Historical backfill** (`POST /admin/sweeps/breakout-detection/backfill?weeks_back=78&step_days=7`): walks reference dates backward from `today - 30d` to `earliest_data + 14d`, runs detection at each reference date, then resolves outcomes from the data already in the DB. This bootstraps the ML hit predictor without waiting 30 days from launch.

### Layer 2 — Feature Delta Analysis (BUILT)

For each genre with ≥3 breakouts and ≥5 baseline tracks, compute Welch's t-test on every audio feature: breakout cohort vs baseline. Cache the deltas and p-values in `genre_feature_deltas`.

Output for each feature: delta (mean breakout − mean baseline) + p-value. Top differentiators = features with p < 0.10, ranked by significance.

Zero scipy dependency — Welch's t-test implemented with `math.erf` for the normal CDF approximation.

### Layer 3 — Lyrical Analysis (BUILT, idle)

For each genre with ≥5 breakout lyrics and ≥10 baseline lyrics, send both sets to an LLM (Groq llama-3.3-70b at $0.59/M input) and ask it to compare. Returns structured JSON: `breakout_themes`, `baseline_themes`, `underserved_themes` (TARGET), `overserved_themes` (AVOID), structural patterns, vocabulary tone, key insight.

Cost: ~$0.02/week at our scale. Cadence: weekly. Cache: `genre_lyrical_analysis`.

**Idle until `GENIUS_API_KEY` is configured.** Pipeline is wired end-to-end; flips on automatically once lyrics start landing.

### Layer 4 — Gap Finder (BUILT)

K-means clustering of audio features per genre. For each cluster:
- `breakout_density` = breakouts in cluster / total tracks in cluster
- `supply_density` = total tracks in cluster / total tracks
- `gap_score` = breakout_density / baseline_breakout_rate

A high gap score = "breakouts happen disproportionately here, but few people compete here." Sort by gap_score, return clusters as opportunity zones with human-readable descriptions ("fast 145 BPM, high-energy, dark, electronic").

Endpoint: `GET /admin/gap-finder?genre=X&n_clusters=N`.

### Layer 5 — Smart Prompt v2 (BUILT, the user-facing payoff)

See §12 for the full description. Synthesizes Layers 1-4 (and 6 when available) into a production-ready Suno/Udio prompt with rationale + confidence + based_on counts.

### Layer 6 — ML Hit Predictor (TODO, data-bound)

XGBoost gradient-boosted trees. Training data = resolved breakout_events. Inputs: 13 audio features + delta-from-genre-baseline + competitive context + platform signals + temporal features. Output: probability the blueprint will produce a hit.

**Cold start solved by the historical backfill above.** Once the backfill runs, we have ~hundreds of resolved events to train on immediately, instead of waiting 30 days.

Training sweep: weekly. Model storage: `model_runs` table + `models/hit_predictor_v{N}.json` on disk. Serving: loaded by smart_prompt service to score gap zones before LLM call.

### Layer 7 — Edgy Themes Pipeline (BUILT, evergreen) — FULL SPEC

The problem Layer 7 solves: without it, the LLM defaults to the most averaged-out "universal" themes ("finally finding myself", "dancing through the pain") that sound like 1,000 other songs in the same genre. SoundPulse's brand voice requires **Sabrina-Carpenter-level edge** — double entendres, named pop-culture references, opinionated takes, concrete sensory hooks — across every genre we ship in.

Three-part architecture, all three in production as of April 2026. Validated end-to-end on Kofi James's breakout generation — the song titled itself "Stanley Cup On The Sink" after the Stanley cup reference injected from the scraper table, and the lyrics weave FaceTime / Air Force 1s / phone-unlock imagery into authentic Jamaican Patois.

---

#### Part 1 — Edge rules in the system prompt

**File:** `api/services/smart_prompt.py::SMART_PROMPT_SYSTEM`

A hard block tells the LLM that every song MUST contain **at least TWO** of the following:

| # | Edge device | Example |
|---|---|---|
| (a) | Chorus-level double entendre | Sabrina Carpenter "Taste" — "you'll just have to taste me when he's kissing you" |
| (b) | Named pop-culture reference <18 months old | Sabrina "Please Please Please" — "switch it up like Nintendo" |
| (c) | Opinionated named-target take | Kendrick "Not Like Us"; Doechii naming gatekeepers |
| (d) | Concrete visual/sensory hook | "mascara on the Uber seat"; "your hoodie still smells like your Elf Bar" |
| (e) | Structural surprise | pre-chorus that subverts the verse; bridge that reframes the song |

**Banned tropes list** (rewrite if caught):
- "I'm finally finding myself"
- "Dancing in the rain" / "Dancing through the pain"
- "They don't understand us"
- "Chasing dreams" / "Making it out"
- "You're the one" / "Meant to be"
- "Through the darkness to the light"
- Any line that could appear unchanged on 100 other songs in the genre

**Reference artist bible** — the system prompt explicitly names these as tone exemplars:
- **Sabrina Carpenter** (Short n' Sweet era) — double entendres, pop-culture references, bratty confidence without meanness
- **Chappell Roan** (Midwest Princess) — specific queer experiences, theatrical commitment to a bit, costume-piece storytelling
- **Doechii** (Alligator Bites Never Heal) — rap witty + vulnerable, industry commentary, voice-shifting
- **Charli XCX** (brat) — internet-native references, confession + confrontation
- **Olivia Rodrigo** (GUTS) — specific anger, named emotions, no metaphor when directness hits harder
- **Tyla** (Water) — sexy with specific body language, not "feeling the vibe"

**Genre-does-not-excuse-blandness rule** — explicit directive: Koffee "W", NewJeans "Super Shy", Sierra Ferrell narrating trauma all prove reggae/k-pop/country can be edgy with the right specificity. If the LLM tries to fall back to "universal" themes because it thinks the genre demands it, it's wrong.

---

#### Part 2 — Per-artist `edge_profile`

**Column:** `ai_artists.edge_profile TEXT` with CHECK constraint.

Three tiers:

| Tier | Artist examples | What's allowed |
|---|---|---|
| `clean_edge` | Taylor Swift, Olivia Rodrigo, Sierra Ferrell, Lewis Capaldi | Sharp takes, named emotions, specific imagery — **no** explicit sex, drugs, or profanity |
| `flirty_edge` | Sabrina Carpenter, Doja Cat, Charli XCX, Doechii (pop mode), Chappell Roan | Double entendres, innuendo, bratty confidence, sex-positive but not explicit |
| `savage_edge` | Doechii (rap mode), Ice Spice, Central Cee, Popcaan, Masicka | Explicit allowed, named targets allowed, drugs / sex / money references direct |

**Genre-based defaults** (persona blender assigns these when the LLM doesn't):
- Reggae / dancehall / hip-hop / trap / drill → `savage_edge`
- K-pop / pop / R&B / latin / afrobeats → `flirty_edge`
- Country / folk / acoustic / Christian → `clean_edge` (unless outlaw-leaning)

**Migration:** alembic 018 adds the column + CHECK constraint. Existing artists are NULL until backfilled (smart_prompt defaults to `flirty_edge` on NULL so the pipeline never blocks).

**Persona blender emits it as required output** — the schema passed to gpt-4o-mini in `persona_blender.SYSTEM_PROMPT` forces an `edge_profile` field with the three allowed values. The validator in `blend_persona()` clamps any off-spec value back to `flirty_edge` before INSERT so the DB constraint never trips.

**Admin write path** — both `create-from-persona` and `from-description` endpoints now pass `edge_profile=persona.get("edge_profile")` into the `AIArtist(...)` constructor. The existing row returned to the UI includes it in the GET response.

---

#### Part 3 — Pop-culture references

**Table:** `pop_culture_references` (alembic migration 018)

```sql
CREATE TABLE pop_culture_references (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  reference_type  TEXT NOT NULL,  -- CHECK constraint on 12 values below
  text            TEXT NOT NULL,  -- "in my villain era", "corn kid autotune edit"
  context         TEXT,           -- "Used to mean 'doing what's best for me'..."
  source          TEXT,           -- "TikTok", "app/meme", "drag/queer TikTok"
  source_url      TEXT,           -- for future scrapers that link-back
  genres          TEXT[] NOT NULL DEFAULT '{}',     -- empty = universal
  edge_tiers      TEXT[] NOT NULL DEFAULT '{flirty_edge,savage_edge}',
  first_seen_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  peak_date       DATE,
  expires_at      TIMESTAMPTZ NOT NULL DEFAULT NOW() + INTERVAL '90 days',
  usage_count     INT NOT NULL DEFAULT 0,
  last_used_at    TIMESTAMPTZ,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT ck_pop_culture_references_type CHECK (reference_type IN (
    'tiktok_sound','tiktok_dance','tiktok_phrase',
    'viral_meme','show_reference','brand','app','gaming',
    'celeb_moment','news_event','lyric_phrase','slang'
  ))
);
CREATE INDEX ix_pop_culture_references_expires_at ON pop_culture_references (expires_at);
CREATE INDEX ix_pop_culture_references_genres ON pop_culture_references USING GIN (genres);
```

**The 12 reference_type values** and what each captures:

| Value | Example text | Example context |
|---|---|---|
| `tiktok_sound` | "corn kid autotune edit" | Used for genuine-love jokes |
| `tiktok_dance` | "the Stanley Cup dance" | Named dance trend |
| `tiktok_phrase` | "in my villain era" | Excusing self-interest |
| `viral_meme` | "girl dinner" | Chaotic feminine aesthetic |
| `show_reference` | "White Lotus confessional" | Privileged breakdown |
| `brand` | "Erewhon smoothie" | Aspirational LA influencer life |
| `app` | "Duolingo streak" | Gamified obsession |
| `gaming` | "Fortnite OG map" | 2018-2020 nostalgia |
| `celeb_moment` | "Selena's CFDA dress" | Named fashion moment |
| `news_event` | "Labubu release" | Non-political cultural moment |
| `lyric_phrase` | "mother is mothering" | Drag/queer TikTok praise |
| `slang` | "the ick" | Dating discourse vocabulary |

**Scraper (MVP)** — `api/services/pop_culture_scraper.py::refresh_pop_culture_references()`

Single LLM call to a "weekly cultural analyst" persona that harvests ~20 references per run. Configured via `config/llm.json` action `pop_culture_scraper` → `smart_prompt_default` (currently Groq llama-3.3-70b; flips to gpt-4o-mini when OpenAI RPD resets).

**The scraper system prompt** (condensed):

> You are a cultural analyst writing a weekly briefing for pop songwriters at a virtual record label. Your job is to surface SPECIFIC, REFERENCEABLE pop-culture moments a lyric writer can actually name-drop in a chorus or verse this week.
>
> Good reference = named, specific, currently-viral, edgy enough to feel of-the-moment.
> Bad reference = vague category ("social media"), generic ("parties"), or stale (>18 months old).
>
> [12 reference type definitions + 3 edge tier definitions + genre list]
>
> Write about 20 references per response. Mix types. Be specific — "TikTok" alone is worthless; "the corn kid autotune edit" is gold. Decay_weeks should be 8 for fast-moving memes, 26 for brand references, 52 for genuine cultural moments.

Returns strict JSON `{ "references": [ { reference_type, text, context, source, genres, edge_tiers, decay_weeks } ] }`. Parser strips code fences and inserts one row per valid entry, computing `expires_at = NOW() + decay_weeks * 7 days`. Skipped-on-validation rows are logged but don't fail the batch.

**Endpoints:**
- `POST /admin/pop-culture/refresh` — manual trigger (becomes a weekly cron later)
- `GET /admin/pop-culture/list?live_only=true&genre=k-pop&edge=flirty_edge&limit=100` — debug/browse current references with all filters

**Future (Phase 2) sources** — when we hit scale, the same table will be fed by:
1. **TikTok Creative Center scraper** (trending sounds + hashtags + creator spotlight)
2. **X trending topics** (via RapidAPI or direct scraping)
3. **Know Your Meme RSS** (filtered to "alive in the last 60 days")
4. **Billboard Hot 100 + Genius lyric scraper** (what phrases are this week's hits coining)
5. **Reddit r/popular top posts** (breakout culture events)
6. **Perplexity / Tavily weekly agent ping** ("what's the biggest pop-culture moment this week")

Same `pop_culture_references` schema, same injection code — each scraper becomes a feeder. The LLM analyst stays in the loop as an editor/de-duplicator.

---

#### Injection into the lyric brief

**File:** `api/services/smart_prompt.py`

When `generate_smart_prompt(db, genre, edge_profile)` runs:

1. Resolves the top-level genre token (`pop.k-pop` → `pop`) so a K-pop artist picks up pop-tagged references plus the universal pool.
2. Calls `fetch_references_for_prompt(db, genre=top_genre, edge_profile=effective_edge, limit=8)` which runs:
   ```sql
   SELECT ... FROM pop_culture_references
   WHERE expires_at > NOW()
     AND (:genre = ANY(genres) OR genres = '{}' OR array_length(genres, 1) IS NULL)
     AND :edge = ANY(edge_tiers)
   ORDER BY RANDOM() LIMIT 8
   ```
   Random sort so consecutive songs for the same artist don't reuse the same hooks.
3. Formats the sample as a `POP_CULTURE_HOOKS` block:
   ```
   POP_CULTURE_HOOKS — live references from our weekly culture briefing.
   Use 1-2 of these where they fit naturally. Do NOT force-fit. Do NOT
   explain them in the lyric — if a reference needs explanation it's
   already dead. Specific > clever > generic.

     1. [tiktok_phrase] "in my villain era" — Used to mean doing what is best for me...
     2. [brand] "Stanley cup" — The pastel 40oz tumbler everyone is obsessed with...
     3. [slang] "the ick" — Sudden disgust at a partner for a small detail...
     ...

   Edge profile: savage_edge — match the tone accordingly.
   ```
4. Injects the block into `SMART_PROMPT_TEMPLATE` alongside breakout data, feature deltas, gap finder output, and lyrical intelligence.
5. LLM returns JSON with the usual `prompt` + `rationale`, plus two new fields: `edge_devices_used` (list of the 2+ edge devices actually put in the lyric) and `pop_culture_hooks_used` (which refs the LLM chose to fold in).
6. `mark_references_used()` bumps `usage_count` + `last_used_at` on every reference that was offered (not just the ones chosen) so the retirement logic has a signal.

**Decay:** `expires_at > NOW()` filter on every fetch. Stale references become invisible automatically — no scheduled prune job needed.

---

#### Per-generation regeneration (the key wiring decision)

**File:** `api/routers/admin.py::generate_song_for_blueprint`

Before calling the orchestrator, the admin endpoint **regenerates the smart_prompt fresh** with the artist's edge_profile rather than reusing the blueprint's genre-only cached text:

```python
from api.services.smart_prompt import generate_smart_prompt
fresh = await generate_smart_prompt(
    db,
    genre=blueprint.primary_genre,
    model="suno",
    edge_profile=getattr(artist, "edge_profile", None),
)
blueprint_dict["smart_prompt_text"] = fresh["prompt"] or blueprint.smart_prompt_text
```

**Why regenerate every time:**
- Blueprints are genre-level and created once; they know nothing about the artist who will eventually get assigned.
- Pop-culture references are time-sensitive — a blueprint from 30 days ago would miss this week's viral phrases.
- Edge profile varies per artist; the same blueprint assigned to Kofi (savage_edge) vs a clean_edge country singer should produce very different lyrics.
- Cost: ~$0.01 per generation at gpt-4o-mini rates, ~$0.001 at Groq rates — trivial relative to the $0.06 Suno call.

**Fallback:** if the fresh call fails (LLM outage, rate limit), the cached blueprint `smart_prompt_text` is used instead. A generation never blocks on the edge layer.

---

#### End-to-end flow diagram

```
  persona_blender (create-from-persona)
    ↓ sets artist.edge_profile based on genre + LLM judgment
    ↓ emits ethnicity/gender/age/visual_dna/fashion_dna/lyrical_dna
    ↓
  POP-CULTURE SCRAPER  (POST /admin/pop-culture/refresh, weekly)
    → Groq llama-3.3-70b (or gpt-4o-mini) harvests ~20 refs
    → INSERT INTO pop_culture_references (expires_at = NOW + decay)
    ↓
  breakout engine (Layers 1-5)
    → song_blueprint created (genre-level, no artist yet)
    ↓
  assignment engine → CEO gate → artist assigned
    ↓
  POST /admin/blueprints/{id}/generate-song
    ├─ load artist + blueprint + voice_state
    ├─ REGENERATE smart_prompt FRESH:
    │    generate_smart_prompt(
    │      genre = blueprint.primary_genre,
    │      edge_profile = artist.edge_profile,    ← Part 2 dial
    │    )
    │    ├─ fetch breakout context + deltas + gap + lyrical intel
    │    ├─ fetch_references_for_prompt(top_genre, edge) → up to 8 refs  ← Part 3 injection
    │    ├─ build template with POP_CULTURE_HOOKS block + EDGE RULES system prompt  ← Part 1
    │    ├─ LLM call (Groq llama-3.3-70b OR gpt-4o-mini)
    │    ├─ mark_references_used() bumps counters
    │    └─ returns { prompt, rationale: {edge_devices_used, pop_culture_hooks_used, ...} }
    ├─ assemble_generation_prompt(
    │    voice_dna_summary  (always)
    │    voice_reference    (non-empty when artist has prior songs)
    │    FRESH smart_prompt  (with edge + live refs) ← overrides blueprint cache
    │    production_constraints
    │    policy_constraints
    │  )
    ├─ suno_kie.generate(final_prompt)
    ├─ persist songs_master (draft) + music_generation_calls
    └─ return { song_id, task_id, estimated_cost_usd }

  → Suno Kie.ai v5.5 generates the song (~60-180s polling window)
  → on SUCCESS: self-host audio bytes, flip songs_master draft → qa_pending
  → audio QA sweep → qa_passed → available in Songs UI
```

---

#### Validation results (April 2026)

Verified on real end-to-end generations before promoting Layer 7 to BUILT:

- **Kofi James (savage_edge, reggae)** — generated "Stanley Cup On The Sink". Title literally pulled from a pop-culture reference injected from the seeded table. Lyrics include "FaceTime glow on the ceiling", "Air Force 1s at the door", "Stanley cup on the sink with your lipstick mark", "phone unlock", "still sleep with your phone unlock" (double entendre: surveillance + intimacy), all in authentic Jamaican Patois. Old pipeline on the same blueprint produced "Rise with Me" and "Identity Study" — exactly the generic self-empowerment slop the edge rules ban.

- **Kira Lune (flirty_edge, K-pop)** — first generation was the generic "Moon Above My Head" baseline. Next generation with Layer 7 wired will get K-pop-specific pop-culture references (Labubu keychain, delulu-is-the-solulu, HYBE comeback aesthetics) filtered to flirty_edge tier.

---

#### Known limitations + Phase 2 roadmap

- **MVP scraper depends on LLM pre-training** — gpt-4o-mini / Groq llama-3.3-70b see an early-2024 cutoff, so "this week's" freshness is approximate. Phase 2 swaps in live scrapers (TikTok Creative Center, X trending, Billboard Hot 100) that feed the same table. Current MVP proves the injection plumbing works.
- **No automatic cron yet** — pop-culture refresh is a manual POST. Phase 2 adds Celery beat schedule (weekly Monday 09:00 UTC).
- **Usage-based retirement is passive** — we bump `usage_count` but don't yet auto-retire overused references. Phase 2 adds a rule: if a reference has been offered to the LLM >50 times, halve its `expires_at` so it exits rotation faster.
- **Edge profile defaults are static** — we don't yet learn which edge level performs best per artist based on stream outcomes. Phase 2: once Layer 6 (ML hit predictor) has training data, feed `edge_profile` as a feature and let the model recommend level-ups/downs.
- **Hooks are random-sampled** — we don't yet prefer references that haven't been used recently. Phase 2: `ORDER BY (usage_count + random()) ASC` so fresh refs bubble up.
- **PRD sentiment checks are manual** — no automated gate that inspects a generated lyric for banned tropes before it hits songs_master. Phase 2: a post-generation LLM validator that rejects lyrics failing the edge rules + loops back for retry.

---

## §11. Opportunity Quantification

For each breakout opportunity, the engine answers two questions:

1. **"How big is this?"** → projected lifetime streams + $ revenue per platform (low/median/high)
2. **"Should I trust the number?"** → explicit confidence level + score + 6 components

See `planning/PRD/opportunity_quantification_spec.md` for the full model. Summary:

### Stream estimation

A new (unproven) track in the gap zone is projected to achieve a peak Spotify popularity discounted from the breakout cohort:

```python
new_track_peak_pop_low    = cohort_p10  * 0.60
new_track_peak_pop_median = cohort_mean * 0.75
new_track_peak_pop_high   = cohort_p90  * 0.90
```

Each popularity is mapped to lifetime stream bands via an industry-known table (popularity 80 → 8M-30M lifetime, popularity 70 → 500K-2M, etc.). Then cross-platform multipliers convert Spotify stream estimates to Apple Music (×0.30), YouTube Music (×0.45), Tidal (×0.02), Amazon (×0.10).

Each platform has a per-stream payout band (low/mid/high). Streams × rates → $ revenue. Sum across platforms = total expected revenue range.

TikTok is reported separately as `estimated_video_uses` (not $) because TikTok pays into a pool, not per-stream.

### Confidence model

Six weighted components, each in [0, 1]:

```python
confidence_score = (
    0.30 * sample_size_score +     # n_breakouts / 15
    0.20 * popularity_coverage +   # n_with_pop_data / n_breakouts
    0.15 * variance_score +        # 1 - std/30 (low variance = high confidence)
    0.10 * data_freshness +        # exp(-days_since_latest / 30)
    0.10 * feature_coverage +      # audio feature coverage % / 100
    0.15 * outcome_calibration     # resolved / total breakouts
)
```

Labels: `high` (≥0.70 + ≥10 breakouts + ≥5 with popularity), `medium` (≥0.45 + ≥5 breakouts), `low` (≥0.25), `very_low`.

### Caching

Computed daily by the same job that runs feature delta analysis (chained). Cached in `breakout_quantifications` keyed by `(genre_id, window_end)`. Surfaced via `top-opportunities` endpoint.

### Honest limitations (documented in the spec)

- Revenue is **gross**, not net of distributor cut, publishing splits, or PRO collection lag.
- Apple/Tidal/Amazon estimates are derivative of Spotify (multiplier model). Genre-specific tuning is a future enhancement.
- TikTok exposure is a discovery proxy, not a direct $ figure.
- The 0.75 discount factor for new tracks is the v1 default. It will be tuned via outcome calibration once we have ≥30 resolved breakouts.
- Confidence depends heavily on `outcome_calibration` which is 0 today; the historical backfill bootstraps this.

---

## §12. Smart Prompt v2 — Blueprint Generation

The user-facing payoff layer. See `api/services/smart_prompt.py`.

### Input (assembled from cached layers)

For a given `genre` and target `model` (suno/udio/soundraw/musicgen):

1. **Breakout context** (Layer 1): n_breakouts, avg composite_ratio, avg velocity_ratio, opportunity rank
2. **Feature deltas** (Layer 2): top differentiators with p-values
3. **Top gap zone** (Layer 4): description, sonic center (tempo/energy/etc.), breakout density
4. **Lyrical intelligence** (Layer 6): breakout themes, underserved themes (TARGET), overserved themes (AVOID), tone, structural patterns, key insight — ONLY IF lyrical analysis exists for this genre
5. **ML hit prediction** (Layer 6 ML): probability score for the gap zone — ONLY IF model is trained

### LLM call

Sent to Groq llama-3.3-70b via `llm_client.py` action `smart_prompt_generation` (temperature 0.7, max_tokens 2000). System prompt establishes the role: "hit songwriter's AI collaborator at a virtual record label."

User prompt directs the LLM to:
1. Target the gap zone sonically
2. Reflect winning differentiators
3. Use one of the underserved themes
4. Avoid overserved themes
5. Match winning vocabulary tone
6. Be SPECIFIC, not generic

### Output

```json
{
  "prompt": "STYLE: ...\n\nLYRICS:\n[Verse 1]\n...",
  "rationale": {
    "sonic_targeting": "one sentence",
    "lyrical_targeting": "one sentence",
    "differentiation": "one sentence"
  },
  "confidence": "high|medium|low",
  "based_on": {
    "breakout_count": 17,
    "feature_deltas_count": 17,
    "feature_baseline_count": 31,
    "gap_clusters": 4,
    "lyrical_analysis_present": false,
    "audio_features_coverage_pct": 100
  },
  "model": "suno",
  "genre": "r-and-b.soul",
  "llm_call": {
    "model": "llama-3.3-70b-versatile",
    "tokens": 1083,
    "cost_cents": 0,
    "latency_ms": 1651
  }
}
```

Endpoint (single genre): `POST /api/v1/blueprint/generate-v2 {genre, model}`

Endpoint (top N in parallel): `GET /api/v1/blueprint/top-opportunities?n=10&model=suno&sort_by=opportunity|revenue|confidence` — also merges in cached quantification + surfaced_at, used by SongLab UI.

---

## §13. Prediction Models

### Current state

The original v2 spec described a LightGBM ensemble. **The breakout engine has effectively replaced this for opportunity detection.** The remaining role for a dedicated ML model is **per-blueprint hit prediction** — given a feature vector, what's the probability this specific blueprint becomes a hit?

### ML Hit Predictor architecture (TODO, P8)

XGBoost regressor, ~70 features:

```python
features = {
    # Audio features (13)
    "tempo", "energy", "danceability", "valence", "acousticness",
    "instrumentalness", "liveness", "speechiness", "loudness",
    "key", "mode", "duration_ms", "time_signature",

    # Genre context (delta from baseline)
    "tempo_delta", "energy_delta", "valence_delta", "danceability_delta",

    # Competitive context
    "genre_track_count", "genre_breakout_rate", "gap_score",

    # Platform signals
    "platform_count_at_detection", "initial_velocity", "initial_composite",

    # Temporal
    "day_of_week", "month", "is_summer",
}

label = outcome_label  # 'hit' (1.0), 'moderate' (0.5), 'fizzle' (0.0)
```

Time-series cross-validation (no future-leakage). Model versioning in `model_runs` table. Serving: loaded into smart_prompt to score gap zones before LLM call.

### Cold start

Solved by the historical backfill (§10 Layer 1). Once the backfill runs, we have ~hundreds of resolved events from the past 18 months immediately.

---

## §14. Model Validation & Backtesting

UI: existing Model Validation page.

### What the model does

Given a track's first 14 days of cross-platform momentum + audio features, predict whether it will reach top-20 in 14 days.

**This was the v2 plan and remains relevant for the 7d/14d/30d horizons.** It complements the ML Hit Predictor (which targets the breakout-vs-fizzle classification post-detection).

### Backtesting

Daily 4:30am UTC cron. Splits data by date, trains on past, validates on held-out future. Metrics: AUC-ROC, precision@10, recall, F1. Stored in `backtest_results`.

---

# Part III — Canonical Workflow & Entity Model

## §15. The 13-step orchestration sequence

This is the **canonical workflow** for a single song from opportunity to revenue. Implemented end-to-end across §10-47.

```
1. Genre opportunity / song opportunity detected         [§10 Breakout Engine]
2. Song Blueprint generated                              [§12 Smart Prompt v2]
3. Artist Fit Evaluation                                 [§22 Assignment Engine]
   - try matching to existing roster
   - if no good fit, generate new artist
4. CEO critical decision gate                            [§23 + §49]
   - approve existing artist assignment
   - or approve creation of new artist
5. Artist finalized                                      [§18-21]
6. Song generated under artist                           [§24]
7. Audio QA + metadata derivation                        [§25, §27]
8. Distribution submission                               [§28-30]
9. Identifier ingestion from distributor                 [§29 Phase 2]
10. Rights / royalty / monetization submissions          [§37-41]
11. Marketing launch and ongoing optimization            [§42-45]
12. Performance ingestion                                [§46]
13. Feedback loops into artist, metadata, marketing      [§43.K Analytics Agent]
```

**Critical correction (resolving v2 vagueness):** The artist is **not always created before the song blueprint**. The blueprint exists FIRST. Then the system decides whether the blueprint belongs under an existing artist or a new artist. After that decision, the actual generated song is created under that artist.

---

## §16. Core entity relationships

```
genre_opportunity         → many   song_blueprints
song_blueprint            → one    song (after generation)
artist                    → many   songs
song                      → one    artist
song                      → many   audio_assets
song                      → one    release_track_record
release                   → many   songs
song                      → many   submissions (per lane)
song                      → many   royalty_registrations
song                      → many   marketing_campaigns
artist                    → many   social_accounts
artist                    → many   visual_assets
breakout_event            → one    track
breakout_quantification   → one    genre + window
ceo_decision              → one    entity (any type)
```

**Principle:** A genre does NOT imply a single artist forever. Multiple artists may occupy the same genre if their brand fits, audience cuts differently, or strategic differentiation calls for it.

**§15 vs §16 — same flow, different lens.** §15 above walks the 13 procedural steps in time order (what happens when). This section maps the same flow through the entity graph (what points to what). Step 1 produces a `breakout_event` + `song_blueprint`; steps 3-5 produce an `artist`; steps 6-7 produce a `song` + `audio_assets`; step 8 produces a `release_track_record`; steps 10-11 produce `royalty_registrations` + `marketing_campaigns`. Every entity in this section can be traced to the step that creates it.

---

## §17. Database schema (canonical, reconciled)

Source-of-truth for the table layer. Order: existing tables (BUILT) → new tables for Phase 3+.

### BUILT — Phase 1 + Phase 2 tables

```sql
-- Existing entity tables (Phase 1, no schema changes)
artists             -- id, name, spotify_id, chartmetric_id, genres[], audio_profile, metadata_json
tracks              -- id, title, artist_id, spotify_id, isrc, chartmetric_id, genres[], audio_features, metadata_json
trending_snapshots  -- id, entity_id, entity_type, snapshot_date, platform, platform_rank, platform_score, signals_json, normalized_score, velocity, composite_score
genres              -- 959 hierarchical taxonomy with platform mappings
predictions         -- id, entity_id, entity_type, predicted_score, confidence, horizon, predicted_at, resolved_at, actual_score
backtest_results    -- model validation per period
scraper_configs     -- scraper scheduling + last_status + last_error
api_keys            -- auth + tier
feedback            -- user prediction feedback

-- Phase 2 tables (BUILT)
llm_calls                       -- per CLAUDE.md mandate, every LLM call logged
breakout_events                 -- §10 Layer 1
genre_feature_deltas            -- §10 Layer 2
genre_lyrical_analysis          -- §10 Layer 3
model_runs                      -- §13 ML model versioning
track_lyrics                    -- §10 Layer 5
breakout_quantifications        -- §11
ceo_profile                     -- §49 single-row
agent_registry                  -- §50 14 agents
tools_registry                  -- §50 41 tools
agent_tool_grants               -- §50 many-to-many
```

### TODO — Phase 3 tables (DDL specs below)

Schema below resolves the marketing spec's underspecified tables. All tables use `id UUID PRIMARY KEY DEFAULT gen_random_uuid()` unless noted.

#### `song_blueprints`
*Resolves marketing spec vagueness: "song blueprint exists upstream" without DDL.*

```sql
CREATE TABLE song_blueprints (
    id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    genre_id                    VARCHAR(100) NOT NULL,
    detected_via                VARCHAR(50) NOT NULL,  -- 'breakout_engine_v2'
    breakout_event_ids          UUID[],                -- which breakouts inspired this
    -- Sonic profile (from gap zone)
    target_tempo                FLOAT,
    target_key                  INT,
    target_mode                 INT,
    target_energy               FLOAT,
    target_danceability         FLOAT,
    target_valence              FLOAT,
    target_acousticness         FLOAT,
    target_loudness             FLOAT,
    -- Lyrical profile
    target_themes               TEXT[],
    avoid_themes                TEXT[],
    vocabulary_tone             VARCHAR(50),
    structural_pattern          JSONB,  -- {avg_verse_lines, chorus_repetition, talk_singing}
    -- Production cues
    production_notes            TEXT,
    reference_track_descriptors TEXT[],
    -- Predicted success
    predicted_success_score     FLOAT,
    quantification_snapshot     JSONB,  -- copy of breakout_quantifications row at creation time
    -- Lifecycle
    status                      VARCHAR(30) NOT NULL DEFAULT 'pending_assignment',
    -- pending_assignment | assigned | rejected | superseded
    smart_prompt_text           TEXT NOT NULL,  -- the actual LLM-generated prompt
    smart_prompt_rationale      JSONB,
    smart_prompt_llm_call_id    UUID REFERENCES llm_calls(id),
    created_at                  TIMESTAMPTZ DEFAULT NOW(),
    updated_at                  TIMESTAMPTZ DEFAULT NOW()
);
```

#### `ai_artists`
*Resolves vagueness: `lyrical_dna`, `persona_dna`, `social_dna` JSON shapes were undefined in source. Defined below.*

```sql
CREATE TABLE ai_artists (
    artist_id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    stage_name                      TEXT NOT NULL UNIQUE,
    legal_name                      TEXT NOT NULL,
    age                             INTEGER,
    gender_presentation             TEXT,
    ethnicity_heritage              TEXT,
    provenance                      TEXT,                -- city/region of origin
    early_life_summary              TEXT,
    relationship_status             TEXT,
    sexual_orientation              TEXT,                -- only if part of brand narrative
    languages                       TEXT[],
    primary_genre                   TEXT NOT NULL,
    adjacent_genres                 TEXT[],
    influences                      TEXT[],
    anti_influences                 TEXT[],
    voice_dna                       JSONB NOT NULL,      -- shape below
    visual_dna                      JSONB NOT NULL,      -- shape below
    fashion_dna                     JSONB,
    lyrical_dna                     JSONB,               -- shape below (NEW DEFINITION)
    persona_dna                     JSONB,               -- shape below (NEW DEFINITION)
    social_dna                      JSONB,               -- shape below (NEW DEFINITION)
    content_rating                  TEXT DEFAULT 'mild', -- clean | mild | explicit
    roster_status                   TEXT DEFAULT 'active', -- active | retired | on_hiatus
    song_count                      INTEGER NOT NULL DEFAULT 0,
    -- Incremented by the song generation pipeline (§24) after each
    -- successfully generated + QA-passed song. Drives the §21 two-phase
    -- voice rule: 0 → descriptive prompt, ≥1 → reference-conditioned.
    last_released_at                TIMESTAMPTZ,
    creation_trigger_blueprint_id   UUID REFERENCES song_blueprints(id),
    ceo_approved                    BOOLEAN DEFAULT FALSE,
    ceo_approval_at                 TIMESTAMPTZ,
    ceo_notes                       TEXT,
    created_at                      TIMESTAMPTZ DEFAULT NOW(),
    updated_at                      TIMESTAMPTZ DEFAULT NOW()
);
```

**Defined JSONB shapes for ai_artists:**

```json
// voice_dna (from marketing spec, verbatim)
{
  "timbre_core": "warm, slightly raspy, breath-forward young male tenor",
  "brightness": "medium-dark",
  "thickness": "light-medium",
  "breathiness": "medium",
  "roughness": "low-medium grit",
  "range_estimate": "A2-E4 chest, falsetto to A4",
  "delivery_style": ["melodic rap", "half-sung verses", "whisper doubles"],
  "phrasing_density": "medium-fast",
  "accent_pronunciation": "US Southwest, light Spanish coloration",
  "autotune_profile": "medium-heavy pitch correction, fast retune on hooks",
  "adlib_profile": ["short breathy echoes", "stacked trailing adlibs"],
  "harmony_profile": "tight octave doubles, occasional third-above harmony",
  "reference_song_ids": [],
  "seed_song_id": null,
  "suno_persona_id": null,
  "consistency_strategy": "description_only_until_seed_song_exists"
}

// visual_dna (from marketing spec, verbatim)
{
  "face_description": "oval face, sharp eyebrows, medium-full lips, slightly hooded eyes",
  "body_presentation": "lean, wiry, medium height",
  "hair_signature": "dark wavy cropped cut",
  "tattoos_piercings": ["small neck tattoo", "single ear hoop"],
  "color_palette": ["#0E0E10", "#5B2EFF", "#9B0D23"],
  "art_direction": "moody urban night photography",
  "reference_sheet_asset_id": null
}

// fashion_dna (from marketing spec, verbatim)
{
  "style_summary": "latin urban streetwear with luxury accents",
  "core_garments": ["oversized bomber", "boxy tees", "stacked cargos"],
  "materials": ["nylon", "denim", "matte leather"],
  "accessories": ["silver chain", "small hoop", "rings"],
  "footwear": ["retro sneakers", "combat silhouettes"],
  "cultural_style_refs": ["reggaeton streetwear", "Y2K sportswear"],
  "avoid": ["formal tailoring", "country western cues"]
}

// lyrical_dna (NEW — was undefined in source)
{
  "recurring_themes": ["heartbreak", "introspection", "small-town defiance"],
  "vocab_level": "conversational",       // simple | conversational | poetic | abstract
  "perspective": "first_person",          // first_person | narrative | omniscient
  "motifs": ["midnight drives", "neon", "ghosts"],
  "rhyme_density": "medium",              // low | medium | high
  "explicit_default": false,
  "language": "en",
  "avoid_phrases": []
}

// persona_dna (NEW — was undefined in source)
{
  "backstory": "Born in Tucson, moved to LA at 19, self-taught producer, dropped out of community college to chase music",
  "personality_traits": ["introverted", "intense", "self-deprecating"],
  "social_voice": "earnest and a little dark, occasional dry humor",
  "posting_style": "irregular but personal — never corporate",
  "controversy_stance": "avoid politics, stay focused on the music",
  "interview_persona": "thoughtful, measured, not eager to please",
  "fan_relationship": "treat fans like co-conspirators, not customers"
}

// social_dna (NEW — was undefined in source)
{
  "platform_handles": {
    "tiktok": "@voidboyofficial",
    "instagram": "@voidboy",
    "youtube": "@VOIDBOYmusic",
    "twitter": "@voidboy_"
  },
  "content_calendar_template": {
    "monday": "lyric clip",
    "tuesday": "studio BTS",
    "wednesday": "fan reply video",
    "thursday": "song teaser",
    "friday": "release post / new track promo",
    "saturday": "lifestyle / aesthetic post",
    "sunday": "lore / backstory"
  },
  "engagement_style": "respond to first 50 comments on every post within 1h",
  "posting_cadence_per_day": 2,
  "preferred_video_length_seconds": 15,
  "hashtag_strategy": "3 niche genre tags + 2 broad pop tags + 1 brand tag"
}
```

#### Other tables (verbatim from marketing spec, no schema changes needed)

The marketing spec defines these tables completely. They're folded in as-is:
- `reference_artists` (full schema in marketing spec §3.2)
- `artist_visual_assets`
- `artist_voice_state`
- `ceo_decisions`
- `audio_assets`
- `song_qa_reports`
- `song_submissions`
- `songs_master` — **the canonical song table**. DDL inlined below (the marketing spec's `songs` from §5.1 is superseded by `songs_master`).

**Resolution of `songs` vs `songs_master` conflict:** Use `songs_master` as the canonical table. Drop the older `songs` (generation subset) from the design.

#### `songs_master` — the canonical song row

Every song the system produces has exactly one row here. ~95 fields across 13 field families, derived once at generation time (§27) and projected outward into lane-specific payloads for distribution, rights, marketing, and analytics.

```sql
CREATE TABLE songs_master (
    -- Identity
    song_id                     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    internal_code                TEXT UNIQUE,                -- e.g. SP-2026-00014
    title                        TEXT NOT NULL,
    title_sort                   TEXT,                        -- for A-Z sort (strips "The", etc.)
    alt_titles                   TEXT[],
    subtitle                     TEXT,
    version_type                 VARCHAR(30),                 -- original | remix | acoustic | radio_edit | extended
    parent_song_id               UUID REFERENCES songs_master(song_id),
    -- Classification
    primary_artist_id            UUID NOT NULL REFERENCES ai_artists(artist_id),
    featured_artist_ids          UUID[],
    blueprint_id                 UUID NOT NULL REFERENCES song_blueprints(id),
    primary_genre                VARCHAR(100) NOT NULL,
    subgenres                    TEXT[],
    mood_tags                    TEXT[],
    content_rating               VARCHAR(10) NOT NULL DEFAULT 'mild', -- clean | mild | explicit
    language                     VARCHAR(10) NOT NULL DEFAULT 'en',
    -- Audio analysis (post-generation, via Essentia + Librosa)
    tempo_bpm                    FLOAT,
    key_pc                       INTEGER,                     -- 0..11 pitch class
    key_mode                     INTEGER,                     -- 0 minor | 1 major
    key_camelot                  VARCHAR(4),                  -- e.g. "8B"
    time_signature               INTEGER,
    duration_seconds             INTEGER,
    loudness_lufs                FLOAT,
    energy                       FLOAT,
    danceability                 FLOAT,
    valence                      FLOAT,
    acousticness                 FLOAT,
    instrumentalness             FLOAT,
    speechiness                  FLOAT,
    liveness                     FLOAT,
    -- Vocals
    vocal_profile                JSONB,                       -- timbre, delivery, autotune_amount, adlib_density
    has_explicit_vocals          BOOLEAN DEFAULT FALSE,
    vocal_mix_ratio              FLOAT,                       -- 0..1 prominence of vocal layer
    -- Lyrics
    lyric_text                   TEXT,
    lyric_themes                 TEXT[],
    lyric_structure              JSONB,                       -- {verses, choruses, bridge, outro}
    lyric_snippet_candidates     JSONB,                       -- TikTok hook offsets
    vocabulary_tags              TEXT[],
    -- Rights
    writers                      JSONB,                       -- [{name, ipi, split, role}]
    publishers                   JSONB,                       -- [{name, ipi, split}]
    master_owner                 TEXT DEFAULT 'SoundPulse Records LLC',
    iswc                         VARCHAR(20),                 -- assigned by PRO
    copyright_year               INTEGER,
    copyright_line               TEXT,
    -- Distribution
    isrc                         VARCHAR(15),                 -- from distributor
    upc                          VARCHAR(20),                 -- from distributor (release-level)
    distributor                  VARCHAR(30),
    distributor_work_id          TEXT,
    territory_rights             TEXT[],                      -- ISO country codes, ['WORLD'] for all
    -- Release planning
    release_id                   UUID REFERENCES releases(id),
    scheduled_release_date       DATE,
    actual_release_date          DATE,
    pre_save_date                DATE,
    release_strategy             VARCHAR(30),                 -- single | album_cut | ep_cut | surprise_drop
    -- Artwork
    primary_artwork_asset_id     UUID,                        -- FK to artist_visual_assets
    alt_artwork_asset_ids        UUID[],
    artwork_brief                TEXT,
    -- Marketing
    marketing_hook               TEXT,                        -- one-line pitch
    marketing_tags               TEXT[],                      -- SEO / playlist-fit / mood labels
    playlist_fit                 TEXT[],                      -- candidate playlist descriptors
    target_audience_tags         TEXT[],
    pr_angle                     TEXT,
    -- Generation metadata
    generation_provider          VARCHAR(30),                 -- suno_evolink | musicgen | udio
    generation_provider_job_id   TEXT,
    generation_prompt            TEXT,
    generation_params            JSONB,
    generation_cost_usd          FLOAT,
    llm_call_id                  UUID REFERENCES llm_calls(id),
    regeneration_count           INTEGER DEFAULT 0,
    -- QA
    qa_report_id                 UUID,                        -- FK to song_qa_reports
    qa_pass                      BOOLEAN,
    duplication_risk_score       FLOAT,
    -- ML predictions (at generation time, frozen for backtest)
    predicted_success_score      FLOAT,
    predicted_stream_range_low   BIGINT,
    predicted_stream_range_median BIGINT,
    predicted_stream_range_high  BIGINT,
    predicted_revenue_usd        FLOAT,
    prediction_model_version     VARCHAR(50),
    prediction_confidence        FLOAT,
    -- Actuals (updated by §46 performance ingestion)
    actual_streams_30d           BIGINT,
    actual_streams_90d           BIGINT,
    actual_streams_lifetime      BIGINT,
    actual_revenue_usd           FLOAT,
    outcome_label                VARCHAR(20),                 -- hit | moderate | fizzle | unresolvable
    outcome_resolved_at          TIMESTAMPTZ,
    -- Lifecycle
    status                       VARCHAR(30) NOT NULL DEFAULT 'draft',
    -- draft | qa_pending | qa_passed | submitted | live | taken_down | archived
    created_at                   TIMESTAMPTZ DEFAULT NOW(),
    updated_at                   TIMESTAMPTZ DEFAULT NOW(),
    -- Derived indexes
    CONSTRAINT songs_master_isrc_unique UNIQUE (isrc)
);

CREATE INDEX idx_songs_master_primary_artist ON songs_master (primary_artist_id);
CREATE INDEX idx_songs_master_blueprint      ON songs_master (blueprint_id);
CREATE INDEX idx_songs_master_release        ON songs_master (release_id);
CREATE INDEX idx_songs_master_status         ON songs_master (status);
CREATE INDEX idx_songs_master_release_date   ON songs_master (actual_release_date);
```

**`song_count` maintenance.** A post-insert trigger on `songs_master` (status transition to `qa_passed`) increments `ai_artists.song_count` and sets `ai_artists.last_released_at = NOW()`. Driven by the song generation pipeline (§24), not manually maintained.

#### Tables that needed DDL (resolved here)

```sql
-- release_track_record
CREATE TABLE release_track_record (
    id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    song_id                     UUID NOT NULL REFERENCES songs_master(song_id),
    release_id                  UUID NOT NULL REFERENCES releases(id),
    track_number                INTEGER NOT NULL,
    is_lead_single              BOOLEAN DEFAULT FALSE,
    created_at                  TIMESTAMPTZ DEFAULT NOW()
);

-- releases
CREATE TABLE releases (
    id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    artist_id                   UUID NOT NULL REFERENCES ai_artists(artist_id),
    title                       TEXT NOT NULL,
    release_type                TEXT NOT NULL,  -- single | EP | album | compilation
    release_date                DATE,
    pre_save_date               DATE,
    upc                         TEXT,
    distributor                 VARCHAR(50),    -- labelgrid | revelator | sonosuite
    distributor_release_id      TEXT,
    artwork_asset_id            UUID,
    status                      VARCHAR(30) DEFAULT 'planning',
    -- planning | submitted | live | takedown_requested | taken_down
    created_at                  TIMESTAMPTZ DEFAULT NOW()
);

-- royalty_registrations (rolled up across all rights lanes)
CREATE TABLE royalty_registrations (
    id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    song_id                     UUID NOT NULL REFERENCES songs_master(song_id),
    lane                        VARCHAR(30) NOT NULL,
    -- pro_ascap | pro_bmi | mlc_mechanical | soundex_neighboring | youtube_cid | sync_marketplace
    target_org                  VARCHAR(100) NOT NULL,
    external_id                 TEXT,           -- their work ID once registered
    status                      VARCHAR(30) DEFAULT 'pending',
    -- pending | submitted | confirmed | rejected | needs_manual_intervention
    submission_payload          JSONB,
    response_payload            JSONB,
    submitted_at                TIMESTAMPTZ,
    confirmed_at                TIMESTAMPTZ,
    error_message               TEXT,
    retry_count                 INTEGER DEFAULT 0,
    created_at                  TIMESTAMPTZ DEFAULT NOW()
);

-- marketing_campaigns
CREATE TABLE marketing_campaigns (
    id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    song_id                     UUID NOT NULL REFERENCES songs_master(song_id),
    artist_id                   UUID NOT NULL REFERENCES ai_artists(artist_id),
    phase                       VARCHAR(10) NOT NULL,  -- M0 | M1 | M2 | M3 | M4 | M5
    started_at                  TIMESTAMPTZ DEFAULT NOW(),
    phase_entered_at            TIMESTAMPTZ DEFAULT NOW(),
    next_gate_check_at          TIMESTAMPTZ,
    metrics_snapshot            JSONB,           -- last metric values
    status                      VARCHAR(30) DEFAULT 'active',
    -- active | paused | graduated | killed
    created_at                  TIMESTAMPTZ DEFAULT NOW(),
    updated_at                  TIMESTAMPTZ DEFAULT NOW()
);

-- social_accounts (per artist)
CREATE TABLE social_accounts (
    id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    artist_id                   UUID NOT NULL REFERENCES ai_artists(artist_id),
    platform                    VARCHAR(30) NOT NULL,
    -- tiktok | instagram | youtube | twitter | facebook | bandcamp | soundcloud
    handle                      VARCHAR(200) NOT NULL,
    display_name                VARCHAR(200),
    platform_user_id            VARCHAR(200),
    oauth_token_encrypted       TEXT,
    refresh_token_encrypted     TEXT,
    token_expires_at            TIMESTAMPTZ,
    follower_count              INTEGER DEFAULT 0,
    last_synced_at              TIMESTAMPTZ,
    status                      VARCHAR(30) DEFAULT 'active',
    -- active | suspended | shadow_banned | deleted
    created_at                  TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (artist_id, platform)
);

-- social_posts
CREATE TABLE social_posts (
    id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    artist_id                   UUID NOT NULL REFERENCES ai_artists(artist_id),
    social_account_id           UUID NOT NULL REFERENCES social_accounts(id),
    song_id                     UUID REFERENCES songs_master(song_id),
    campaign_id                 UUID REFERENCES marketing_campaigns(id),
    platform                    VARCHAR(30) NOT NULL,
    post_kind                   VARCHAR(30) NOT NULL,
    -- video | image | text | story | reel
    content_brief               TEXT,
    asset_url                   TEXT,
    caption                     TEXT,
    hashtags                    TEXT[],
    scheduled_for               TIMESTAMPTZ,
    posted_at                   TIMESTAMPTZ,
    platform_post_id            VARCHAR(200),
    views                       INTEGER DEFAULT 0,
    likes                       INTEGER DEFAULT 0,
    shares                      INTEGER DEFAULT 0,
    saves                       INTEGER DEFAULT 0,
    comments                    INTEGER DEFAULT 0,
    last_metrics_at             TIMESTAMPTZ,
    status                      VARCHAR(30) DEFAULT 'draft',
    -- draft | scheduled | posted | failed | deleted
    created_at                  TIMESTAMPTZ DEFAULT NOW()
);

-- genre_config (per-genre tunables for the assignment + artist pipelines)
-- Resolves v2 vagueness: §18 N=3 reference-artist default needed a home.
CREATE TABLE genre_config (
    genre_id                    VARCHAR(100) PRIMARY KEY REFERENCES genres(id),
    reference_artist_count      INTEGER NOT NULL DEFAULT 3,
    -- how many reference artists §19 pulls for this genre
    reuse_threshold             FLOAT NOT NULL DEFAULT 0.68,
    -- §22 reuse_score cutoff; some genres may demand a stricter reuse bar
    cooldown_days               INTEGER NOT NULL DEFAULT 14,
    -- minimum gap between releases from the same artist in this genre
    max_artists_per_genre       INTEGER,
    -- portfolio cap; NULL means "uncapped"
    ceo_approval_required       BOOLEAN NOT NULL DEFAULT TRUE,
    -- whether §23 CEO gate is mandatory for this genre
    notes                       TEXT,
    updated_at                  TIMESTAMPTZ DEFAULT NOW()
);

-- revenue_events
CREATE TABLE revenue_events (
    id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    song_id                     UUID NOT NULL REFERENCES songs_master(song_id),
    artist_id                   UUID NOT NULL REFERENCES ai_artists(artist_id),
    platform                    VARCHAR(50) NOT NULL,
    territory                   VARCHAR(10),
    period_start                DATE NOT NULL,
    period_end                  DATE NOT NULL,
    stream_count                BIGINT DEFAULT 0,
    revenue_cents               BIGINT DEFAULT 0,
    royalty_type                VARCHAR(30),
    -- streaming | mechanical | performance | sync | content_id
    source                      VARCHAR(50),
    -- distributor | mlc | ascap | bmi | soundex | youtube | direct
    raw_payload                 JSONB,
    created_at                  TIMESTAMPTZ DEFAULT NOW()
);
```

---

# Part IV — Artist System

## §18. Artist creation pipeline

For each new song blueprint that does not map to an existing artist (per §22 decision engine), create a new artist:

```
song_blueprint
  → choose 3 reference artists in target niche      [§19]
  → enrich each with reference_artist data
  → validate copy risk (no >0.75 similarity)
  → blend candidate persona via LLM + deterministic rules
  → generate A/B/C alternatives
  → CEO approval gate                               [§23]
  → persist as ai_artists row
  → generate visual reference sheet                 [§20]
  → initialize voice_state                          [§21]
```

**N=3 reference artists** is the default. Tunable per genre via `genre_config.reference_artist_count` (§17).

---

## §19. Artist reference research pipeline

For each new blueprint requiring a new artist:

### Step A — Choose reference artists

Select top N=3 real artists in the target niche from:
- Genre + subgenre from blueprint
- Momentum window (last 90 days)
- Charting + social growth from Chartmetric

### Step B — Enrich each reference

For each reference artist, populate the `reference_artists` table (full DDL in marketing spec §3.2). Sources:

| Field family | Source |
|---|---|
| **Factual** (age, nationality, languages, genres) | Chartmetric `/api/artist/{id}` + Wikipedia + bio + press kit (browser scrape via BlackTip) |
| **Visual** (face, body, hair, fashion, color palette) | 10-20 public images via vision pipeline (Claude Vision through `llm_client.py`) |
| **Voice** (timbre, range, delivery, accent, autotune) | 3-5 top songs analyzed via Essentia/Librosa for pitch contour, spectral centroid, breathiness, vocal range, speech-vs-sung ratio, phrasing density |
| **Lyrical** (themes, perspective) | Lyric analysis via Genius + LLM theme extraction |
| **Social voice** | Recent posts scraped via BlackTip from official handles |

### Step C — Compute confidence per field

Each enrichment field carries a `confidence_report` JSON: `{age: 0.95, voice_timbre: 0.7, ...}`. Per the non-negotiable rule (§58), any field derived from weak inference must carry a confidence score.

---

## §20. Visual reference sheet (8-view)

**Resolved from marketing spec §3.5:** an 8-view composite (replacing the older 6-angle from v2). Views:

1. Front face
2. Side L
3. Side R
4. Back
5. Top-L looking down
6. Top-R looking down
7. Bottom-L looking up
8. Bottom-R looking up

Process:
1. Generate master front portrait via Stable Diffusion + IP-Adapter (or Flux) using `visual_dna` prompt
2. Lock embedding/seed from the master
3. Generate the other 7 views with the locked embedding
4. Composite into single 8-view sheet
5. Run facial consistency QA across all 8 views (custom check via embedding similarity)
6. Set as canonical `visual_dna.reference_sheet_asset_id` on the artist row
7. All future image generation uses this sheet as conditioning anchor

Stored in `artist_visual_assets`.

---

## §21. Voice consistency (two-phase rule)

**Resolved from marketing spec §3.6:**

### Rule 1 — First song (`song_count == 0`)

```python
voice_prompt = build_descriptive_prompt(artist.voice_dna)
# Uses: timbre, range, delivery_style[], accent, autotune_profile,
#       adlib_profile, influences[]
# No reference audio — Suno is given a textual description only
```

### Rule 2 — Subsequent songs (`song_count >= 1`)

```python
voice_prompt = build_referenced_prompt(
    artist.voice_dna,
    seed_song_id           = artist_voice_state.seed_song_id,
    best_reference_song_id = artist_voice_state.best_reference_song_id,
    latest_reference_song_id = artist_voice_state.latest_reference_song_id,
    suno_persona_id        = artist_voice_state.suno_persona_id,  # if provider supports
)
# Order of preference for reference:
#   1. seed_song (the first one — defines canonical voice)
#   2. best_performing (highest streams to date)
#   3. most_recent (catches gradual evolution)
```

**Honest constraint:** Do not assume text-only prompts guarantee voice consistency. The first song establishes the seed; reference-conditioning improves consistency on subsequent songs but doesn't guarantee it. If a generated track's voice diverges materially from prior tracks, it fails QA (§25) and is regenerated.

### `voice_state_reference_block` — the exact prompt fragment §24 injects

Used by §24 during prompt assembly. Returned by a helper `build_voice_state_reference_block(artist_id) → str | None` that reads `ai_artists.song_count` and picks Rule 1 vs Rule 2.

```python
# Rule 1 (song_count == 0) — returns None.
# §24 skips injection entirely; the descriptive voice_dna_summary block
# already carries the full voice description.

# Rule 2 (song_count >= 1) — returns a text block shaped like this:
"""
[VOICE REFERENCE]
This artist has an established vocal identity. Match it tightly.
Seed reference:      <storage_url of artist_voice_state.seed_song_audio>
Best-performing:     <storage_url of artist_voice_state.best_reference_song_audio>
Most-recent:         <storage_url of artist_voice_state.latest_reference_song_audio>
Provider persona:    <suno_persona_id if available, else "none">
Consistency targets:
  - Timbre drift vs seed:     < 0.12 cosine distance
  - Pitch contour similarity: > 0.75
  - Delivery style:           <artist.voice_dna.delivery_style joined>
Fail the generation rather than compromise voice consistency.
"""
```

The block is a fixed-shape Jinja template in `api/services/prompt_assembly.py` (to be built in P8/P9 work). It is serialized into the Suno generation payload alongside the textual prompt, with the three reference URLs hitting the provider's reference-audio slot where supported (Suno via EvoLink supports up to 2; if the provider only accepts one we use seed_song as the canonical).

---

## §22. Assignment-vs-creation decision engine

**Trigger:** every new song blueprint goes through this engine before any artist action.

### Inputs

- `song_blueprint` (§17 schema)
- `roster` — list of `ai_artists` rows
- `artist_performance_state` — recent stream counts, follower growth, last release date, cadence health
- `portfolio_strategy_state` — diversification goals, niche coverage, capacity per artist

### Scoring dimensions (10 total)

1. **genre_match** — exact + adjacent + influence overlap
2. **voice_fit** — does the blueprint's vocal demands match `voice_dna`?
3. **lyrical_fit** — themes overlap with `lyrical_dna.recurring_themes`?
4. **visual_brand_fit** — does the song fit the artist's `visual_dna` aesthetic?
5. **audience_fit** — does the song match the artist's existing listener demographics?
6. **release_cadence_fit** — has the artist released too recently? (cooldown ≥14 days)
7. **momentum_fit** — *(NEW, resolved from marketing spec vagueness — was referenced in formula but not in dimension list)* — does the artist have current upward momentum that this release can ride?
8. **cannibalization_risk** — will this song eat into the artist's existing catalog's algorithmic placement?
9. **brand_stretch_risk** — does this song stretch the brand too far?
10. **strategic_diversification_value** — does keeping this on the existing artist hurt portfolio diversity?

### Decision formulas (with `momentum_fit` added)

```python
reuse_score = (
    0.22 * genre_match +
    0.18 * voice_fit +
    0.12 * lyrical_fit +
    0.12 * brand_fit +
    0.10 * audience_fit +
    0.08 * cadence_fit +
    0.08 * momentum_fit -      # was referenced but undefined in source
    0.05 * cannibalization_risk -
    0.05 * stretch_risk
)
# Range: roughly [0, 1]; threshold for reuse = 0.68

new_artist_score = (
    0.25 * differentiation_value +
    0.20 * untapped_audience_value +
    0.15 * blueprint_specialization_value +
    0.10 * catalog_hygiene_value +
    0.10 * experimental_portfolio_value +
    0.10 * current_artist_saturation +
    0.10 * artist_fit_failure
)
```

### Decision logic

```python
if best_existing_reuse_score >= 0.68 and not override_flags:
    proposal = "reuse"
    propose_artist = best_existing
else:
    proposal = "create_new"
    generate_persona_alternatives(N=3)

# Either way, send to CEO Action Agent (§23) for approval
ceo_decision = request_ceo_decision(proposal, ...)
```

**0.68 threshold** is the v1 default. Tunable. Future calibration can use outcome data (was the reused-artist song's performance better/worse than projected? was the new-artist song's growth better/worse?).

---

## §23. CEO critical decision gate

**The first mandatory CEO gate** in the autonomous pipeline. Triggered by §22.

### Action: `request_ceo_decision`

```json
{
  "decision_id": "uuid",
  "decision_type": "artist_assignment",
  "entity_type": "song_blueprint",
  "entity_id": "uuid",
  "proposal": "reuse | create_new",
  "data": {
    "song_blueprint": {...},
    "proposed_artist": { /* if reuse */ },
    "alternatives": [ /* if create_new: 3 persona alternatives */ ],
    "scoring_breakdown": {
      "reuse_scores": {"artist_id": 0.71, ...},
      "new_artist_scores": [0.62, 0.58, 0.55]
    },
    "context": "natural-language summary explaining the recommendation"
  },
  "sent_via": "telegram",
  "sent_at": "2026-04-12T22:00:00Z"
}
```

### Channels

Per `ceo_profile` (§49): `telegram` (default), `email`, `phone` (SMS via Twilio future), `slack`. The CEO Action Agent (M) reads `ceo_profile.preferred_channel` and routes accordingly.

### Possible responses

| Response | Effect |
|---|---|
| `approve` | Proceed with the proposal as-is |
| `approve_with_modifications` | CEO edits a field, system uses the modified version |
| `reject` | Mark blueprint as `rejected`, do not generate |
| `request_new_options` | Send 3 different alternatives (only valid for create_new) |

Recorded in `ceo_decisions` table. Workflow blocks until response or timeout (default 24h, configurable).

### Other CEO gates

Additional decision points that escalate to CEO:
- Paid spend >$X per song (Phase M3 amplification)
- Brand pivot (artist direction change)
- Catalog takedown
- New tool/credential requiring spend
- Detection of policy issue (DMCA, copyright claim, etc.)

All use the same `request_ceo_decision` mechanism.

---

# Part V — Song Production

## §24. Song generation under artist

### Inputs

```python
generation_inputs = {
    "artist": ai_artists.get(artist_id),
    "song_blueprint": song_blueprints.get(blueprint_id),
    "voice_state": artist_voice_state.get(artist_id),
    "policy_constraints": {
        "explicit_allowed": artist.content_rating in ('mild', 'explicit'),
        "max_duration_seconds": 300,
        "min_duration_seconds": 90,
    },
}
```

### Prompt assembly

```
final_prompt =
    artist.voice_dna_summary +
    voice_state_reference_block +    # see §21 two-phase rule
    song_blueprint.smart_prompt_text + # the §12 output
    production_constraints +
    policy_constraints
```

### Provider call

Suno via EvoLink (`POST https://api.evolink.ai/v1/suno/generate`). Returns: audio file URL, lyrics text, generation params, provider job ID.

### Output normalization

Normalize provider response into `audio_assets`:

```sql
INSERT INTO audio_assets (
    asset_id, song_id, provider, provider_job_id, format,
    sample_rate, bitrate, duration_seconds, storage_url,
    checksum, is_master_candidate, created_at
) VALUES (...);
```

Multiple `audio_assets` per song are allowed (regeneration attempts). Best is marked `is_master_candidate = true`.

### Retry policy

If QA (§25) fails, regenerate with same prompt up to 3 attempts. After 3 failures, escalate to CEO (decision_type: `generation_failure`).

### Release assembly is a separate step (deliberate)

Generation writes a `songs_master` row in `draft` status with a `NULL` `release_id`. It does **not** create a `releases` row or a `release_track_record`. That binding happens later in §30 when the user (or the Distribution / Submissions Agent) decides which release a passing-QA song belongs to — a single, an EP cut, part of an album, or a surprise drop.

**Why separate:** one song can live as a post-QA draft for days or weeks before the release strategy is finalized, and the same song might be promoted from "pending" to "lead single" without regeneration. Forcing release creation at generation time bakes a decision that PRD §27's "generate once, transform outward per target service" principle explicitly wants to defer.

The status transitions for a song are:

```
draft          → qa_pending   (orchestrator submits to provider)
qa_pending     → qa_passed    (§25 audio QA succeeds)
qa_pending     → qa_failed    (retry up to 3x, then escalate)
qa_passed      → assigned_to_release  (§30 release assembly binds release_id)
assigned_to_release → submitted       (§28 distribution submission)
submitted      → live         (distributor confirms publication)
live           → archived | taken_down
```

---

## §25.5 Vocal Stem Pipeline (instrumental mixing)

**Purpose.** When the CEO uploads an instrumental and generates a song via Suno's `add-vocals` endpoint, Kie.ai does NOT lock to the uploaded bytes — it analyzes the beat and **recreates** a similar backing track underneath Suno's vocals. The result is "similar but not the same". This pipeline post-processes Suno's output to extract just the vocal layer and mix it onto the user's real instrumental.

**Architecture.** Separate Railway microservice (`services/stem-extractor/`) following the same pattern as `services/tunebat-crawler/` and `services/portal-worker/`. Runs Demucs (Meta's state-of-the-art stem separator) locally via PyTorch CPU wheels. Polls the main API for pending jobs, downloads audio, separates, mixes, posts results back.

**Why a microservice instead of in-process.** Demucs + PyTorch CPU = ~1 GB of dependencies. Keeping the main API container slim (stays ~200 MB) matters for deploy speed + cold-start latency. The microservice isolates the heavy ML path and can be scaled/scheduled independently when demand grows.

**Why not Kie.ai's stems endpoint.** Probed 9 variants (`/api/v1/generate/stems`, `/vocal-separation`, `/vocal-removal`, `/audio-separation`, etc). All return 404. Kie.ai is a thin wrapper — Suno's own stems feature isn't passed through.

### Schema (alembic 024)

```sql
song_stem_jobs (                  -- work queue
    id UUID PK,
    song_id UUID FK → songs_master,
    music_generation_call_id UUID FK → music_generation_calls,
    source_instrumental_id UUID FK → instrumentals,
    source_audio_url TEXT NOT NULL,   -- Suno output MP3 URL
    status TEXT CHECK IN ('pending','in_progress','done','failed'),
    worker_id TEXT, claimed_at, completed_at,
    error_message, retry_count, params_json
)

song_stems (                      -- output artifacts
    id UUID PK,
    song_id UUID FK → songs_master,
    job_id UUID FK → song_stem_jobs,
    stem_type TEXT CHECK IN ('suno_original','vocals_only',
                             'final_mixed','drums','bass','other'),
    content_type VARCHAR(50),
    audio_bytes BYTEA,             -- inline storage
    size_bytes INT, duration_seconds FLOAT, loudness_lufs FLOAT,
    UNIQUE (song_id, stem_type)
)
```

### Worker flow

```
1. Main API: Kie.ai Suno poll returns 'succeeded' for an add-vocals task
2. _enqueue_stem_job_if_needed() detects the uploadUrl in params_json
3. Creates a song_stem_jobs row with status='pending'
4. services/stem-extractor/ claim-next loop picks it up (SELECT FOR UPDATE SKIP LOCKED)
5. Worker downloads:
   - Suno output (source_audio_url) → suno.mp3
   - User's original instrumental (source_instrumental_url) → instrumental.mp3
6. TEMPO-LOCK PRE-PASS (librosa + ffmpeg atempo):
   - librosa.beat.beat_track(suno.mp3) → suno_bpm
   - librosa.beat.beat_track(instrumental.mp3) → instr_bpm
   - ratio = instr_bpm / suno_bpm
   - If |ratio − 1| > 0.001 and ratio ∈ (0.9, 1.1):
       ffmpeg -i suno.mp3 -filter:a atempo=<ratio> → suno_tempoed.mp3
     atempo preserves pitch; ratios outside (0.9, 1.1) are almost
     always half/double-time estimator octave errors → skip.
7. Worker runs Demucs on the tempo-locked track (or raw if tempo
   lock was skipped/failed):
     python -m demucs -n htdemucs --mp3 suno_tempoed.mp3
     → demucs_out/htdemucs/suno_tempoed/{vocals,drums,bass,other}.mp3
8. PHASE-LOCK PRE-MIX PASS (librosa onset cross-correlation):
   - Load first 16 s of instrumental and tempo-locked Suno full mix
   - librosa.onset.onset_strength on both (hop=512)
   - Zero-mean; np.correlate(env_tgt, env_ref, mode='full')
   - Peak → lag_frames → offset_seconds
   - If 0.010 < |offset| < 2.0 s:
       offset > 0 (suno late):  ffmpeg -ss <offset> vocals.mp3 → vocals_phase_locked.mp3
       offset < 0 (suno early): ffmpeg -af adelay=<ms>|<ms>    → vocals_phase_locked.mp3
     Sub-10ms is noise; >2s is probably intro-length mismatch, not phase → skip.
9. Worker runs the final amix:
     ffmpeg -i vocals_phase_locked.mp3 -i instrumental.mp3
       -filter_complex '[0:a]volume=1.25[v];[1:a]volume=1.0[i];[v][i]amix=...'
       → final_mixed.mp3
     (Vocals boosted +25% so they sit on top without fighting the beat.
      Tuning knob in services/stem-extractor/worker.py::_ffmpeg_mix)
10. Base64-encode suno_original (the UNMODIFIED Suno download — the
    tempo-locked intermediate is discarded) + vocals_only + final_mixed
    and POST to /admin/worker/stem-ack/{job_id}
11. API writes one song_stems row per stem, flips job to 'done'
```

### Tempo-lock + phase-lock rationale

Suno's add-vocals mode takes the uploaded instrumental as a *beat reference* but does not atomically lock to it — the generated full mix typically drifts by 0.5–2 % in BPM and 50–300 ms in downbeat phase vs. the source. When Demucs vocals are laid over the original instrumental without correction, the two clocks fight each other and the mix sounds "close but off", especially as the song progresses (drift compounds).

**Why measure BPM on the full Suno mix, not the vocals stem.** Librosa's beat tracker relies on strong onsets (drum hits, bass plucks). Vocals alone — especially held notes — produce weak, ambiguous onsets and BPM estimates that hallucinate half/double-time. The full Suno mix still has Suno's recreated drums + bass, which give a rock-solid BPM reading. So we measure BPM *before* Demucs splits the track, then time-stretch *before* Demucs runs. The vocals stem inherits the locked tempo for free.

**Why pitch-shift is NOT in the pipeline.** Pitch-shifting vocals by more than ~1 semitone produces audible formant warping (chipmunk effect). Suno already uses the user instrumental as a key reference, so key drift is rare in practice. If a future song comes out in the wrong key, fix it at the source (regenerate with a more specific key prompt) rather than shifting post-hoc.

**Why `atempo`, not `rubberband`.** ffmpeg's `rubberband` filter (high-quality time-stretch) requires `--enable-librubberband` at build time, which Debian's stock `ffmpeg` package does not ship. `atempo` is pitch-preserving, built-in, and transparent for the sub-3% corrections we need. Swap to rubberband later if we ever see stretch ratios outside that sweet spot.

**Graceful degradation.** Every step in the pre-pass is wrapped in try/except — any librosa failure, numpy error, or ffmpeg hiccup logs a warning and continues to the next stage using the unmodified audio. A broken tempo lock never blocks a song from reaching `final_mixed`. The `alignment_summary` JSON blob is logged on every job so we can diagnose drift patterns offline.

### Admin endpoints

- `POST /admin/worker/stem-claim-next` — atomic claim, returns song + source URLs + instrumental URL
- `POST /admin/worker/stem-ack/{job_id}` — worker posts back stem payloads (base64)
- `POST /admin/worker/stem-fail/{job_id}` — worker posts failure with retry flag
- `GET /admin/songs/{song_id}/stems` — lists stems + job status for a song
- `GET /admin/songs/{song_id}/stems/{stem_type}.mp3` — streams a single stem

### Performance

CPU-only PyTorch 2.2 on a Railway default container (shared vCPU), `htdemucs` model, ~2–3-minute track. Observed end-to-end on a 132 s Suno output:
- Download (suno + instrumental): ~1 s
- **Tempo-lock pre-pass** (librosa BPM × 2 + atempo stretch): ~8–15 s
- Demucs separation: 90–900 s (varies wildly with container's shared-CPU neighbour noise; ~14 min observed on first production job, ~3 min on a dedicated core)
- **Phase-lock pre-pass** (librosa onset cross-correlation + ffmpeg trim/pad): ~3–5 s
- ffmpeg mix: 2–4 s
- Ack POST (3 base64 stems): ~1 s

**Total per job: ~2–15 minutes** (Demucs dominates — lock passes add <20 s combined).

The model weights are pre-downloaded at Docker build time (~500 MB) so the first job after a cold start doesn't pay the download cost. Librosa's numba JIT pays a one-time ~5–10 s compile cost on the first `beat_track` call after boot, then is hot forever.

### Storage footprint per song

Each `song_stems` row carries a BYTEA blob inline:
- `suno_original`: ~2-4 MB
- `vocals_only`: ~1-2 MB
- `final_mixed`: ~2-4 MB
- Optional `drums` / `bass` / `other` when `STEM_STORE_EXTRAS=1`: +3 × ~2 MB

Baseline: ~6-10 MB per song. With extras: ~12-16 MB. For a 1000-song catalog that's ~10-15 GB — Neon handles it.

### UI integration

`/songs` page detail panel includes a `StemAwareAudioPlayer` component. Default playback = `final_mixed` if available, else falls back to the master `audio_assets` URL. Toggle strip below the player lets the CEO A/B between mixed / vocals / suno / drums / bass / other. Active stem highlighted in violet, inactive muted. Job-state banner reports "extraction queued" / "demucs separating" / "failed" with live refetch while in progress.

### Required env vars on the Railway service

| Var | Purpose |
|---|---|
| `SOUNDPULSE_API` | Base URL of the main API |
| `API_ADMIN_KEY` | `X-API-Key` with admin privilege |
| `WORKER_ID` | Stable identifier (default hostname) |
| `POLL_INTERVAL_SEC` | Sleep between empty polls (default 30) |
| `DEMUCS_MODEL` | Model name (default `htdemucs`) |
| `STEM_STORE_EXTRAS` | Set `1` to also store drums/bass/other stems |

### Known limitations + future work

- **Structural drift beyond the 16 s phase window.** Phase-lock uses the first 16 s of audio to find a single offset. If Suno's output has a longer intro, adds a bar somewhere in the middle, or resolves a section boundary differently, we lose sync later in the song even though the head is locked. Next step if this bites: multi-window DTW (dynamic time warping) that stretches non-linearly across the full duration — doable but ~10× the CPU cost of the current pre-pass.
- **Key (pitch) mismatch is not corrected.** We deliberately don't pitch-shift vocals — formant warping sounds worse than the occasional semitone drift. If Suno comes back in the wrong key, regenerate rather than post-process.
- **BPM estimator can pick half/double-time.** Librosa's beat tracker occasionally returns 160 BPM on a 80 BPM track (or vice versa). Guarded by the `0.9 < ratio < 1.1` clamp — outside that band we skip the stretch entirely. Fallback path is the raw-Suno mix, which is still ≥ the pre-pipeline baseline.
- **Demucs CPU latency.** 3–15 min per job on Railway's shared CPU is acceptable for our volume (~dozens/day) but becomes a bottleneck if the catalog grows past hundreds/day. Upgrade path: GPU Railway service or swap in a lighter model (`htdemucs_ft`, `mdx_extra_q`).
- **Extras storage disabled by default.** Setting `STEM_STORE_EXTRAS=1` doubles storage; leave off unless we need drums/bass for a remix flow or stem submission.
- **No per-stem loudness normalization yet.** `loudness_lufs` column exists but the worker doesn't populate it — follow-up can run librosa RMS at ack time.
- **Alignment telemetry only in logs.** The `alignment_summary` JSON (BPMs, ratio, phase offset, locked flags) lives only in worker stdout for now. A `song_stem_jobs.alignment_json` column would surface it in the Songs UI — trivial migration whenever we want it.

---

## §25. Audio QA

Before any audio is accepted, run QA checks. Result row written to `song_qa_reports`.

### Required checks

| Check | Threshold | Action on fail |
|---|---|---|
| Duration | 90-300 seconds | Regenerate |
| Tempo match (vs blueprint) | ±10% | Regenerate |
| Key match | exact or ±1 semitone | Regenerate |
| Energy match | ±0.15 | Regenerate |
| Silence | <5% total non-silent audio | Regenerate |
| Clipping | <0.5% peak clipping | Regenerate |
| Loudness normalization | -14 LUFS (Spotify target) ±1 | Auto-normalize, no regen |
| Lyric intelligibility | >0.6 (heuristic) | Regenerate |
| Vocal prominence | mid-range RMS shows vocal layer | Regenerate |
| Duplication risk vs catalog | <0.85 cosine similarity to any existing song's audio embedding | Regenerate (NEVER ship near-duplicates) |

The QA service uses **Essentia + Librosa** for DSP. **No reliance on Spotify's `/v1/audio-features`** — that endpoint is dead for our app.

### Schema

```sql
song_qa_reports (
    qa_report_id, song_id, asset_id,
    tempo_match_score, key_match_score, energy_match_score,
    silence_score, clipping_score, duplication_risk_score,
    pass_fail BOOLEAN, report_json JSONB, created_at
)
```

---

## §26. Lyrics

### Approach

**A. Suno generates from prompt (DEFAULT).** The smart prompt includes a LYRICS section with structural guidance and theme directives. Suno produces lyrics inline with the audio. Faster, cheaper, tightly coupled to the audio.

**B. Pre-generate via Groq llama-3.3-70b, feed to Suno.** Higher control. Used when CEO approves a specific lyric direction or for special releases.

### Storage

Generated lyrics text is stored on `songs_master.lyric_text`. Lyric features (themes, structure, snippet candidates for TikTok) are stored on `songs_master` and in `track_lyrics` for cross-genre analysis.

### Genius cross-reference

Once the song is distributed and indexed by Genius (typically 7-14 days post-release), the `genius_lyrics` scraper picks it up automatically and links the `track_lyrics` row via spotify_id or ISRC. This enriches the song with the same fields used for breakout track analysis (themes, vocab richness, section structure).

### Rights consideration

ASCAP/BMI registration does NOT require lyrics text — only writer/publisher/composer credits. Lyrics are treated as a brand+marketing asset, not a registration requirement. Label (SoundPulse Records LLC) owns the lyric copyright.

---

## §27. Metadata strategy

**Principle:** Generate metadata ONCE into a canonical master record (`songs_master`), then transform outward per target service (DSP delivery, PRO registration, sync marketplace, social pitch).

### Sources

| Source | What it provides |
|---|---|
| Artist (`ai_artists`) | display name, primary genre, copyright lines |
| Blueprint (`song_blueprints`) | target features, themes, reference descriptors |
| Audio analysis (Essentia/Librosa post-generation) | actual tempo, key, energy, loudness LUFS, danceability |
| Lyrics analysis | language, themes, snippet candidates, vocabulary tags |
| Distribution requirements | UPC, ISRC, territory rights, release date |
| Rights system | writers, publishers, splits, copyright |
| Marketing | hooks, pitches, playlist fit tags, SEO keywords |

### `songs_master` — full canonical schema

(See §17 — defined verbatim from marketing spec §10. ~95 fields covering identity, classification, audio analysis, vocals, lyrics, rights, distribution, release planning, artwork, marketing, generation metadata, QA, ML predictions, and actuals.)

### Audio enrichment stack

| Tool | Use |
|---|---|
| **Essentia** | Core DSP, music descriptors |
| **Librosa** | Additional audio analysis |
| **Demucs** | Source separation if needed |
| **Custom classifier heads** | Mood, instrumentation, vocal type |
| **LLM** | Lyric theme summarization ONLY (not DSP) |

**Critical:** Spotify's `/v1/audio-features` is NOT the path for any new analysis. It's dead for our app.

---

# Part VI — Distribution & Submissions

The **Submissions Agent (#14)** orchestrates everything in this part. See §43.N.

## §28. Submission classes

| Class | Description | Examples | Tools |
|---|---|---|---|
| **A** API-native | Programmatic REST/JSON, automatable end-to-end | LabelGrid, Revelator, SonoSuite, MLC DDEX, YouTube Data API | Direct HTTP |
| **B** Portal/browser | Web-only, requires login + form fill | ASCAP, BMI, SoundExchange, some sync platforms | BlackTip stealth browser via Fonzworth (or similar service per lane) |
| **C** Partner-gated | Requires label/MCN/publisher partnership status | YouTube Content ID, Beatport label tier | BLOCKED until partnership; manual fallback |

Every submission is recorded in `song_submissions` regardless of class (see §17).

---

## §29. Submission ordering and dependencies

**Core rule:** Submissions are NOT fully parallel. The distributor is the canonical source for `release_id`, `track_id`, UPC/EAN, and ISRC. Downstream lanes need these identifiers, so sequencing matters.

### 7-phase sequence

```
Phase 0 — Internal preflight
  Generate and validate all internal metadata before any external submission.
  Output: canonical songs_master row, ai_artists row, credits, splits,
          audio asset selected, artwork asset selected.

Phase 1 — DSP distributor submission
  Submit to LabelGrid (or Revelator if LG fails).
  Purpose: validate release package, create release in distributor,
           receive UPC/EAN, ISRC(s), distributor release id, DSP routing ids.

Phase 2 — Identifier ingestion
  Immediately GET/poll distributor and persist:
    - UPC, ISRC, release external id, per-track external id, validation status

Phase 3 — Rights registration (uses refreshed DB record)
  - PRO registration agent (Fonzworth ASCAP, BMI portal)
  - Mechanical lane (MLC DDEX)
  - SoundExchange / neighboring rights lane
  - Internal royalty graph

Phase 4 — UGC monetization
  - YouTube Content ID (where partner status exists, otherwise SKIP with note)
  - Platform UGC rights policies

Phase 5 — Sync licensing
  - Sync marketplace / licensing partner submission
  - ONLY after metadata, rights ownership, and clean artwork are final

Phase 6 — Profile / discovery optimization
  - Claim artist profiles on DSPs
  - Update bios/images
  - Connect pre-save / profile links
  - Push lyric assets
```

### Dependency graph

```
song + artist finalized
  → release package compiled
    → distributor submission (Phase 1)
      → distributor returns identifiers (Phase 2)
        → PRO registration (Phase 3)
        → mechanical registration (Phase 3)
        → SoundExchange registration (Phase 3)
        → YouTube Content ID (Phase 4 — if partnered)
        → sync licensing submission (Phase 5)
```

### Hard rules

1. Cannot submit downstream rights lanes until writer/publisher splits are FINAL (no `pending` values)
2. Cannot submit to sync marketplace if `ownership/control` fields are incomplete
3. Cannot submit to Content ID until ownership policy is confirmed
4. Every submission is logged to `song_submissions` (per non-negotiable rule §58.5)

---

## §30. Distribution provider strategy

**Validated against the API reality (see §55 for the full validation table). Most "music distributor APIs" don't actually exist as public REST.**

### Real options

| Provider | Status | Pricing | Notes |
|---|---|---|---|
| **LabelGrid** | TODO (MVP-1 priority) | $1,428/yr starter | REST API, sandbox available |
| **Revelator** | TODO (alternative) | Enterprise contract | Full white-label SaaS |
| **SonoSuite** | TODO (alternative) | Enterprise | Documented REST |

### NOT viable (despite often-claimed)

| Provider | Reality |
|---|---|
| **DistroKid** | No public API. UI only. |
| **TuneCore** | No public API. Enterprise-partnership only. |
| **CD Baby** | Legacy XML feed deprecated 2018. Dead. |
| **Amuse / UnitedMasters / RouteNote / LANDR** | No public APIs |

### Provider abstraction (Class A interface)

```typescript
interface DistributionProvider {
  create_release(release: ReleasePackage): Promise<DistributorReleaseId>;
  upload_audio(release_id: string, asset: AudioAsset): Promise<void>;
  upload_artwork(release_id: string, artwork: ArtworkAsset): Promise<void>;
  validate_release(release_id: string): Promise<ValidationResult>;
  submit_distribution(release_id: string): Promise<SubmissionStatus>;
  get_release(release_id: string): Promise<ReleaseDetail>;
  list_track_identifiers(release_id: string): Promise<TrackIdentifier[]>;  // UPC, ISRC
}
```

LabelGrid implementation is **MVP-1 priority** per the marketing spec. Revelator is the fallback.

---

## §31. ASCAP service — Fonzworth

ASCAP has no public API. Browser-only registration. **Solved by the Fonzworth service** at `C:\Users\edang\myApps_v2\fonzworth\` (sibling repo).

### Architecture

Two-process Node.js/TypeScript service:

```
REST API (Fastify)              Worker (Node.js)
┌──────────────────┐           ┌──────────────────────┐
│ POST /submissions │──────────▶│ Poll DB for pending  │
│ GET  /submissions │           │ Import BlackTip       │
│ GET  /health      │           │ Login → Fill → Submit │
└────────┬─────────┘           └──────────┬───────────┘
         │                                │
         ▼                                ▼
   PostgreSQL (Neon)                BlackTip
   - submissions                    - stealth Chrome
   - submission_logs                - human-calibrated timing
   - llm_calls                      - anti-detection
   - sessions                       - imported directly (not TCP)
```

### Tech stack

| Concern | Choice |
|---|---|
| Runtime | Node.js 22+, TypeScript |
| API | Fastify |
| ORM | Drizzle |
| DB | PostgreSQL (Neon, separate branch from soundPulse) |
| Job queue | Postgres polling (`SELECT FOR UPDATE SKIP LOCKED`) |
| Tests | Vitest |
| Validation | Zod |
| Logging | Pino |
| Browser | BlackTip (direct import from local path) |
| LLM (error recovery only) | Anthropic SDK + Claude Vision |

### Submission flow (`ascap-submitter.ts`)

```
1. Check session validity → re-login if expired
2. Navigate to "Register a Work"
3. Fill song title
4. For each writer: add writer, fill name/IPI/split/role
5. For each publisher: add publisher, fill name/IPI/split
6. Screenshot before submit
7. Click submit
8. Wait for confirmation
9. Screenshot after submit
10. Log success + confirmation number
```

**No LLM on the happy path** — ASCAP forms are deterministic. LLM is used ONLY for error recovery: screenshot the failure, ask Claude Vision what went wrong, attempt recovery.

### Rate limiting

| Limit | Value |
|---|---|
| Inter-submission delay | random 60-180 seconds |
| Daily window | business hours 9AM-5PM ET |
| Session breaks | 5-15 min pause every 8-10 submissions |
| Daily cap | 30 submissions (configurable) |
| Browser restart | every 15 submissions (memory hygiene) |

### Schema

```sql
submissions          -- job queue: id, status, song_title, writers JSONB,
                     -- publishers JSONB, metadata JSONB, attempt_count,
                     -- error_message, screenshot_path, batch_id, timestamps
submission_logs      -- audit trail: event_type, details JSONB, screenshot
llm_calls            -- model, tokens, cost (per CLAUDE.md mandate)
sessions             -- ASCAP cookie persistence
```

### Phased delivery

| Phase | Deliverables |
|---|---|
| **1 Foundation** | Scaffold, DB schema, API routes (POST/GET /submissions, /health), validation tests |
| **2 Core** | ASCAP login + form submission, session manager, screenshots, worker loop |
| **3 Hardening** | Rate limiter, batch submission, retry logic, LLM error recovery, llm_calls logging |
| **4 Ops** | Dashboard endpoints, alerting, screenshot rotation, API docs |

### Risks

| Risk | Mitigation |
|---|---|
| ASCAP changes form selectors | LLM error recovery detects change → alert → manual selector update |
| Rate limiting / account block | Conservative pacing, business hours only, BlackTip stealth |
| Browser memory leaks | Restart every 15 submissions |
| ASCAP adds CAPTCHA | BlackTip stealth bypasses simple ones; advanced ones require CAPTCHA service |

**Integration with SoundPulse:** The Submissions Agent (#14) calls Fonzworth's REST API (`POST /submissions` with the ASCAP work registration payload). Fonzworth runs its worker independently and writes back to a SoundPulse-readable webhook (`POST /api/v1/admin/submissions/ascap-callback`) when complete.

---

## §32. BMI portal automation

Same architecture pattern as Fonzworth ASCAP, separate service or module:
- Browser automation via BlackTip
- BMI publisher portal login
- Work registration form fill
- Confirmation capture
- Same rate limits as ASCAP

**Status:** TODO. Same structure as Fonzworth makes this a 2-3 day port.

---

## §33. MLC DDEX

The Mechanical Licensing Collective accepts bulk DDEX-formatted files via SFTP for member publishers.

### Path

1. Generate DDEX-compliant XML for the work
2. Upload to MLC SFTP endpoint with member credentials (`MLC_MEMBER_ID`, `MLC_SFTP_KEY`)
3. Poll for acceptance/rejection
4. Update `royalty_registrations` row

### Tools needed

- DDEX schema validation library (Python `lxml` or similar)
- SFTP client (`paramiko`)

### Status

TODO. Requires MLC membership (free for publishers but requires registration). Worth the effort because it's the ONLY rights lane that has a real programmatic path.

---

## §34. SoundExchange

Portal-only registration. Same pattern as ASCAP/BMI: browser automation via BlackTip.

**Optional:** Email `techsupport@soundexchange.com` to inquire about API access. They've been known to grant programmatic submission to repertoire systems for label-tier accounts.

Status: TODO.

---

## §35. YouTube Content ID

**BLOCKED for direct API access.** Content ID requires YouTube Partner Program / Multi-Channel Network status, which we don't have.

### Workaround

1. **Phase 4a (no partnership):** Upload songs to artist's official YouTube channel via YouTube Data API v3 (this works without partnership). Cover art + audio = "art track." Manual content claim if UGC infringement detected.
2. **Phase 4b (partnership achieved):** Once we have a label-tier partnership (MCN affiliation or direct label deal), wire up Content ID asset ingestion.

The Submissions Agent currently SKIPS Phase 4 (Content ID) and logs a `needs_partnership` status.

---

## §36. Sync marketplaces

Sync = song licensing for film/TV/ads. Highest per-placement value, hardest to automate.

### Reality

| Marketplace | API status |
|---|---|
| Songtradr | No public API. Submission via account UI. |
| Musicbed | No public API. |
| Marmoset | No public API. |
| Pond5 | API for stock content, not sync placements |

### Approach

Browser automation via BlackTip per marketplace. Lower priority than core distribution + PROs.

Status: TODO (Phase MVP-3 per marketing spec).

---

# Part VII — Rights & Royalties

## §37. PRO lane

Performance Rights Organizations register the **composition** (not the recording).

| Org | Path | Status |
|---|---|---|
| **ASCAP** | Fonzworth browser service (§31) | TODO |
| **BMI** | Same pattern, separate service (§32) | TODO |
| **SESAC** | Invitation-only PRO. We don't qualify. Skip. | n/a |

Default: register every song with ASCAP (US). Optionally with BMI if publisher structure differs.

### Required payload

```json
{
  "title": "Midnight Drive",
  "alt_titles": ["Midnight Drive (Original)"],
  "writers": [
    {"name": "Eduardo D'Angelo", "ipi": "00123456789", "split": 100, "role": "writer/composer"}
  ],
  "publishers": [
    {"name": "SoundPulse Records LLC", "ipi": "00987654321", "split": 100}
  ],
  "iswc": null,                 // assigned later by PRO
  "isrc": "USRC12500001",       // from distributor
  "duration": 195,
  "performance_date": "2026-05-01"
}
```

**ISWC** is assigned by the PRO upon successful registration. It's captured back into `royalty_registrations.external_id` and pushed onto `songs_master.iswc`.

### Setup costs

- Publisher registration ($50 one-time)
- IPI number application
- TuneRegistry ($95/mo) — optional alternative if Fonzworth isn't ready

---

## §38. Mechanical lane

Pays the songwriter for reproductions (downloads, mechanical streams).

### Path

**The MLC** (US) — DDEX-based bulk submission per §33. Free for members.

For non-US territories: HFA (Harry Fox Agency) and per-country mechanical organizations. Lower priority. TODO.

---

## §39. Neighboring rights lane

Pays the **performer** for terrestrial radio + non-interactive streaming.

### Path

**SoundExchange** — register the recording per §34. Browser automation.

Some neighboring rights organizations in EU territories (PPL UK, GVL Germany) offer separate registration. TODO Phase MVP-3.

---

## §40. UGC monetization lane

YouTube Content ID per §35. **BLOCKED until label partnership.**

Other UGC sources:
- Facebook Rights Manager — requires partnership
- TikTok CMS — partnership tier
- Instagram Music Library — partnership tier

**Workaround:** Manual claim/dispute flow when UGC infringement is detected.

---

## §41. Sync lane

Per §36. Browser automation per marketplace. TODO Phase MVP-3.

---

# Part VIII — Marketing System

## §42. Marketing phases M0–M5

Marketing is **phase-based and metric-gated**, not "do everything at once."

### Phase M0 — Asset readiness

Do not start marketing until ALL of:
- Song distributed / release date known
- Artist identity finalized
- 8-view reference sheet exists
- Short-form content assets ready (15 short clips, 5 photos)
- TikTok hook timestamps selected
- Metadata complete in `songs_master`
- Landing links ready (smart link, pre-save link)

### Phase M1 — Existence / identity seeding

**Goal:** Establish artist surface area. Build profile legitimacy.

**Activities:**
- Create artist bio + profile assets across TikTok, IG, YouTube Shorts
- 1-2 posts/day on TikTok, IG Reels, YouTube Shorts
- Daily "artist moment" videos (lifestyle content)
- 2 static image posts/week
- 1 lore/backstory post/week
- Smart link in bio + pre-save

**Gate to M2** (must hit ALL):
- ≥10 posts published
- Median watch-through on short-form ≥15%
- ≥100 combined followers OR ≥1,000 total organic views

### Phase M2 — Song anchoring

**Goal:** Connect artist identity to specific song.

**Activities:**
- Post chorus/hook clips repeatedly in varied formats
- Lyric overlay versions
- Mood visualizer clips
- "Studio/creation" fake BTS clips
- Comment farming / audience reply videos
- Launch micro-playlist pitching to indie curators (Playlist Outreach Agent)

**Gate to M3** (must hit ONE of):
- ≥5,000 cumulative short-form views on song clips
- ≥1,000 pre-saves / platform equivalents
- ≥3 independent playlist adds
- ≥500 streams in first 7 days

### Phase M3 — Early distribution amplification

**Goal:** Test paid + influencer + playlist surfaces.

**Activities:**
- Micro-influencer seeding (Influencer Seeding Agent)
- Small paid spend on best-performing organic clip ($100-500 cap)
- Playlist outreach expansion
- Creator usage seeding with sound snippet
- Daily post cadence maintained

**Gate to M4** (must hit ONE of):
- ≥25,000 clip views on best asset
- ≥20 creator videos using sound
- ≥5,000 streams in 30 days
- ≥15 playlist adds

### Phase M4 — Breakout acceleration

**Goal:** Concentrate budget and agent effort where signal exists.

**Activities:**
- Double posting on winning platforms
- Paid amplification only on best-converting creatives
- Push UGC prompts (UGC Trigger Agent)
- Coordinated creator seeding
- Editorial pitch refresh (Editorial/PR Agent activates)
- Profile optimization and artist narrative expansion

**Gate to M5** (must hit ONE of):
- ≥100,000 video views
- ≥50 creator uses
- ≥25,000 streams/month
- Platform algorithmic playlist pickup

### Phase M5 — Catalog compounding

**Goal:** Use song success to grow artist brand and next release.

**Activities:**
- Follow-up single planning (feeds back into §10 breakout engine)
- Retain audience with non-song content
- Cross-promote prior catalog
- Collect community signals
- Feed learnings into next song blueprint via the Analytics Agent

---

## §43. Marketing agent catalog (14 agents)

All 14 agents are seeded in `agent_registry`. Default tool grants are seeded in `agent_tool_grants`. The Settings UI (§50) shows the live state and allows grant modifications.

### A. Artist Identity Agent
- **Purpose:** Maintain coherent artist brand across platforms
- **Tools:** groq (LLM), flux_falai, stable_diffusion, instagram_graph, facebook_graph
- **Actions:** Write bios, choose images, update social profiles, maintain canon

### B. Content Strategy Agent
- **Purpose:** Decide what content gets made this week/day
- **Tools:** groq, chartmetric (trend feeds)
- **Actions:** Daily content brief, prioritize hooks, assign content jobs

### C. Video Generation Agent
- **Purpose:** Produce short-form videos and visualizers
- **Tools:** veo, flux_falai, stable_diffusion (for static frames)
- **Actions:** Render clips, produce variants, export platform-specific formats

### D. Copy / Caption Agent
- **Purpose:** Write captions, hooks, CTAs, replies
- **Tools:** groq
- **Actions:** Captions, hashtags, hook overlays, response templates

### E. Social Posting Agent
- **Purpose:** Publish, schedule, and manage posts
- **Tools:** tiktok_content_posting, instagram_graph, facebook_graph, youtube_data_api, x_twitter_api, blacktip (for portal-only platforms)
- **Actions:** Post, schedule, retry failures, collect post IDs

### F. Community Agent
- **Purpose:** Respond to comments; create illusion of active artist
- **Tools:** groq, instagram_graph, tiktok_content_posting
- **Actions:** Reply to comments, pin comments, suggest follow-up videos

### G. Playlist Outreach Agent
- **Purpose:** Pitch to independent curators
- **Tools:** submithub, groover, email_smtp, blacktip
- **Actions:** Find playlists, send pitches, log responses

### H. Micro-Influencer Seeding Agent
- **Purpose:** Get small creators to use the sound
- **Tools:** email_smtp, instagram_graph, tiktok_content_posting
- **Actions:** Shortlist creators, send briefs, track adoption

### I. UGC Trigger Agent
- **Purpose:** Increase use of track sound in creator content
- **Tools:** tiktok_content_posting, groq
- **Actions:** Create UGC prompts, generate creator briefs

### J. Paid Growth Agent
- **Purpose:** Amplify only proven creatives
- **Tools:** meta_ads, linkfire, feature_fm
- **Actions:** Launch ads, rotate creatives, report ROAS / stream lift

### K. Analytics Agent
- **Purpose:** Central performance brain
- **Tools:** chartmetric, songstats, spotify_web_api, youtube_data_api
- **Actions:** Compute KPIs, emit alerts, trigger phase transitions

### L. Editorial / PR Agent
- **Purpose:** Pitch higher-trust outlets
- **Tools:** groq, email_smtp
- **Actions:** Write press notes, send pitches, follow up

### M. CEO Action Agent
- **Purpose:** Escalate to CEO for approvals
- **Tools:** email_smtp, telegram_bot, slack_webhook
- **Actions:** Send decision packet, pause workflow, record response

### N. Submissions Agent (NEW)
- **Purpose:** Orchestrate all song submissions across DSP, PRO, mechanical, neighboring, UGC, sync
- **Tools:** labelgrid, revelator, sonosuite, fonzworth_ascap, bmi_portal, mlc_ddex, soundexchange, youtube_cms, blacktip, anthropic, email_smtp
- **Actions:** Create release in distributor, poll for identifiers, submit to PROs, submit mechanicals, submit neighboring rights, register UGC, log every submission to song_submissions, escalate to CEO Action Agent on failure
- **Dependencies:** Honors §29 ordering (DSP first, then identifier ingestion, then rights lanes)

### Resolved vagueness

- **"Visual Asset Agent"** referenced in source but not defined → folded into Artist Identity Agent (A) which already manages visual assets
- **"Brand Pivot Agent"** referenced in source but not defined → not a separate agent. Brand pivots are handled by the Content Strategy Agent (B) escalating to the CEO Action Agent (M) when metric trends warrant it

---

## §44. Metrics + triggers

### Core metrics tracked

| Metric | Source | Used by |
|---|---|---|
| Follower count per platform | Platform APIs | Phase gates |
| Post volume | `social_posts` | Content Strategy Agent |
| Views per clip | `social_posts.views` | Content Strategy Agent, Phase gates |
| Avg watch-through % | Platform analytics | M1 gate |
| Saves / shares | `social_posts` | Content Strategy Agent |
| Sound uses / creator uses | Platform analytics | UGC Trigger Agent |
| Pre-saves | Smart link analytics | M2 gate |
| Streams 1d / 7d / 30d | Distribution analytics | M2/M3/M4 gates |
| Playlist adds | Songstats | M2/M3/M4 gates |
| Content view → stream conversion | Cross-source attribution | Paid Growth Agent |
| Paid CAC per stream / follower | Meta Ads + analytics | Paid Growth Agent kill switch |

### Trigger examples

- median watch-through <10% over last 10 clips → **refresh content format**
- one clip >3× median views → **create 5 derivatives**
- 3 playlists add → **expand outreach universe**
- 20 creator uses in 7 days → **activate UGC Trigger Agent**
- paid CAC exceeds threshold for 3 days → **pause paid**
- follower threshold hit but song underperforms → **shift to artist-brand building**

---

## §45. 0→3K streams playbook

Realistic 30-day launch playbook (~$500/song):

| Week | Activity | Cost |
|---|---|---|
| -2 | Hypeddit pre-save link | Free |
| -1 | Pre-save promotion via Meta ads | $40 |
| 1 | Playlist Push curator campaign | $300 |
| 1 | Meta Ads stream targeting | $100 |
| 1-2 | SubmitHub blog/playlist credits | $40 |
| 2-3 | Groover curator pitches | $55 |

Expected outcome: ~3,000-6,000 streams in first 30 days for Suno-grade songs that pass AI music detection.

### Tier breakdown

| Tier | Channels | ROI |
|---|---|---|
| **Tier 1 (high ROI)** | Playlist Push (25 streams/$), Meta Ads ($0.15-0.40/stream), Hypeddit (free), short-form video | Best per-$ |
| **Tier 2** | SubmitHub ($8-12/placement, 60-200 streams), Groover ($2.18/curator, 10-21% acceptance), TikTok sound seeding | Mid |
| **Tier 3** | Reddit, Discord (5-50 streams/post), blog coverage (50-500 streams) | Low / brand |

### AI detection warning

**SubmitHub uses 98.5%-accurate AI music detection.** Suno tracks WILL be flagged. Mitigation:
- Use Udio's style-transfer capability where possible (less detectable)
- Mix in real instrumentation (live overdubs) where budget allows
- Avoid mass submission to AI-skeptical curators

### Spotify algorithmic thresholds

- Discover Weekly: ~2,500 streams + 375 saves in 2 weeks
- Autoplay/Radio: >50% listen-through
- Release Radar: 30+ followers
- Day-1 boost: 100+ pre-saves

---

# Part IX — Revenue & Analytics

## §46. Revenue tracking

`revenue_events` table (§17). Every payout from every source becomes a row.

### Sources

| Source | Royalty type | Frequency |
|---|---|---|
| Distributor (LabelGrid) → DSPs | streaming | Monthly |
| MLC | mechanical | Quarterly |
| ASCAP | performance | Quarterly |
| BMI | performance | Quarterly |
| SoundExchange | digital_performance | Quarterly |
| YouTube Content ID | content_id | Monthly |
| Sync marketplace | sync | Per placement |

All revenue → SoundPulse Records LLC bank account (single point of collection).

### Reconciliation

Daily cron pulls reports from each source's API/CSV export, normalizes to `revenue_events`. The Analytics Agent (K) computes per-song and per-artist totals + ROI.

---

## §47. Reconciliation

Each source has its own reporting cycle and currency. Reconciliation rules:

| Step | Rule |
|---|---|
| Currency normalization | Convert all to USD at the date-of-payment exchange rate |
| Stream count vs revenue | Cross-check `stream_count` × estimated rate ≈ `revenue_cents` (within ±20% tolerance) |
| Discrepancy alert | If any month's total deviates >30% from smoothed trend → escalate to CEO |
| Per-song ledger | Sum `revenue_events` per song, attribute to artist, attribute to release |
| Tax categorization | Streaming/mechanical/sync/sync sublabels for tax filing |

---

# Part X — Platform & Infrastructure

## §48. AI Assistant

**BUILT.** Hideable panel in the dashboard (`Cmd/Ctrl+.` shortcut, persisted in localStorage `soundpulse.assistant.visible`).

Backend: `api/services/assistant_service.py` calls Groq llama-3.3-70b via `llm_client.py` with action `assistant_chat`. Pulls live DB context (track count, recent breakouts, opportunity scores) before each call.

---

## §49. CEO Profile + CEO Action Agent

### CEO Profile

Single-row `ceo_profile` table (§17) with:
- name, email, phone, telegram_handle, telegram_chat_id, slack_channel
- preferred_channel (`email|phone|telegram|slack`)
- escalation_severity_threshold (`low|medium|high|critical`)
- quiet_hours_start, quiet_hours_end, timezone

Edited via Settings UI (§50). Source-of-truth for any agent that needs to escalate.

### CEO Action Agent (M)

When any agent needs CEO approval:

```python
async def request_ceo_decision(decision):
    profile = load_ceo_profile()
    if in_quiet_hours(profile):
        if decision.severity not in ('critical',):
            queue_for_morning(decision)
            return

    if profile.preferred_channel == 'telegram':
        send_telegram(profile.telegram_chat_id, format(decision))
    elif profile.preferred_channel == 'email':
        send_email(profile.email, format(decision))
    # ... etc

    persist_to_ceo_decisions(decision)
    block_calling_workflow()
```

Response received → write `response_payload` to `ceo_decisions` row → unblock the workflow.

---

## §50. Settings UI — Tools & Agents registry (BUILT)

`/settings` page in the dashboard. Two sections:

### CEO Profile section
Form for editing the `ceo_profile` row.

### Tools & Agents section

Two views (toggleable):

**By tool view** — for each tool in `tools_registry`:
- Name, category, status badge, automation class (A/B/C)
- Required env vars + credential-presence indicator (green ✓ or red ⚠ with missing vars listed)
- List of agents granted access to it (pills)
- Inline grant: "+ grant" button → dropdown of unassigned agents
- Inline revoke: hover any pill → × button

**By agent view** — for each agent in `agent_registry`:
- Code letter, name, purpose
- List of tools the agent is granted access to (pills)
- Same inline grant/revoke

### Schemas

- `agent_registry` — 14 agents seeded
- `tools_registry` — 41 tools seeded (covering all data, LLMs, generation, visual, video, distribution, rights, social, marketing, communication categories; openai_cli_proxy routes all image gen through gpt-image-1 — DALL-E 3 removed as of 2026-04-13 for insufficient realism)
- `agent_tool_grants` — many-to-many, 51 default grants seeded

### Endpoints

```
GET    /api/v1/admin/agents
GET    /api/v1/admin/tools                            (with credentials_configured check)
GET    /api/v1/admin/agent-tool-grants?pivot=by_tool|by_agent
POST   /api/v1/admin/agent-tool-grants                {agent_id, tool_id, scope?}
DELETE /api/v1/admin/agent-tool-grants?agent_id=X&tool_id=Y
GET    /api/v1/admin/ceo-profile
PUT    /api/v1/admin/ceo-profile
```

---

## §51. SongLab UI (BUILT)

`/song-lab` page. Loads top 10 breakout opportunities on mount via `GET /blueprint/top-opportunities?n=10&model=suno`.

Each card shows:
- Rank #, genre name, opportunity score (0-100)
- Confidence + momentum badges
- Stats strip: composite_ratio, velocity_ratio, breakout_rate, surfaced_at
- Quantification block: $ revenue (low/median/high), stream estimates per platform, TikTok exposure
- Expanded view: rationale (sonic/lyrical/edge), full prompt, "Copy to clipboard"
- Model picker (Suno/Udio/SOUNDRAW/MusicGen) — switching re-runs in parallel
- Sort options: opportunity / revenue / confidence

Refresh button + 5-min cache so LLM tokens aren't burned on every reload.

---

## §52. API Reference

All routes are prefixed `/api/v1/` unless noted. Authentication via `X-API-Key` header.

### Public — Query
```
GET  /trending?entity_type=track&limit=50
GET  /search?q=...
GET  /predictions?entity_id=X
```

### Public — Genres + Blueprints
```
GET  /blueprint/genres
POST /blueprint/generate                     (legacy v1, deterministic Python)
POST /blueprint/generate-v2                  (smart prompt v2, LLM-powered)
GET  /blueprint/top-opportunities?n=10&model=suno&sort_by=opportunity|revenue|confidence
```

### Public — Assistant
```
POST /assistant/chat
```

### Public — Backtesting + Predictions
```
POST /backtesting/run
GET  /backtesting/results
GET  /backtesting/runs
GET  /backtesting/genres
```

### Admin — Scrapers
```
GET    /admin/scraper-config
PATCH  /admin/scraper-config/{id}
POST   /admin/scraper-config/{id}/run-now
```

### Admin — Sweeps
```
GET  /admin/sweeps/status
POST /admin/sweeps/classification
POST /admin/sweeps/composite
POST /admin/sweeps/breakout-detection
POST /admin/sweeps/breakout-detection/backfill?weeks_back=78&step_days=7
POST /admin/sweeps/feature-delta-analysis
POST /admin/sweeps/lyrical-analysis?only_genre=X
```

### Admin — Breakout views
```
GET /admin/breakouts?genre=X&limit=50
GET /admin/feature-deltas?genre=X
GET /admin/lyrical-analyses?genre=X
GET /admin/gap-finder?genre=X&n_clusters=N
```

### Admin — Lyrics + audio features
```
GET  /admin/tracks/needing-audio-features
GET  /admin/tracks/needing-audio-features-cm
GET  /admin/tracks/needing-lyrics
POST /admin/lyrics/bulk
```

### Admin — Diagnostics
```
GET  /admin/db-stats
GET  /admin/db-stats/history?days=90
GET  /admin/db-stats/hydration
GET  /admin/db-stats/hydration/history
GET  /admin/chartmetric/probe?cm_track_id=X
GET  /admin/chartmetric/probe-sub-endpoints?cm_track_id=X
GET  /admin/spotify/cooldown
POST /admin/spotify/cooldown/clear
GET  /admin/llm-usage?days=30
GET  /admin/version
```

### Admin — Settings (CEO + Agents/Tools)
```
GET    /admin/ceo-profile
PUT    /admin/ceo-profile
GET    /admin/agents
GET    /admin/tools
GET    /admin/agent-tool-grants?pivot=by_tool|by_agent
POST   /admin/agent-tool-grants
DELETE /admin/agent-tool-grants?agent_id=X&tool_id=Y
```

### Admin — Backfill operations
```
POST /admin/artists/backfill-chartmetric-id
POST /admin/artists/backfill-spotify-ids
POST /admin/artists/backfill-spotify-ids-from-chartmetric
POST /admin/artists/flag-for-classification
GET  /admin/artists/with-chartmetric-id
```

---

## §53. Cron schedule

| Job | Cadence | Built? |
|---|---|---|
| chartmetric scraper | 4h | ✓ |
| chartmetric_deep_us | 3h | ✓ |
| chartmetric_artist_tracks | 48h | ✓ |
| chartmetric_artist_stats | 48h | ✓ |
| chartmetric_us_cities | 12h | ✓ |
| chartmetric_artists | 12h | ✓ |
| chartmetric_audio_features | 6h | ✓ |
| chartmetric_playlist_crawler | 72h | ✓ |
| spotify | 6h | ✓ |
| genius_lyrics | 24h | ✓ (idle) |
| musicbrainz | 12h | ✓ |
| kworb | 24h | ✓ |
| radio | 24h | ✓ |
| classification sweep | 15min | ✓ |
| composite sweep | 15min | ✓ |
| breakout detection | 6h | ✓ |
| feature delta analysis (chains quantification) | 24h | ✓ |
| lyrical analysis | 168h (weekly) | ✓ (idle) |
| stale-scraper reaper | 30min | ✓ |
| tunebat-crawler | continuous loop | ✓ (Railway service) |
| ML hit predictor training | weekly | TODO |
| revenue reconciliation | daily | TODO |
| song generation queue | hourly | TODO |
| submission queue (Submissions Agent) | 5min | TODO |
| social posting queue | 5min | TODO |
| marketing phase gate check | hourly | TODO |

---

## §54. Deployment architecture

### Currently running on Railway

| Service | What |
|---|---|
| `soundPulse` | FastAPI API + APScheduler in-process |
| `ui` | React frontend (Vite + nginx) |
| `tunebat-crawler` | BlackTip + Xvfb crawler service (NEW) |
| Neon (external) | Postgres serverless |

### Phase 3 additions

| Service | What |
|---|---|
| `fonzworth-ascap` | Standalone TS service for ASCAP browser registration |
| `submissions-orchestrator` | Submissions Agent worker — could live in soundPulse or as separate service |
| `marketing-agents` | Worker(s) for the 13 marketing agents |
| `song-generator` | Suno/EvoLink call orchestration |
| `revenue-collector` | Daily reconciliation cron |
| GPU compute (optional) | For local Essentia runs if we offload audio QA |
| S3 + CDN (optional) | Audio asset storage |

---

## §55. External API dependencies — VALIDATED REALITY

This is the source-of-truth for what APIs ACTUALLY work, validated against 2025-2026 reality. Every entry here was checked against the API itself or current developer documentation.

| Tool | Status | Reality |
|---|---|---|
| **Chartmetric** | ✅ ACTIVE | Full REST API. $350/mo, 2 req/sec, 172,800/day. Documented endpoints. |
| **Spotify Web API (search/catalog)** | ✅ ACTIVE | Free. Use for search + metadata. |
| **Spotify `/v1/audio-features`** | ❌ DEAD | Returns 403 for any client created after 2024-11-27. No exception. Use Tunebat scrape instead. |
| **Spotify for Artists** | ❌ NO API | UI only. Analytics + playlist pitching are not exposed. Use Chartmetric/Songstats. |
| **Apple Music for Artists** | ❌ NO API | UI only. Use Chartmetric. |
| **MusicBrainz** | ✅ ACTIVE | Free, 1 req/sec anonymous. |
| **Songstats** | ✅ ACTIVE | Paid $50-500/mo. Alternative to Chartmetric. |
| **Genius API** | ✅ ACTIVE | Free with API client registration. Lyrics page must be scraped (API doesn't return lyrics). |
| **Tunebat (scrape)** | ✅ ACTIVE | Cloudflare-protected. Use BlackTip via tunebat-crawler service. Returns 12 audio features. |
| **DistroKid API** | ❌ NO API | UI only. |
| **TuneCore API** | ❌ NO API | Enterprise partnership only. |
| **CD Baby API** | ❌ DEAD | Legacy XML feed deprecated 2018. |
| **LabelGrid API** | ✅ ACTIVE | $1,428/yr starter, REST, sandbox. **MVP-1 distributor.** |
| **Revelator API** | ✅ ACTIVE | Enterprise contract ($1k+/mo typical). White-label SaaS. Real REST. |
| **SonoSuite API** | ✅ ACTIVE | Documented REST. Enterprise contract. |
| **Symphonic** | ⚠ PARTNERSHIP | Partnership-only, not direct API. |
| **TuneRegistry** | ✅ ACTIVE | $35-95/mo. CSV bulk import. PRO submission delivery. |
| **ASCAP** | ❌ NO API | Browser-only via Fonzworth. |
| **BMI** | ❌ NO API | Browser-only, Fonzworth pattern. |
| **SESAC** | n/a | Invitation-only PRO, we don't qualify. |
| **The MLC** | ✅ ACTIVE | DDEX bulk for members. Free. |
| **SoundExchange** | ❌ NO API | Browser-only. Email techsupport@soundexchange.com to inquire about API access. |
| **Songtrust** | ❌ NO API | UI only. NOT recommended (15-20% commission). |
| **CISAC IPI** | ❌ NO API | Database not publicly queryable. Use MusicBrainz as proxy. |
| **YouTube Data API v3** | ✅ ACTIVE | Free quota. Video upload + analytics work. |
| **YouTube Content ID** | ❌ PARTNER-GATED | Requires MCN/label partnership. Can't be assumed turnkey. |
| **TikTok Content Posting API** | ⚠ AUDIT REQUIRED | Sandbox/draft only without TikTok app audit. Full publish needs business verification. |
| **Instagram Graph API** | ⚠ APP REVIEW | Reels publishing works with `instagram_content_publish` scope after Meta app review. |
| **Facebook Graph API** | ⚠ APP REVIEW | `pages_manage_posts` scope, app review required. |
| **X (Twitter) API v2** | ✅ ACTIVE | Free tier limited; basic $200/mo. |
| **Linkfire** | ✅ ACTIVE | REST API. Smart links. Enterprise pricing. |
| **Feature.fm** | ✅ ACTIVE | REST API. $9.99/mo+. |
| **Bandcamp** | ⚠ READ-ONLY | Read-only API for sales/merch (artist accounts). No upload. |
| **SoundCloud** | ❌ FROZEN | New API app registration closed since 2021. |
| **Beatport** | ❌ PARTNERSHIP | Label Manager API for approved labels only. |
| **Playlist Push** | ❌ NO API | Browser only. $300/campaign. |
| **SubmitHub** | ❌ NO API | Browser only. $0.80-1.00/credit. **98.5% AI music detection rate.** |
| **Groover** | ❌ NO API | Browser only. ~$2.18/curator, 10-21% acceptance. |
| **Suno (direct)** | ❌ NO PUBLIC API | Use EvoLink wrapper. |
| **Suno via EvoLink** | ✅ ACTIVE | $0.111/song REST wrapper. |
| **Suno via CometAPI** | ✅ ACTIVE | $0.144/song alternative wrapper. |
| **Udio** | ⚠ FRAGILE | Direct API exists but downloads broken as of 2026-04. Avoid for production. |
| **SOUNDRAW** | ✅ ACTIVE | $500/mo plan = ~1K songs. REST API. |
| **MusicGen via Replicate** | ✅ ACTIVE | $0.064/run. REST. |
| **Stable Audio 2.5** | ✅ ACTIVE | $0.20/run. REST. |
| **DALL-E 3 via OpenAI** | ✅ ACTIVE | ~$0.04/image. |
| **Flux via fal.ai** | ✅ ACTIVE | REST. |
| **Stable Diffusion + IP-Adapter via Replicate** | ✅ ACTIVE | REST. Used for face-locked artist generation. |
| **Google Veo** | ✅ ACTIVE | API. Used for video generation. |
| **Groq** | ✅ ACTIVE | Llama 3.3 70B at $0.59/M input. **Used for assistant, lyrical analysis, smart prompt.** |
| **OpenAI** | ✅ ACTIVE | Per-token pricing. |
| **Anthropic Claude** | ✅ ACTIVE | Per-token. **Used by Fonzworth for ASCAP error recovery (Claude Vision).** |
| **BlackTip** | ✅ ACTIVE | Local Node.js library. Stealth Chrome via patchright. **Critical infrastructure.** |
| **Telegram Bot API** | ✅ ACTIVE | Free. Used for CEO escalation. |
| **Slack incoming webhooks** | ✅ ACTIVE | Free. |
| **SMTP** | ✅ ACTIVE | Use SendGrid or similar provider. |

### Resolution of conflicts from source docs

| Conflict | Resolution |
|---|---|
| v2 referenced "Spotify Audio Analysis API" as a Phase 2 dependency | Marked DEAD. Replaced by Tunebat scrape via BlackTip. |
| Marketing spec assumed direct distributor APIs | Pinned to LabelGrid (MVP-1) + Revelator (alternative). Other distributors marked NO API. |
| Marketing spec assumed Spotify for Artists analytics | Replaced with Chartmetric + Songstats. |
| YouTube Content ID listed as both "mandatory" and "partner-gated" | Resolved: marked as Phase 4b, blocked until partnership. Submissions Agent skips Phase 4 with `needs_partnership` status. |
| MLC listed as "not safe to assume turnkey" but also "mandatory" | Resolved: MLC IS programmatic via DDEX for members (validated). Mandatory once we register as a publisher member. |
| TikTok posting "where available" | Resolved: requires app audit. Submissions Agent uses draft mode until audit, with manual review fallback. |

---

## §56. Operating costs

### Current monthly (Phase 1+2)

| Item | Cost |
|---|---|
| Chartmetric | $350 |
| Neon Postgres | $0-50 (free tier mostly sufficient) |
| Railway hosting (5 services) | $30-80 |
| Groq | ~$0 (free tier) |
| BlackTip / tunebat-crawler infra | included in Railway |
| Genius | $0 (free) |
| RapidAPI Shazam | $0 (disabled, replaced by Chartmetric Shazam data) |
| **Total** | **~$430/mo** |

### Phase 3 additions

| Item | Cost |
|---|---|
| LabelGrid distribution | $1,428/yr ($120/mo) |
| Suno via EvoLink | $0.11/song × N |
| DALL-E 3 cover art | $0.04/song |
| Anthropic (Fonzworth error recovery) | ~$5/mo |
| TuneRegistry (optional alt to Fonzworth) | $35-95/mo |
| MLC membership | $0 |
| Promotion (per song M3 push) | $300-500/song (only on greenlit songs) |

### Phase 3 totals

| Songs/month | Infrastructure | Promotion (cumulative) | Total monthly |
|---|---|---|---|
| 10 | $620 | $5,000 | $5,620 |
| 50 | $720 | $15,000 | $15,720 |
| 200 | $940 | $40,000 | $40,940 |

Promotion only fires on songs that pass the Phase M3 gate (proven organic signal). For any song that doesn't reach M3, promo cost is $0.

---

# Part XI — Build Order & Implementation Rules

## §57. MVP build order

**Recovered from marketing spec §17, with Phase 1+2 already complete.**

### MVP 1 — Production pipeline core
- Artist creation system (§18-21)
- Artist assignment engine (§22)
- Song generation under artist (§24)
- `songs_master` DB
- `song_blueprints` DB
- LabelGrid distribution connector (§30, MVP-1 priority)
- Identifier ingestion (§29 Phase 2)
- CEO decision gate (§23)

### MVP 2 — Rights + marketing core
- Fonzworth ASCAP service (§31)
- BMI portal automation (§32)
- SoundExchange portal (§34)
- Marketing phase engine (§42)
- Content / Video / Caption / Social Posting agents (§43.B,C,D,E)
- Analytics Agent (§43.K)

### MVP 3 — Scale + optimization
- MLC mechanical workflow (§33)
- YouTube Content ID (§35, requires partnership)
- Sync provider connectors (§36)
- Paid Growth Agent (§43.J)
- Editorial / PR Agent (§43.L)
- Cross-catalog compounding logic
- ML Hit Predictor (§13) — needs historical backfill data first

---

## §58. Non-negotiable implementation rules

1. **Never hardcode a single artist per genre.**
2. **Song blueprint precedes artist assignment decision.** The blueprint exists first.
3. **First song sets seed voice; later songs reference prior songs.** Two-phase rule (§21).
4. **Distribution happens BEFORE downstream rights steps that need returned identifiers.** Strict §29 ordering.
5. **Every external submission must be persisted in `song_submissions`.** No exceptions.
6. **Every critical roster decision must support CEO escalation.** Via §23 and §49.
7. **Metadata must be generated once into a canonical master record (`songs_master`), then transformed outward per target service.**
8. **Marketing is phase-based and metric-gated**, not "do everything at once."
9. **Any partner-gated integration must be abstracted behind provider interfaces.** Distribution, PRO, social posting all behind interfaces.
10. **Any field derived from weak inference must carry a confidence score internally.**
11. **Every LLM call must be logged** to `llm_calls` (CLAUDE.md mandate). This already enforced via `llm_client.py`.
12. **Generality principles (CLAUDE.md):** Never build for a specific instance/model/OS. Never hardcode a fix to a test case. Think systemically.
13. **No claims of automation for things that aren't.** APIs that don't exist are marked BLOCKED with a manual-fallback note. No silent stubs.
14. **Spec-vs-reality reconciliation.** When a source doc claims an API exists but it doesn't (e.g., DistroKid API), this PRD says BLOCKED and provides the workaround. Do not implement against fictional APIs.
15. **AI music detection is real.** SubmitHub flags Suno tracks at 98.5% accuracy. Do not assume Suno output is undetectable.

---

## §59. What's already built (✅)

All of the following are deployed and verified in production at https://soundpulse-production-5266.up.railway.app:

- **Data layer:** 15+ scrapers, 23k+ snapshots, 1,732 artists with chartmetric_id, 1,727 with classified genres
- **Tunebat crawler:** Standalone Railway service running BlackTip + Xvfb, autonomously enriching audio features for ~1,090+ tracks (and growing)
- **Breakout Analysis Engine:** All 6 layers implemented. 1,093 breakouts detected in first sweep across 90 genres.
- **Opportunity Quantification:** $ + stream projections + 6-component confidence model. Cached daily.
- **Smart Prompt v2:** LLM-powered, parallel for top-N, 5-min cache, real rationale, average ~2 sec for 5 prompts.
- **SongLab UI:** 10-card grid, copy-to-clipboard, model picker, sort options, surfaced dates, quantification block.
- **Settings UI:** CEO profile + Tools/Agents registry with by-tool/by-agent pivots, inline grant/revoke, credential-presence detection.
- **Submissions Agent (#14):** Registered with all submission tools granted. Implementation TODO.
- **Stale-scraper reaper, Spotify rate-limit governor, classification sweep with track_rollup signal, scraper registry refactor, LLM provider abstraction, 11 alembic migrations.**

---

## §60. What's blocked (🚫) and the workarounds

| Item | Why blocked | Workaround |
|---|---|---|
| **Spotify `/v1/audio-features`** | App created after 2024-11-27 | ✅ Tunebat crawler via BlackTip (BUILT) |
| **DistroKid/TuneCore/CD Baby distribution** | No public APIs | Use LabelGrid (TODO MVP-1) |
| **ASCAP/BMI registration** | No public APIs | Fonzworth browser service (TODO MVP-2) |
| **SoundExchange registration** | No public API | Browser pattern, Fonzworth-style (TODO MVP-2) |
| **YouTube Content ID** | Partnership required | Skip Phase 4 until partnership; manual claim/dispute fallback |
| **Spotify for Artists / Apple for Artists analytics** | No public APIs | Use Chartmetric + Songstats |
| **TikTok auto-publish** | App audit required | Use sandbox/draft mode + manual review until audit complete |
| **Instagram/Facebook publishing** | App review required | Apply for `instagram_content_publish` scope review |
| **Genius lyrics** | Needs `GENIUS_API_KEY` env var (free signup at genius.com/api-clients) | User action: 5 min to sign up + add env var |
| **Suno commercial rights** | Evolving legal area; perpetual commercial license via Warner deal but US Copyright Office doesn't recognize raw AI audio as copyrightable | Accept legal risk, document in artist contracts |

---

---

## §61. Appendix — Tools registry enumeration (42 entries)

Seeded in `tools_registry` (§17, §50). Every entry is addressable by `id` and grantable to any agent via `agent_tool_grants`. Order: category, then alphabetical.

### Automation (1)
1. **blacktip** — BlackTip stealth browser (Node.js/patchright). Underpins every browser-scrape and browser-automation tool below.

### Communication (3)
2. **email_smtp** — Email via SMTP provider (SendGrid/similar).
3. **slack_webhook** — Slack incoming-webhook delivery for ops + CEO alerts.
4. **telegram_bot** — Telegram Bot API — default CEO escalation channel.

### Data (7)
5. **chartmetric** — Chartmetric REST API (primary market-data source, $350/mo).
6. **genius_lyrics** — Genius API (free, needs `GENIUS_API_KEY`).
7. **musicbrainz** — MusicBrainz (free, identifiers + metadata cross-reference).
8. **songstats** — Songstats (analytics backup to Chartmetric).
9. **spotify_audio_features** — Spotify `/v1/audio-features` — DEPRECATED (blocked post-2024-11-27).
10. **spotify_web_api** — Spotify Web API (track/album/artist lookups, wrapped by `spotify_throttle`).
11. **tunebat** — Tunebat audio-features scrape via BlackTip (replaces spotify_audio_features).

### Distribution (3)
12. **labelgrid** — LabelGrid distribution connector (MVP-1 target).
13. **revelator** — Revelator distribution connector (MVP-1 alternative).
14. **sonosuite** — SonoSuite distribution connector (MVP-1 alternative).

### Generation (4)
15. **musicgen** — MusicGen via Replicate (live, $0.064/run).
16. **soundraw** — SOUNDRAW enterprise API.
17. **suno_evolink** — Suno via EvoLink third-party wrapper ($0.111/song).
18. **udio** — Udio Pro (stubbed — licensing transition, ETA H2 2026).

### LLM (3)
19. **anthropic** — Anthropic Claude (including Vision for Fonzworth error recovery).
20. **groq** — Groq Llama 3.3 70B (primary cost-effective LLM).
21. **openai** — OpenAI (GPT-4o and DALL-E 3 access).

### Marketing (6)
22. **feature_fm** — Feature.fm smart-link + pre-save.
23. **groover** — Groover curator outreach.
24. **linkfire** — Linkfire smart-link.
25. **meta_ads** — Meta Ads (Facebook + Instagram).
26. **playlist_push** — Playlist Push curator outreach.
27. **submithub** — SubmitHub curator outreach.

### Rights (5)
28. **bmi_portal** — BMI publisher portal (browser automation).
29. **fonzworth_ascap** — Fonzworth ASCAP submission service (§31).
30. **mlc_ddex** — MLC DDEX feed (mechanical lane).
31. **soundexchange** — SoundExchange portal (neighboring rights).
32. **youtube_cms** — YouTube CMS / Content ID (partnership-gated).

### Social (5)
33. **facebook_graph** — Facebook Graph API.
34. **instagram_graph** — Instagram Graph API.
35. **tiktok_content_posting** — TikTok Content Posting API (audit-gated).
36. **x_twitter_api** — X (Twitter) API v2.
37. **youtube_data_api** — YouTube Data API v3.

### Video (1)
38. **veo** — Google Veo video generation.

### Visual (3)
39. **flux_falai** — Flux via fal.ai. Fallback if OpenAI rejects.
40. **stable_diffusion** — Stable Diffusion + IP-Adapter. Fallback for face-locked generation.
41. **openai_cli_proxy** — ⭐ **Preferred image-gen entry point.** Routes through `gpt-image-1` (OpenAI's native multimodal model). Used for: artist reference sheets (§20, 8-view face-locked via `/v1/images/edits`), song artwork, promo assets, social post visuals. **DALL-E 3 was removed** as insufficiently photorealistic for human portraits — `gpt-image-1` replaces it entirely.

**Count verification:** 1 + 3 + 7 + 3 + 4 + 3 + 6 + 5 + 5 + 1 + 3 = **41** ✓. Matches the seeded row count in `tools_registry` after DALL-E 3 removal.

---

# Document footer

**Source documents merged into this v3:**
1. `planning/PRD/SoundPulse_PRD_v2.md` (Part I verbatim, Parts II-IV updated/superseded where conflicts)
2. `planning/PRD/soundpulse_artist_release_marketing_spec.md` (canonical for §1, §2 workflow + entity model; §3-12 artist/song/submission/marketing systems; §17-18 build order + non-negotiables)
3. `planning/PRD/breakoutengine_prd.md` (compressed into §10)
4. `planning/PRD/opportunity_quantification_spec.md` (compressed into §11)
5. `C:\Users\edang\myApps_v2\fonzworth\planning\PRD\ascap-submission-service.md` (compressed into §31)
6. API validation research from 2025-2026 (folded into §55)

**16 vagueness/conflict items resolved inline — enumerated:**

| # | Item | Resolution | Location |
|---|---|---|---|
| 1 | `lyrical_dna` JSON shape was undefined in source | Defined as 8-field shape (themes, vocab, perspective, motifs, rhyme density, explicit flag, language, avoid list) | §17 |
| 2 | `persona_dna` JSON shape was undefined | Defined as 7-field shape (backstory, traits, voice, posting, controversy, interview, fan relationship) | §17 |
| 3 | `social_dna` JSON shape was undefined | Defined as 6-field shape (handles, calendar template, engagement style, cadence, video length, hashtag strategy) | §17 |
| 4 | `momentum_fit` referenced in formula but not in dimension list | Added as the 10th scoring dimension in assignment engine | §22 |
| 5 | Visual Asset Agent referenced but had no defined scope | Folded into Artist Identity Agent (A) | §43 |
| 6 | Brand Pivot Agent referenced but overlapped other agents | Routed to Content Strategy (B) for signal + CEO Action (M) for decision | §43 |
| 7 | `songs` vs `songs_master` — two names for the canonical song table | Superseded `songs`; `songs_master` is canonical, with full DDL inlined | §17 |
| 8 | "Artist created before blueprint" vs "blueprint first" ordering | Resolved: blueprint FIRST, then assignment/creation | §15 |
| 9 | YouTube Content ID "mandatory" vs "partner-gated" | Resolved: partnership-gated, Submissions Agent skips with `needs_partnership` | §55 |
| 10 | MLC "not safe to assume turnkey" vs "mandatory" | Resolved: MLC is programmatic via DDEX for members; mandatory once registered | §55 |
| 11 | TikTok posting "where available" | Resolved: draft mode + audit gate, manual fallback until audit lands | §55 |
| 12 | 8-view visual sheet vs v2's older 6-angle | Resolved: 8-view is canonical (marketing spec §3.5 wins) | §20 |
| 13 | `genre_config` tunables had no home table | Added full DDL with 6 tunable fields (reference_artist_count, reuse_threshold, cooldown_days, max_artists, CEO gate flag, notes) | §17 |
| 14 | `ai_artists.song_count` referenced by §21 voice rule but not a column | Added as `INTEGER NOT NULL DEFAULT 0` + post-insert trigger from `songs_master` | §17 |
| 15 | `voice_state_reference_block` referenced by §24 but not defined | Defined concrete text template + helper function signature | §21 |
| 16 | `songs_master` declared canonical but DDL was missing | Full ~95-field DDL inlined, 13 field families | §17 |

Items 1-12 were resolved in v3 first pass; items 13-16 were resolved in the consistency-audit pass.

**Originals are unmodified at:**
- `planning/PRD/SoundPulse_PRD_v2.md`
- `planning/PRD/soundpulse_artist_release_marketing_spec.md`

This v3 is the canonical executable spec. When in doubt, this document wins.
