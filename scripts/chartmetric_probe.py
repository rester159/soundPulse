"""
Chartmetric API endpoint probe — verifies tier access for the deep US matrix.

Run this BEFORE the deep backfill. It does three things:

1. Hits every endpoint in `ENDPOINT_MATRIX` once with the right date snap
   and the right country/genre param to verify the user's tier includes it.
2. Discovers the numeric Chartmetric city IDs for US cities via
   `GET /api/cities?country_code=US` and prints them so they can be
   persisted for per-city pulls.
3. Probes the audience-demographic endpoints (which are sometimes a paid
   add-on) for a known artist (Drake, cm_id=1932) so we know whether the
   enrichment lane is unlocked.

Usage:
    docker exec soundpulse-api-1 python scripts/chartmetric_probe.py
    # or:
    CHARTMETRIC_API_KEY=... python scripts/chartmetric_probe.py

Estimated requests: ~50 (well under the 172,800/day budget)
Estimated time: ~1–2 minutes
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from collections import defaultdict
from datetime import date, timedelta
from typing import Any

import httpx

from scrapers.chartmetric_deep_us import ENDPOINT_MATRIX, _snap_to_weekday

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [probe] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

CHARTMETRIC_API_BASE = "https://api.chartmetric.com"
CHARTMETRIC_API_KEY = os.environ.get("CHARTMETRIC_API_KEY", "")
# Probe runs at 2s/req (= 0.5 req/sec) — well under Chartmetric's 2 rps limit.
# The first probe at 0.55s/req triggered token-bucket throttling and gave us
# 17 false-positive 429s, masking real tier vs rate-limit distinctions.
REQUEST_DELAY = 2.0

# Drake — used as a known-popular test artist for the demographic probes
TEST_ARTIST_CM_ID = 1932


async def authenticate(client: httpx.AsyncClient) -> str:
    resp = await client.post(
        f"{CHARTMETRIC_API_BASE}/api/token",
        json={"refreshtoken": CHARTMETRIC_API_KEY},
    )
    resp.raise_for_status()
    token = resp.json().get("token")
    if not token:
        raise RuntimeError(f"No token in response: {list(resp.json().keys())}")
    return token


async def call(
    client: httpx.AsyncClient,
    token: str,
    path: str,
    params: dict[str, Any],
) -> tuple[str, int, int, list[dict[str, Any]]]:
    """Returns (status, http_code, item_count, sample_items)."""
    url = f"{CHARTMETRIC_API_BASE}{path}"
    try:
        resp = await client.get(
            url,
            headers={"Authorization": f"Bearer {token}"},
            params=params,
            timeout=20.0,
        )
    except httpx.HTTPError:
        return ("ERROR", 0, 0, [])

    if resp.status_code in (401, 403):
        return ("TIER", resp.status_code, 0, [])
    if resp.status_code == 404:
        return ("NOT_FOUND", 404, 0, [])
    if resp.status_code == 429:
        return ("RATE_LIMITED", 429, 0, [])
    if not (200 <= resp.status_code < 300):
        return ("ERROR", resp.status_code, 0, [])

    try:
        data = resp.json()
    except Exception:
        return ("ERROR", resp.status_code, 0, [])

    items = None
    if isinstance(data, dict):
        obj = data.get("obj")
        if isinstance(obj, dict) and "data" in obj:
            items = obj["data"]
        else:
            for k in ("data", "charts", "tracks", "results", "items", "cities"):
                if k in data and isinstance(data[k], list):
                    items = data[k]
                    break
    elif isinstance(data, list):
        items = data

    if items is None:
        return ("EMPTY", resp.status_code, 0, [])
    sample = items[:2] if items else []
    return ("OK" if items else "EMPTY", resp.status_code, len(items), sample)


async def probe_main() -> None:
    if not CHARTMETRIC_API_KEY:
        logger.error("CHARTMETRIC_API_KEY env var not set")
        sys.exit(1)

    today = date.today()
    yesterday = today - timedelta(days=1)
    last_thursday = _snap_to_weekday(yesterday, "thursday")
    last_friday = _snap_to_weekday(yesterday, "friday")

    async with httpx.AsyncClient(timeout=30) as client:
        logger.info("Authenticating with Chartmetric...")
        token = await authenticate(client)
        logger.info("Authenticated. Probing %d endpoints + cities + artist enrichment...",
                    len(ENDPOINT_MATRIX))
        print()

        # ----- 1. Probe each endpoint once with the right date / params -----

        results: list[dict[str, Any]] = []
        for ep in ENDPOINT_MATRIX:
            target = (
                last_thursday if ep.weekday == "thursday"
                else last_friday if ep.weekday == "friday"
                else yesterday
            )
            params: dict[str, Any] = {"date": target.isoformat()}
            if ep.country_param:
                params[ep.country_param] = ep.country_value
            # For per-genre endpoints, just probe with the FIRST genre value
            if ep.genre_loop and ep.genre_param:
                params[ep.genre_param] = ep.genre_loop[0]
            params.update(ep.params or {})

            status, code, count, _ = await call(client, token, ep.path, params)
            results.append({
                "source": ep.source_platform,
                "type": ep.chart_type,
                "path": ep.path,
                "weekday": ep.weekday or "",
                "confirmed": ep.confirmed,
                "status": status,
                "code": code,
                "count": count,
            })
            await asyncio.sleep(REQUEST_DELAY)

        # ----- 2. Discover US cities (numeric Chartmetric city IDs) -----

        print("Probing /api/cities?country_code=US to discover US city IDs...")
        cities_status, cities_code, cities_count, cities_sample = await call(
            client, token, "/api/cities", {"country_code": "US"}
        )
        await asyncio.sleep(REQUEST_DELAY)

        # Some Chartmetric installations expose this as /api/search?type=cities instead
        if cities_status != "OK":
            cities_status, cities_code, cities_count, cities_sample = await call(
                client, token, "/api/search",
                {"type": "cities", "q": "United States", "limit": 50},
            )
            await asyncio.sleep(REQUEST_DELAY)

        # ----- 3. Probe artist enrichment endpoints -----

        artist_probes = [
            (f"/api/artist/{TEST_ARTIST_CM_ID}",                                {}),
            (f"/api/artist/{TEST_ARTIST_CM_ID}/stat/spotify",                   {}),
            (f"/api/artist/{TEST_ARTIST_CM_ID}/stat/instagram",                 {}),
            (f"/api/artist/{TEST_ARTIST_CM_ID}/stat/tiktok",                    {}),
            (f"/api/artist/{TEST_ARTIST_CM_ID}/stat/youtube",                   {}),
            (f"/api/artist/{TEST_ARTIST_CM_ID}/where-people-listen",            {}),
            (f"/api/artist/{TEST_ARTIST_CM_ID}/instagram-audience",             {}),
            (f"/api/artist/{TEST_ARTIST_CM_ID}/tiktok-audience",                {}),
            (f"/api/artist/{TEST_ARTIST_CM_ID}/youtube-audience",               {}),
            (f"/api/artist/{TEST_ARTIST_CM_ID}/career",                         {}),
            (f"/api/artist/{TEST_ARTIST_CM_ID}/relatedartists",                 {"limit": 10}),
        ]
        artist_results: list[dict[str, Any]] = []
        for path, params in artist_probes:
            status, code, count, _ = await call(client, token, path, params)
            artist_results.append({"path": path, "status": status, "code": code, "count": count})
            await asyncio.sleep(REQUEST_DELAY)

        # ----- 4. Test the /artist/list filtered crawl -----

        list_status, list_code, list_count, list_sample = await call(
            client, token, "/api/artist/list",
            {
                "code2": "US",
                "sortColumn": "sp_monthly_listeners",
                "sortOrderDesc": "true",
                "limit": 100,
                "offset": 0,
            },
        )

    # ----- REPORT -----

    print("\n" + "=" * 86)
    print("CHARTMETRIC API PROBE REPORT")
    print("=" * 86)
    print(f"\nTested dates: yesterday={yesterday}  thursday={last_thursday}  friday={last_friday}")

    print(f"\n--- Chart endpoints ({len(results)} probed) ---")
    print(f"{'SRC':<13} {'TYPE':<32} {'WKDY':<10} {'CNF':<5} {'STATUS':<13} {'CODE':<5} {'ITEMS':<6}")
    print("-" * 86)
    for r in sorted(results, key=lambda x: (x["source"], x["type"])):
        flag = "y" if r["confirmed"] else "?"
        print(f"{r['source']:<13} {r['type']:<32} {r['weekday']:<10} {flag:<5} "
              f"{r['status']:<13} {str(r['code']):<5} {r['count']:<6}")

    by_status: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in results:
        by_status[r["status"]].append(r)
    print("\nSummary:")
    for status, items in sorted(by_status.items()):
        print(f"  {status:<14} {len(items):>4} endpoints")

    confirmed_failing = [r for r in results if r["confirmed"] and r["status"] != "OK"]
    if confirmed_failing:
        print(f"\n  ! {len(confirmed_failing)} confirmed endpoints not returning OK — investigate:")
        for r in confirmed_failing:
            print(f"    - {r['source']}/{r['type']}: {r['status']} ({r['code']})")

    speculative_ok = [r for r in results if not r["confirmed"] and r["status"] == "OK"]
    if speculative_ok:
        print(f"\n  + {len(speculative_ok)} speculative endpoints worked — promote to confirmed=True:")
        for r in speculative_ok:
            print(f"    - {r['source']}/{r['type']}")

    print(f"\n--- US cities discovery ---")
    print(f"  /api/cities?country_code=US -> {cities_status} ({cities_code}), {cities_count} cities")
    if cities_status == "OK" and cities_sample:
        print("  First 2 sample entries:")
        for c in cities_sample[:2]:
            cid = c.get("id") or c.get("city_id") or c.get("cm_city")
            cname = c.get("name") or c.get("city_name") or c.get("city")
            cstate = c.get("state_code") or c.get("state") or ""
            print(f"    id={cid}  name={cname}  state={cstate}")
        print(f"\n  -> Persist these city IDs and pass them as `city_id` to /charts/applemusic/tracks")
        print(f"    and /city/{{id}}/tracks for per-city US pulls.")

    print(f"\n--- Artist enrichment probes (test artist cm_id={TEST_ARTIST_CM_ID}) ---")
    print(f"{'PATH':<60} {'STATUS':<14} {'CODE':<5}")
    print("-" * 86)
    for r in artist_results:
        print(f"{r['path']:<60} {r['status']:<14} {str(r['code']):<5}")
    audience_paths = [r for r in artist_results if "audience" in r["path"]]
    audience_unlocked = [r for r in audience_paths if r["status"] == "OK"]
    if audience_paths and not audience_unlocked:
        print("\n  ! Audience-demographic endpoints all returned non-OK — likely a paid add-on.")
        print("    Email Chartmetric support to confirm tier access if you want them.")
    elif audience_unlocked:
        print(f"\n  + Audience-demographic endpoints unlocked ({len(audience_unlocked)}/{len(audience_paths)}).")

    print(f"\n--- /api/artist/list filtered crawl ---")
    print(f"  /api/artist/list?code2=US&sortColumn=sp_monthly_listeners&limit=100  -> "
          f"{list_status} ({list_code}), {list_count} artists")
    if list_status == "OK":
        print("  -> Use this to crawl every US artist by monthly listeners — paginate offset by 100.")

    print("\n" + "=" * 86)
    print("Next steps:")
    print("  1. Promote speculative-OK endpoints in scrapers/chartmetric_deep_us.py")
    print("  2. Persist the discovered US city IDs (a follow-up task adds them to ENDPOINT_MATRIX)")
    print("  3. Run scripts/backfill_chartmetric_deep_us.py --confirmed-only --days 730")
    print("=" * 86 + "\n")


if __name__ == "__main__":
    asyncio.run(probe_main())
