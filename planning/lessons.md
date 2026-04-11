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

