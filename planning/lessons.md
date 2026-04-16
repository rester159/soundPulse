# Lessons Learned

> Log mistakes, misses, and gaps here with root cause + fix. Read at the start of every session.

---

## L001 — Chartmetric `/api/charts/spotify` `type=plays` is not a valid value (2026-04-11)

**Discovery:** While building the deep US Chartmetric scraper, the doc-discovery subagent (reading the official `api.chartmetric.com/apidoc` cross-referenced against pycmc and the Mixture Labs CLI) confirmed that `/api/charts/spotify` accepts only `type=regional` and `type=viral`. The values `plays`, `popularity`, `monthly_listeners`, `playlist_count`, `playlist_reach` belong to the SEPARATE `/api/charts/spotify/artists` endpoint.

**Impact:** The existing `scrapers/chartmetric.py`, `scripts/backfill_chartmetric.py`, and `scripts/backfill_deep.py` all included a `type=plays` entry in `CHART_ENDPOINTS`. Chartmetric was either silently returning empty data or returning the wrong chart for that call. This contributed to the "why so few records?" mystery — we were burning ~25% of the daily-cadence rate budget on an invalid endpoint.

**Root cause:** The original scraper was written from a comment that said `type` accepts `regional/viral/plays` — that comment was wrong. No probe verified the assumption.

**Fix:** Removed the `plays` entry from all three files. Confirmed against the apidoc.

**Prevention:**
1. **Always verify upstream API endpoints against the canonical docs** before adding them to a scraper. Comments lie. Docs (and well-maintained third-party clients like pycmc) don't.
2. **Probe scripts before production runs.** The new `scripts/chartmetric_probe.py` hits every endpoint in `ENDPOINT_MATRIX` once and reports success/failure — run it before any backfill.
3. **Don't trust silent success.** If a scraper "succeeds" but returns 0 entries from a chart that should have hundreds, that's a bug, not normal. Add count assertions to scrapers and alert on anomalies.

**Files affected:** `scrapers/chartmetric.py`, `scripts/backfill_chartmetric.py`, `scripts/backfill_deep.py`. The deep US scraper (`scrapers/chartmetric_deep_us.py`) was built from the apidoc directly so it was never wrong.

---

## L002 — Bulk ingest must defer expensive per-row work or it can't scale (2026-04-11)

**Discovery:** While building the bulk ingest endpoint to support the deep US Chartmetric backfill (~205K calls × ~200 rows each = ~40M row inserts), the audit had already flagged that `POST /api/v1/trending` was timing out on Neon at modest volumes. Root cause confirmed: every POST runs the genre classifier inline (6+ DB queries per entity), then `recalculate_composite_for_entity` (which does its own multi-table reads + writes), then a cache invalidation. Per-record cost is far too high for bulk loads.

**Impact:** The original backfill scripts (`backfill_chartmetric.py`, `backfill_deep.py`) POST each record individually with `INGEST_DELAY=0.05`. With ~350 records/day × 90 days = 31,500 POSTs, the script would either hit Neon's connection-pool ceiling or run out of patience. The PRD's claim of "9,031 snapshots across 40 dates" matches a backfill that ran but didn't finish.

**Root cause:** The endpoint was designed for small-volume scraper traffic (a few dozen records per scraper tick) and treats every record as a complete unit of work. There was no batched fast-path.

**Fix:** Built `POST /api/v1/trending/bulk` with three deferrals:
1. **No inline genre classification** — entities are tagged `metadata_json.needs_classification = true` and processed by `sweep_unclassified_entities` (15-min interval).
2. **No inline composite recalc** — `normalized_score=0` and a deferred `sweep_zero_normalized_snapshots` runs `normalize_score` + `recalculate_composite_for_entity` afterward.
3. **One cache invalidation per batch**, not per record.
Plus: single transaction, `INSERT ... ON CONFLICT DO NOTHING` for snapshot dedup.

**Prevention:**
1. **For any high-throughput data path, design the fast path FIRST** — don't try to make a per-record path "fast enough" with optimizations.
2. **Defer everything that doesn't have to happen synchronously.** Classification, scoring, denormalization — all background sweeps.
3. **Always have a queue marker.** The deferred sweeps need to find their work — `metadata_json.needs_classification` and `signals_json.normalized_at IS NULL` are how they know what to process.
4. **Sweeps must be idempotent.** Crash mid-batch → re-run picks up where it left off. The current implementation does this via the markers.

---

## L004 — Chartmetric tier limits + probe rate-bucket gotchas (2026-04-11)

**Discovery:** Ran the deep US Chartmetric probe twice (first at 0.55s/req, second at 2.0s/req) against the live API. Captured authoritative tier-vs-rate-limit-vs-param-error reality.

**Findings:**

1. **The user's current Chartmetric tier ($350/mo Developer plan) does NOT include:**
   - **TikTok charts** — all 6 endpoints (`tracks_daily/weekly`, `videos_weekly`, `users_likes/followers`, `top_tracks`) returned 401
   - **Radio/Airplay charts** — all 5 metric variants (`monthly_listeners`, `popularity`, `followers`, `playlist_count`, `playlist_reach`) returned 401
   - **Twitch charts** — both endpoints returned 401
   - **Audience demographics** — `instagram-audience`, `tiktok-audience`, `youtube-audience` returned 401
   - These are **paid add-ons** sold separately. Email `hi@chartmetric.com` to confirm pricing.

2. **Chartmetric chart depth has changed.** Spotify regional/viral charts now return **50 items per page**, not 200 as the docs say. To get more, paginate with `offset=50, 100, 150, 200`. Worth adding pagination to the deep scraper.

3. **Several documented endpoints have wrong params in the doc-agent's report:**
   - `/api/charts/spotify/artists` — `interval=daily` returns 400. The 5 type variants likely require `interval=weekly` or `interval=monthly` instead. Apidoc doesn't say which.
   - `/api/charts/applemusic/tracks` — `?insight=top` and `?insight=daily` both 400. Likely the right shape is sub-resources `/tracks/top` and `/tracks/daily`, not query params.
   - `/api/charts/amazon/*` — all 4 variants 400. Possibly `code2=US` (uppercase) is required, or the param name is different.
   - `/api/charts/soundcloud` — both `kind=top` and `kind=trending` 400. Possibly the country/genre format is wrong.
   - `/api/artist/list?code2=US&sortColumn=sp_monthly_listeners` — 400. The sort column name is probably wrong.

4. **Probe rate-bucket gotcha:** the first probe at 0.55s/req (= 1.8 req/sec, just under the 2 rps documented limit) triggered Chartmetric's **token-bucket throttling** mid-burst, returning 17 false-positive 429s. Re-probing at 2.0s/req (= 0.5 req/sec) eliminated all 429s and gave clean tier-vs-param distinctions. **Lesson: Chartmetric's "2 req/sec" headline rate is enforced via a tighter token bucket, not a strict per-second limit.** The deep scraper at 0.55s/req will hit the same throttling on long backfills — bumping it to 1.0s/req (1 rps) is safer, costs ~80% longer backfill time but eliminates 429 noise.

5. **Probe parser bug:** artist endpoints (`/artist/{id}/stat/{platform}`, `/where-people-listen`, etc.) returned EMPTY in the probe report — but the response shape almost certainly has the data under different top-level keys than chart endpoints. The artist endpoints likely work; the probe parser just doesn't recognize their shape. Follow-up task to fix the probe.

**Effective working set after the probe:**
- 17 confirmed-OK chart endpoints
- 79 expanded API calls per snapshot date (with per-genre fan-outs)
- Estimated ~3,000–5,000 unique tracks/day after dedup
- = ~30–80× the current production volume of 60–225 tracks/day
- Uses ~0.05% of the daily 172,800 quota — wildly underutilized

**Path to fuller coverage:**
- Fix the 13 param-error endpoints (P1-072..P1-075, P1-078) → +30% endpoints
- Upgrade Chartmetric tier (P1-079) → +TikTok, +Radio, +Twitch, +audience demographics → could 2x the volume
- Add pagination to existing endpoints → 4x the depth (50 → 200 items per chart)
- Add per-city pulls once `/cities` discovery works (P1-077)

**Prevention:**
1. **Always probe before promoting endpoints to confirmed.** The doc agent's report was largely accurate but had several wrong-param details that only the live API could verify.
2. **Use a generous probe delay** (2s+) to distinguish tier-vs-rate-limit unambiguously. Don't trust 429s in probe runs as evidence of anything.
3. **Different endpoint families have different response shapes.** A chart probe that parses `data: [...]` won't work for artist endpoints — write per-shape parsers when probing different families.
4. **API docs are source-of-record for what EXISTS, not what your tier UNLOCKS.** Always assume tier blocks until proven otherwise.

---

## L003 — Background sweeps need to LOG failures, not swallow them (2026-04-11)

**Discovery:** While building the classification sweep, I had to consciously decide what to do on a per-entity classifier failure. The audit (AUD-001) had already flagged that `api/routers/trending.py:88` swallows every classifier exception with `except Exception: pass`, which is why ~95% of tracks have empty `genres`.

**Impact:** Without per-row logging + retry tracking, "the sweep ran" tells you nothing about WHY classification coverage isn't improving. You're flying blind.

**Root cause:** Generic anti-pattern. `except Exception: pass` is almost never the right choice in production code.

**Fix:** The classification sweep:
- Logs every exception with the entity ID, attempt number, and exception message
- Tracks `classification_attempts` in `metadata_json` (per-entity counter)
- After 3 failed attempts, marks `needs_classification = "skipped"` (string sentinel) so we stop retrying — but the entity is still recoverable via `force_reclassify=True`
- Stores the last error in `classification_last_error` so you can grep the DB for what's failing

**Prevention:**
1. **Never swallow exceptions silently.** At minimum: log with context (entity id, operation, exception). Audit task AUD-001 / AUD-006 to fix the existing offenders in `trending.py:88` and `genre_classifier.py:402` was created from this discovery.
2. **Bounded retries with permanent-skip sentinel** is the right pattern for unbounded background queues — otherwise one bad row blocks the queue forever or burns cycles forever.
3. **Status endpoints** — add `/api/v1/admin/sweeps/status` so you can see queue depth without running a query.

---

## L005 — Vendor API claims: verify the tier, not just the vendor (2026-04-13)

**Discovery:** While recommending a distributor API partner for SoundPulse, I twice told the user "Too Lost has an API" based on research, and both times it was wrong *in the specific sense that mattered*. The user signed up for Too Lost, paid, looked at their dashboard, saw no API, and called me on it.

**What the research got right:**
- Too Lost genuinely does have an API offering — but it lives on a separate Enterprise/Suite page (`toolost.com/suite/enterprise`, `toolost.com/suite/delivery`), not the consumer pricing page (`toolost.com/pricing`).
- Enterprise tier includes "API access, bulk delivery, ingestion, royalty processing, custom data exports" — their words — but it's sales-gated and invisible from the consumer dashboard a normal $19.99/yr account holder lands in.

**What I got wrong — twice:**

1. **First pass (research-driven recommendation):** I lumped "Enterprise tier with API" into the top-line "Too Lost is #1" recommendation without distinguishing it from the consumer-tier product the user would actually be signing up for. The research report was technically accurate but the pitch buried the fact that API access requires a separate enterprise conversation. Reading it as a user, you'd assume you click "Sign Up" on the pricing page and get API keys. You don't.

2. **Second pass (over-correction):** When the user said "you just sign up, there is no email to be sent," I agreed and said "you're right, I was treating them like enterprise sales vendors" — but then repeated the same error by implying all three top picks (Too Lost / limbo/ / Revelator) were self-serve. **Revelator explicitly has a `Contact Sales` button + `api@revelator.com`**, which I had in the research earlier and ignored in the correction. Too Lost's **real API tier is sales-gated**, which I also had in the research and overrode.

**Impact:** User paid for a subscription on false premises, discovered the dashboard has no API surface, and lost trust in two rounds of my recommendations in a row. Zero code was written based on the wrong recommendation, so the technical blast radius is zero — but the trust blast radius is real and the user had to do the verification work I should have done.

**Root cause:** Three compounding anti-patterns:
1. **Not distinguishing "vendor has X" from "the SKU a customer can self-serve has X."** A research claim like "Vendor offers an API" is meaningless without naming the exact tier and price point. The same vendor can have "API access" on an enterprise plan and zero programmatic surface on the consumer plan.
2. **Not verifying live before recommending.** I had `WebFetch` and `WebSearch` available. I delegated to a subagent, got back a decision-grade report with citations, and relayed it as authoritative without hitting a single vendor page myself.
3. **Trusting my correction instead of re-checking.** When the user pushed back, I corrected by over-agreeing ("yes just sign up") instead of saying "let me actually look." The second mistake was worse than the first because it was a confident correction in the wrong direction.

**Fix:**
- Verified post-hoc by WebSearching `"toolost" API OR "bulk upload" OR "enterprise"` — confirmed:
  - Consumer tier: **no API**, but **CSV bulk upload** is supported (`help.toolost.com/.../9298256399508-How-Do-I-Bulk-Upload-Releases`). That's the workaround for our current account — we can automate CSV generation and the user uploads manually.
  - Enterprise tier: API exists on `toolost.com/suite/enterprise`, sales-gated, separate product.
- Revised the recommendation to be explicit about tier: (1) immediate — automate CSV generation against the consumer account, (2) parallel — contact Too Lost Enterprise via the suite page, (3) hedge — verify limbo/ Music Blocks is truly self-serve for API.

**Prevention (rules for future vendor research):**
1. **Name the exact tier and price in the recommendation.** Not "Vendor X has an API" — "Vendor X Enterprise tier ($XXX/mo, sales-gated) has API access; the consumer tier at $YY/yr does not." If the research can't produce that distinction it's not decision-grade.
2. **Verify live via WebFetch before recommending anything a user will spend money on.** Research agents are a starting point, not an authority. Always load at least the vendor's pricing page and any "developer" / "enterprise" page myself before endorsing.
3. **When a user pushes back, verify — don't reflexively agree.** "You're right, my mistake" without a re-check is a worse error than the original. Treat pushback as a signal to look at primary sources, not a signal to flip positions.
4. **Distinguish "API" from "bulk upload" from "portal automation" in every recommendation.** A CSV bulk import is not an API, but it's not portal automation either — it's a third category worth naming explicitly. The right recommendation often uses CSV bulk import as a bridge while API conversation is underway.
5. **Research output that says "has API, contact for details" is a red flag that the API is sales-gated, not a self-serve product.** Read that language literally.
6. **Self-audit rule for recommendations:** before shipping a vendor rec, ask "if the user signs up for the exact SKU I'm pointing at, will they see the feature I'm promising in their dashboard within 24h?" If no, flag the gap explicitly.

---

## L006 — Pin `librosa` and `scipy` together or `signal.hann` disappears (2026-04-13)

**Discovery:** The stem-extractor Docker build on Railway kept failing at runtime with
`AttributeError: module 'scipy.signal' has no attribute 'hann'`. The error came from
`librosa 0.10.1`, which imports `scipy.signal.hann`. SciPy **1.13** removed that alias —
you have to call `scipy.signal.windows.hann()` now. No `librosa` patch landed until
`0.10.2.post1`, and `pyproject.toml` had `librosa>=0.10` + unpinned `scipy`, so the
Docker image solved to `librosa 0.10.1 + scipy 1.14` on every rebuild.

**Impact:** Every stem-extraction job failed instantly. Wasted ~3 rebuild cycles on
Railway (gcc-free attempts, htdemucs swap, etc.) before isolating the SciPy API drift
as root cause.

**Root cause:** Version range that was valid at pin-time silently went out of range
when a transitive dependency (SciPy) removed a top-level API. No lockfile on the
microservice, so every rebuild re-resolves upwards.

**Fix:**
- Pin `librosa==0.10.2.post1` (contains the `scipy.signal.windows.hann` port)
- Cap `scipy<1.14` as a second-line defense
- Committed in `5e0f467` / `900fcf3`

**Prevention:**
1. **Any Python microservice shipped via Docker without a lockfile is a ticking time bomb.** Use `pip-compile` + `requirements.txt` or `uv lock`, not hand-maintained `>=` ranges.
2. **When a vendor library (librosa/torch/numpy) pins against a scientific stack, pin the scientific stack too.** Upper bounds on scipy/numpy are as important as lower bounds.
3. **A red runtime error on a successful image build is the tell:** the build layer cached OK but resolved a version that no longer exists at the API it's calling. Always check `pip list` in the container on new errors.

---

## L007 — Quantized model dependencies drag in gcc (2026-04-13)

**Discovery:** Trying to upgrade the stem-extractor from `htdemucs` to `mdx_extra_q` for
better vocal isolation pulled in `diffq` (DiffQ weight quantization). `diffq` has no
wheels for Python 3.12 on linux/amd64, so pip builds from source and fails with
`gcc: not found` — the `python:3.12-slim` base doesn't carry a C toolchain.

**Impact:** Adding `mdx_extra_q` as a Demucs backend required either (a) a fatter
Docker base image with `build-essential`, or (b) staying on `htdemucs`. I went with
(b) — the quality delta wasn't worth ~400 MB of base image.

**Root cause:** A pure-Python library wasn't. The model name in the scraper registry
quietly pulled in a C-extension dependency tree that the slim base can't compile.

**Fix:** Reverted to `htdemucs` as the default. `diffq` removed from pyproject.
Commit `5e0f467`.

**Prevention:**
1. **Before adding a new model backend, check its dependency tree in the container
   image you actually ship, not on your laptop.** Macs with `clang` installed and
   bare-metal linux dev boxes lie about this.
2. **Quantized models are not free.** If the README mentions "int8" or "quantization"
   or "bit-packing", assume C-extension dependency drag.
3. **`python:3.12-slim` has no compiler.** Any source-build dep failure on that base
   is either (a) install `build-essential`, (b) find a wheel, or (c) pick a different
   library. Usually (c).

---

## L008 — `railway logs --build` shows build logs, not runtime; `railway redeploy` != `railway up` (2026-04-13)

**Discovery:** During the stem-extractor saga I repeatedly ran `railway logs` to
diagnose runtime failures and got back only build output — scrolled a mile of
"pip installing ...", no Python tracebacks from actual job runs. Separately, I kept
confusing `railway redeploy` (replays the last deployment with the same image) with
`railway up` (uploads the current working tree and builds fresh), which wasted at
least two deploy cycles when I thought I was shipping a fix that Railway was
silently re-shipping the broken build.

**Impact:** ~30 minutes of "why isn't my fix taking effect?" chasing, plus the
false belief that the fix was deployed when it wasn't.

**Root cause:**
1. `railway logs` defaults to a **service-and-environment-scoped** log stream
   whose contents depend on the Railway UI's "Logs" tab selection when you last
   opened it. If that tab is on "Build", the CLI gives you build logs.
2. `railway redeploy` is a **re-trigger**, not an upload. If your local tree has
   unshipped changes, `redeploy` will not pick them up — you need `railway up` or
   `git push` (if Railway is tracking the remote).

**Fix:** Always use explicit flags:
- `railway logs --deployment` for runtime logs
- `railway up` to build-and-ship local changes
- `railway redeploy` only to re-run the last build when you want the SAME artifact
  (e.g., to kick a stuck health check)

**Prevention:**
1. **Add the flag, don't rely on defaults.** Railway CLI defaults follow the web
   UI's state and will bite you when you switch tabs.
2. **When a fix "doesn't take effect," check the deployed commit SHA against
   `git rev-parse HEAD` before touching anything else.** Most of the time the
   deploy didn't ship, not the fix.
3. **`git push` is almost always the right deploy path on Railway when the
   service is GitHub-linked.** CLI `up` is for unlinked-service debugging.

---

## L009 — `gpt-image-1` safety filter blocks vocab that worked on DALL-E 3 (2026-04-12)

**Discovery:** Migrating the portrait generator from DALL-E 3 to `gpt-image-1`
caused silent "safety filter" refusals on prompts that DALL-E 3 had happily
rendered a week earlier. The filter does not raise — the API returns an image
with a generic "safety violation" placeholder, or a 400 with a thin error
message, depending on the prompt. Trigger vocabulary in my case included
normally-fine fashion terms like "fishnet", "latex", "cropped", "distressed",
and (bizarrely) some city names attached to specific fashion descriptors.

**Impact:** Portrait generation silently regressed on ~20% of AI-artist personas
after the model switch. Took a manual audit of blank outputs to notice.

**Root cause:** `gpt-image-1` uses a newer/stricter moderation pass than DALL-E 3,
trained on a different vocabulary. Prompts are filtered server-side before the
image model sees them, so successful DALL-E 3 prompts don't round-trip.

**Fix:** (still open) Build a persona-prompt sanitizer that strips known-triggering
vocab before generation and swaps in neutral alternatives (`fishnet` → `fine mesh`,
`cropped` → `above-waist`, etc.), with an audit log of what was swapped so we can
see filter-drift over time.

**Prevention:**
1. **Assume model migrations change the safety filter, not just the renderer.**
   Never swap image models without re-running the top-20 historical prompts in a
   smoke suite.
2. **Filter refusals are often silent.** Check for blank/placeholder outputs, not
   just HTTP errors.
3. **Keep a trigger-vocab blacklist per model** and a diff log so you can see
   when a new term starts failing.

---

## L010 — Lessons that are written but not enforced don't count (2026-04-13)

**Meta-discovery:** During the Chartmetric ingestion throughput push I had to
apply L004 (the token-bucket / 1.0 s/req fix) to `chartmetric_deep_us.py`
**two days after L004 was written**. Then I had to apply it AGAIN to
`chartmetric_artist_tracks.py` (Stage 2C) because the fix had only landed on the
scraper I was looking at when I wrote the lesson. And `chartmetric_artist_stats.py`
still runs at the old 0.55 s/req today — I haven't fixed it yet.

**Impact:** L004 was written, committed, included in `planning/lessons.md`, and
was supposed to be the enforcement mechanism for "don't hit Chartmetric at 0.55s
/req again." Instead, it sat in a doc that I wasn't reading at the moments I
needed it, while three live scrapers kept making the exact mistake the lesson
described.

**Root cause:** Writing a lesson is a one-time cost. Enforcing a lesson is an
ongoing cost that requires (a) actually reading lessons.md at the start of every
session, (b) doing a search for the pattern the lesson describes across the
codebase, (c) fixing EVERY occurrence, not just the one that happened to trigger
the discovery. I did (c) only for the triggering scraper, and (a) only
sporadically.

**Fix:**
- Applied 1.0 s/req adaptive throttle to `chartmetric_deep_us.py` (commit
  `c1e6ac2`) and `chartmetric_artist_tracks.py` (Stage 2C, commit `0460e48`).
- **Still outstanding:** `chartmetric_artist_stats.py` still has
  `REQUEST_DELAY = 0.55`. Logging as open work.

**Prevention (process rules, not code):**
1. **When a lesson is written, grep the whole codebase for the anti-pattern in
   the same session and fix every occurrence.** Half-applied lessons are worse
   than no lesson because they create false confidence.
2. **Every CLAUDE.md session bootstrap must actually read lessons.md, not just
   claim to.** If the previous session updated L00X, I should know about L00X
   before I write any code that touches an area L00X describes.
3. **Add a lesson-to-code test.** For L004, that's a grep test:
   `rg "REQUEST_DELAY\s*=\s*0\." scrapers/` should return zero results. Turn
   that grep into an assertion in a test file so CI catches regressions.
4. **Meta-rule: if the current session is about to modify a file that has an
   open lesson against it, re-verify the lesson is applied before editing.**

---

## L011 — When a vocal-entry detector "works," it's often the wrong peak (2026-04-12)

**Discovery:** The first cut of the vocal-entry-point detector (used by the
instrumental-mix pipeline to time-align Suno vocals onto a user-uploaded beat)
picked a single spectral-flatness minimum and called it the vocal entry. On ~30%
of test beats it picked the wrong minimum — e.g., a synth pad drop around 0:12
that looked like a vocal entry because the flatness metric crashed at the same
moment. The pipeline then tried to mix the vocal onto the instrumental 15 s
before the beat actually wanted vocals.

**Impact:** Audible "vocal-too-early" artifacts on roughly a third of generated
songs until the detector was rebuilt.

**Root cause:** A single-metric heuristic (spectral flatness) was load-bearing
on a decision with ~5 plausible candidates per track. Any drop in flatness looks
like "a new element entered" — drums, synth, bass, vocal, effect — and the metric
can't distinguish between them.

**Fix:** Voting detector combining three signals:
- `librosa.segment.agglomerative` section boundaries (structural segmentation)
- Spectral flatness minima (timbral change)
- Onset strength peaks (energy change)

Each signal proposes candidates; the detector takes the earliest timestamp that
is voted by at least 2 of the 3. Also added a CEO "nudge vocal entry" UI so the
auto-detection can be manually overridden per-song, and a `remix_only` job type
that skips Demucs on re-mixes (~10 s instead of 15 min).

**Prevention:**
1. **When a heuristic is load-bearing on a creative decision, never let a single
   metric own the decision.** At least 2 independent signals should agree, and
   the number of plausible candidates per decision is a good proxy for how many
   signals you need.
2. **For any ML/DSP decision with meaningful false-positive cost, ship the CEO
   override UI alongside the auto-detection.** "Auto with manual nudge" is
   strictly better than "auto-only" for creative work.
3. **Spectral flatness is noisy on music with dense textures.** Don't use it
   alone for structural analysis.

## L012 — Nested DOM children need explicit `stopPropagation` when a parent listens for the same keys (2026-04-15)

**Discovery:** The VocalEntryStudio orange scratch pin lived as a DOM child of
the green voice block. Both elements had `onKeyDown` handlers — the block
caught ArrowLeft/Right to nudge `voiceEntry`, and the pin caught the same
arrows to nudge `orangePin`. Without `e.stopPropagation()` on the pin's
handler, a single ArrowRight press fired both handlers and advanced
`orangePin` AND `voiceEntry` by 0.1s in lockstep. To the user, the pin
appeared frozen relative to the block because it was moving at exactly the
same screen-space rate as the block itself. Three different "fixes" to the
rendering / z-index / DOM parentage failed to make the symptom go away
because none of them addressed the event bubbling.

**Root cause:** Synthetic events from React's delegated listener at the
root bubble through every React-registered handler in the ancestor chain
unless explicitly stopped. `preventDefault` blocks the browser's default
action; it does NOT block React's other handlers.

**Fix:** `e.stopPropagation()` in the orange pin's keydown for both the
arrow-key and Delete/Backspace branches (commit `e3e4a9e`).

**Lesson:** whenever two nested elements both respond to the same key,
the inner handler MUST `stopPropagation` or you'll get silent double-fire
bugs that look like "my state is frozen" but are really "both states are
moving in sync".

## L013 — Test selectors must be specific enough to survive state changes (2026-04-15)

**Discovery:** Playwright test used `document.querySelector('[title*="scratch pin"]')`
to check whether the orange pin element existed. After `setOrangePin(null)`
the pin was correctly unmounted, but the test query kept returning a
result — because the `"+ orange pin"` TOGGLE BUTTON's own `title` attribute
contained the phrase `"Add an orange scratch pin"`. The substring match
was satisfied by the button. I spent 20 minutes chasing a non-existent
"Del doesn't remove the pin" bug before instrumenting the state directly
via `useEffect` and confirming the state transition was in fact clean.

**Fix:** prefer selectors that uniquely identify the element. For the pin
the right selector is `[title^="scratch pin +"]` (prefix match on the pin's
exact title format `scratch pin +N.Ns from voice entry`), not a substring
match that collides with the button. Better: assign a stable
`data-testid="orange-scratch-pin"` attribute to the element and key tests
on that instead of implementation details of the title.

**Lesson:** when a test is telling you a user-facing bug exists but
instrumented state says everything is fine, the test is lying first.
Check the selector before blaming the code. And prefer `data-testid` or
structurally unique selectors over attribute substring matches.

## L014 — DTW only fixes timing drift within shared content; structural mismatch needs source-level fix (2026-04-15)

**Discovery:** Proposed DTW (dynamic time warping) as a way to sync Suno's
vocal stem to a human-made instrumental. Human correctly pushed back: the
Y3K human instrumental has a 20-second intro, but Suno's generated vocal
only has 5 seconds of intro-equivalent silence. DTW assumes both
sequences contain the same content with only timing differences. When
one sequence has content the other doesn't have at all, DTW picks a
best-effort alignment that stretches a single note across the missing
section — sounds worse than no alignment.

**Root cause of the Y3K sync issue wasn't drift; it was Suno writing a
structurally different song from what the human instrumental is.** No
post-hoc alignment technique fixes that — the vocals simply don't exist
for the intro section.

**Fix direction:** constrain Suno's song structure at the prompt level.
Inject genre-specific section tags `[Intro: 8 bars, instrumental]
[Verse 1: 16 bars] [Pre-chorus: 4 bars] [Chorus: 8 bars] ...` so Suno's
output has a predictable structure that can be matched to the human
instrumental's bar count. This is task `#109` (per-genre song structure
rules) — see `planning/NEXT_SESSION_START_HERE.md`.

**Lesson:** before reaching for a signal-processing fix, check whether
the two sequences actually represent the same underlying content. If
they don't, you're trying to align things that have nothing to align —
fix the generation, not the output. DTW / time-warping / phase-lock are
polish for drift-within-matching-content, not glue for structural
mismatch.

## L015 — Static HTML shells on Railway cache by browser heuristic; set `Cache-Control` meta tags on SPA entry point (2026-04-15)

**Discovery:** Shipped three correct frontend fixes over the course of a
session. Each build produced a new bundle hash (`index-XXXXXXXX.js`). The
user kept reporting "I still see the old UI" after every push, even after
hard-refreshing. Live bundle fetch from my CLI always showed the latest
code, so the deploy was fine. The browser was the culprit: Railway served
`index.html` with no `Cache-Control` header, which makes Chrome fall back
to *heuristic freshness* (roughly: 10 % of the time since the `Last-Modified`
date). For a file with no `Last-Modified`, it uses the etag-based path —
and in practice Chrome was reusing the cached HTML for minutes-to-hours
even across refreshes.

The cached HTML still pointed to the OLD bundle hash. So the browser
fetched the OLD bundle from cache (cached by hash → still valid forever)
and rendered the OLD UI. The new bundle hash sat on disk, uncalled.

**Fix (commit `f283959`):** add explicit `no-cache` meta tags to
`frontend/index.html`:
```html
<meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate" />
<meta http-equiv="Pragma" content="no-cache" />
<meta http-equiv="Expires" content="0" />
```

These force the HTML to always revalidate on load, which means the browser
always gets the freshest bundle reference, which means the freshest JS
bundle is always fetched. The JS bundle itself can still be cached
aggressively (and should be — its hash is immutable).

**Lesson:** SPAs ship with an entry HTML that's essentially a redirect to
a hashed bundle. That entry HTML MUST be marked `no-cache` or the whole
cache-busting-via-hash strategy silently falls apart. When an SPA
redeploy "does nothing," cache the HTML shell first.

**Prevention:** check `curl -I https://<host>/` response headers on every
static-host setup. If there's no `Cache-Control` (or it allows caching),
either add a header at the CDN/server layer or add the meta tags to the
entry HTML. Do not rely on "the user will hard-refresh."

