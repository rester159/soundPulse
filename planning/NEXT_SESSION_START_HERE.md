# START HERE — next session entry point

> Last handoff: **2026-04-16** — end of the PRD-refresh session.
> Point the next model at this file first. Read it top-to-bottom before touching code.

---

## 1. What shipped in the last two sessions

**2026-04-15 / 04-16 (this session + the prior one):**
- ✅ **Task #109 — Per-genre song structure rules** (commit `690d0a3`). All six phases shipped end-to-end: migrations 033 + 034, resolver + prompt formatter + orchestrator wiring (try/except so generation never blocks), admin CRUD + per-artist PATCH, Settings subtab + Artist override block with locked tooltip copy, librosa-based Y3K compliance script. **PRD §70.7 has the full status; §70.8 has the Y3K gate template.** 73 tests green.
- ✅ **Chartmetric Phase A — 429 storm fix** (commit `da26f61`). `BURST: 3 → 1` + `on_429()` calls `bucket.drain()` after `set_rate()`. Eliminated the in-process microburst that produced ~50% 429s. **L016 documents the investigation; PRD §7.3 documents the fix.**
- ✅ **Chartmetric Phase B — cross-replica Postgres-coordinated bucket** (commit `50aec4f`). Migration 035 added `chartmetric_global_bucket` singleton table; `chartmetric_ingest/global_bucket.py::GlobalChartmetricBucket` does `SELECT ... FOR UPDATE` on the singleton row. `ChartmetricQuota.acquire()` now consumes from the global bucket FIRST, then the in-process bucket. Closes the L016 multi-replica fan-out. **PRD §7.3 documents the architecture.**
- ✅ **PRD refresh** (this session). PRD v3 §4 / §7 / §17 / §25 / §50 / §54 / §59 / §60 / §70 all updated to match production. `planning/schema.md` head bumped to 035 with the new `chartmetric_global_bucket` spec. `planning/tasks.md` top-of-backlog rewritten.

**2026-04-15 (prior session, before #109):**
- ✅ Task #107 VocalEntryStudio UI fixes. Orange scratch pin nested + keydown stop-propagation (commits `b1ddfbc`, `528230f`, `e3e4a9e`).
- ✅ Frontend HTML cache-control meta tags (commit `f283959`). L015.

---

## 2. Operator action items pending (no code work needed)

1. **Run Y3K compliance A/B** — once Railway finishes rebuilding `50aec4f`, regenerate Y3K via SongLab so the new `[STRUCTURE]` block injects, then download the audio and run:
   ```
   python -m scripts.measure_structure_compliance \
       --audio /path/to/regenerated_y3k.mp3 \
       --structure-json '<json of pop.k-pop seed structure>' \
       --bpm-hint 120
   ```
   Gate at ≥70% sections within ±1 bar. Y3K maps to `song_id 9df3ff71-47ec-4613-9693-c126d764e805` (Kira Lune, primary_genre `pop.k-pop`).
2. **Find the SPA URL** — Railway dashboard → `ui` service → public URL. The API URL (`...up.railway.app`) was never the SPA. See PRD §54.1.
3. **Verify Chartmetric 429 rate dropped** — once `50aec4f` is live, query Neon: `SELECT count(*) FILTER (WHERE response_status = 429) * 100.0 / count(*) AS pct_429 FROM chartmetric_request_queue WHERE completed_at > now() - interval '5 minutes';`. Should be <5% globally.
4. **Decide on `planning/PRD/soundpulse_artist_release_marketing_spec.md`** — still untracked, predates this session. Commit it whenever ready or decide to fold its content into the main PRD.

---

## 3. What the next session should pick up

In rough priority order based on revenue impact + unblock potential:

| # | Task | Why | Where to start |
|---|---|---|---|
| 1 | **MVP-1 LabelGrid distribution adapter (T-182)** | Highest-leverage — unblocks SoundExchange / playlist / marketing dependencies. | LabelGrid sandbox account setup → `services/distribution/labelgrid.py` adapter following the `_stub_adapter` pattern. |
| 2 | **MVP-2 Fonzworth ASCAP go-live (T-190..T-194)** | Framework shipped already — just needs Dockerfile Playwright unlock + DOM selector tuning against the live portal. | `services/portal-worker/portals/ascap.mjs`. ~3-line Dockerfile edit + an evening of selector iteration. |
| 3 | **MVP-2 MLC DDEX XML builder (T-201)** | Real API path (no browser automation). Mechanical-royalty registration. | `services/distribution/mlc_ddex.py` (new). Spec in PRD §33. |
| 4 | **YouTube Content ID via YouTube Data API v3 (T-203 fallback)** | Partnership-gated for full Content ID, but Data API v3 path for artist-channel uploads works without partnership. | `services/marketing/youtube_uploader.py` (new). |
| 5 | **P1 closeout: Chartmetric 90-day backfill chunks (T-058)** | Get historical data depth for ML training. | `python -m scripts.backfill_chartmetric_deep_us --confirmed-only --days 90`, chunked over multiple runs. |
| 6 | **P2 unblock: First successful ML model training (T-303)** | Data-bound — needs ~6 weeks of resolved breakouts. Earliest viable: late May 2026. Until then: rule-based fallback already in production. | `ml/train.py`. |
| 7 | **Operator-tunable rate-limit knobs** | Promote `chartmetric_global_bucket.rate_per_sec` + `burst` to the admin UI so operator can tune without redeploy. | New `/admin/chartmetric/rate-limit` endpoint + a small Settings sub-section. |

The full backlog with dependencies lives in `planning/task_decom.md`. The completion log at the bottom of that file is durable session-to-session memory.

---

## 4. Standing rules in force (do NOT relax)

- **CLAUDE.md is the operating manual.** Read it on session start.
- **TDD.** Failing test first, every meaningful change. Real-DB tests against the Neon temp-branch path (`mcp__Neon__prepare_database_migration` → run tests → `mcp__Neon__complete_database_migration`).
- **L004 + L010 + L016** — Chartmetric rate limiter discipline. `BURST=1` is load-bearing. Drain on 429. Never assume Chartmetric's documented "2 req/sec" is the actual ceiling — it's enforced via a tighter token bucket.
- **L014** — DTW is dead. Structural mismatch is fixed at the source via §70 structure injection. Do not reach for DTW / phase-lock as the primary fix.
- **L015** — Cache-control meta tags on `frontend/index.html` stay. Do not strip them.
- **L012** — Nested key handlers in React must `e.stopPropagation()`. The orange-pin bug is fixed; don't reintroduce.
- **Generality principles (CLAUDE.md):** Never build for a specific instance / model / OS. Never hardcode a fix to a test case. Treat every hardcoded constant referencing a real-world entity as a code smell.
- **Migrations via Neon MCP** — `prepare_database_migration` → verify on temp branch → `complete_database_migration`. Never raw `alembic upgrade head` against prod.
- **Commits only when explicitly asked.** Never auto-push.

---

## 5. Read-on-arrival

Before writing code:
1. `git log --oneline -10` — see recent commits.
2. `planning/lessons.md` — read at minimum L016 (most recent) and any L00X relevant to the area you're about to touch.
3. `planning/tasks.md` — current top-of-backlog.
4. `planning/PRD/SoundPulse_PRD_v3.md` — relevant section for the chosen task.
5. `planning/schema.md` — current head is `035`; per-table specs.
