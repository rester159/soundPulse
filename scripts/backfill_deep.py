"""
Deep historical backfill from Chartmetric — 2 years of daily chart data.

This builds the full training dataset for the prediction model. With 2 years
of history, we can train the model on "what did charts look like N days before
a breakout?" and validate against what actually happened.

Usage:
    docker exec soundpulse-api-1 python scripts/backfill_deep.py
    docker exec soundpulse-api-1 python scripts/backfill_deep.py --days 365
    docker exec soundpulse-api-1 python scripts/backfill_deep.py --start 2024-01-01 --end 2026-04-01

Estimated time: ~2-4 hours for 730 days (depends on API response times).
Estimated API calls: ~2,920 Chartmetric + ~255k SoundPulse ingest.
"""

import argparse
import asyncio
import logging
import os
import sys
from datetime import date, datetime, timedelta
from typing import Any

import httpx

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [deep-backfill] %(message)s",
    datefmt="%H:%M:%S",
)
# Suppress httpx request logging to keep output clean
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

# --- Config ---
CHARTMETRIC_API_BASE = "https://api.chartmetric.com"
SOUNDPULSE_API_BASE = os.environ.get("SOUNDPULSE_API_URL", "http://localhost:8000")
ADMIN_KEY = os.environ.get("API_ADMIN_KEY", "")
if not ADMIN_KEY:
    logger.error("API_ADMIN_KEY env var is required; refusing to fall back to a hardcoded default")
    sys.exit(1)
CHARTMETRIC_API_KEY = os.environ.get("CHARTMETRIC_API_KEY", "")

# Delays tuned for paid tier (2 req/sec)
CM_REQUEST_DELAY = 0.6  # seconds between Chartmetric API calls
INGEST_DELAY = 0.05  # seconds between SoundPulse ingest calls (fast — it's local)
TOKEN_REFRESH_INTERVAL = 25  # re-auth every N days processed

# NOTE: /api/charts/spotify accepts type ∈ {regional, viral} only.
# The `plays` entry that used to be here has been removed (P1-069 / L001) —
# it's not a valid value and was silently failing for months.
CHART_ENDPOINTS = [
    {
        "source_platform": "spotify",
        "chart_type": "regional",
        "path": "/api/charts/spotify",
        "params": {"type": "regional", "interval": "daily"},
    },
    {
        "source_platform": "spotify",
        "chart_type": "viral",
        "path": "/api/charts/spotify",
        "params": {"type": "viral", "interval": "daily"},
    },
    {
        "source_platform": "shazam",
        "chart_type": "top",
        "path": "/api/charts/shazam",
        "params": {},
    },
]


async def authenticate(client: httpx.AsyncClient) -> str:
    resp = await client.post(
        f"{CHARTMETRIC_API_BASE}/api/token",
        json={"refreshtoken": CHARTMETRIC_API_KEY},
    )
    resp.raise_for_status()
    token = resp.json().get("token")
    if not token:
        raise RuntimeError(f"No token in auth response: {resp.json().keys()}")
    return token


async def fetch_chart(
    client: httpx.AsyncClient,
    token: str,
    endpoint: dict[str, Any],
    chart_date: str,
    max_retries: int = 3,
) -> list[dict[str, Any]]:
    url = f"{CHARTMETRIC_API_BASE}{endpoint['path']}"
    params = {"date": chart_date, "country_code": "us"}
    params.update(endpoint.get("params", {}))

    for attempt in range(max_retries):
        try:
            resp = await client.get(
                url,
                headers={"Authorization": f"Bearer {token}"},
                params=params,
            )

            if resp.status_code == 429:
                retry_after = max(2, int(float(resp.headers.get("Retry-After", 3))))
                logger.debug("Rate limited, waiting %ds (attempt %d)", retry_after, attempt + 1)
                await asyncio.sleep(retry_after)
                continue

            if resp.status_code == 401:
                logger.debug("401 for %s %s — endpoint may not be in plan",
                             endpoint["source_platform"], endpoint["chart_type"])
                return []

            if resp.status_code != 200:
                logger.debug("HTTP %d for %s on %s", resp.status_code, endpoint["source_platform"], chart_date)
                return []

            data = resp.json()
            obj = data.get("obj", {})
            if isinstance(obj, dict) and "data" in obj:
                return obj["data"]
            return []

        except (httpx.ReadTimeout, httpx.ConnectError) as e:
            logger.debug("Network error (attempt %d): %s", attempt + 1, e)
            await asyncio.sleep(2 * (attempt + 1))

    return []


def parse_entry(entry: dict, source_platform: str, chart_type: str, snapshot_date: str) -> dict | None:
    cm_track_id = entry.get("cm_track") or entry.get("cm_track_id") or entry.get("id")
    name = entry.get("name") or entry.get("title") or entry.get("track_name")

    artist_names = entry.get("artist_names") or entry.get("artist_name") or entry.get("artist")
    if isinstance(artist_names, list):
        artist_name = ", ".join(artist_names)
    else:
        artist_name = artist_names

    rank = entry.get("rank") or entry.get("position") or entry.get("chart_position")

    if not name:
        return None

    entity_identifier = {
        "title": name,
        "artist_name": artist_name or "Unknown",
    }

    if entry.get("spotify_track_id"):
        entity_identifier["spotify_id"] = entry["spotify_track_id"]
    elif entry.get("spotify_id"):
        entity_identifier["spotify_id"] = entry["spotify_id"]
    if entry.get("isrc"):
        entity_identifier["isrc"] = entry["isrc"]
    if cm_track_id:
        entity_identifier["chartmetric_id"] = cm_track_id

    try:
        rank_int = int(float(rank)) if rank is not None else None
    except (ValueError, TypeError):
        rank_int = None

    spotify_popularity = entry.get("spotify_popularity")
    if spotify_popularity is not None:
        raw_score = float(spotify_popularity)
    elif rank_int is not None:
        raw_score = max(0.0, 200.0 - rank_int)
    else:
        raw_score = None

    return {
        "platform": "chartmetric",
        "entity_type": "track",
        "entity_identifier": entity_identifier,
        "raw_score": raw_score,
        "rank": rank_int,
        "signals": {
            "chart_type": chart_type,
            "source_platform": source_platform,
            "cm_track_id": cm_track_id,
            "source_rank": rank_int,
            "spotify_popularity": spotify_popularity,
            "velocity": entry.get("velocity"),
            "current_plays": entry.get("current_plays"),
            "genres": entry.get("track_genre") or entry.get("genre"),
        },
        "snapshot_date": snapshot_date,
    }


async def ingest_batch(client: httpx.AsyncClient, records: list[dict]) -> tuple[int, int, int]:
    created = dupes = errors = 0
    for record in records:
        try:
            resp = await client.post(
                f"{SOUNDPULSE_API_BASE}/api/v1/trending",
                json=record,
                headers={"X-API-Key": ADMIN_KEY},
            )
            if resp.status_code == 201:
                created += 1
            elif resp.status_code == 409:
                dupes += 1
            else:
                errors += 1
            await asyncio.sleep(INGEST_DELAY)
        except Exception:
            errors += 1
    return created, dupes, errors


async def backfill(start_date: date, end_date: date):
    if not CHARTMETRIC_API_KEY:
        logger.error("CHARTMETRIC_API_KEY not set")
        sys.exit(1)

    # Build date list (oldest first)
    dates = []
    current = start_date
    while current <= end_date:
        dates.append(current.isoformat())
        current += timedelta(days=1)

    total_days = len(dates)
    total_api_calls = total_days * len(CHART_ENDPOINTS)
    est_records = total_days * 350
    est_minutes = (total_api_calls * CM_REQUEST_DELAY + est_records * INGEST_DELAY) / 60

    logger.info("=" * 60)
    logger.info("DEEP BACKFILL")
    logger.info("  Date range: %s to %s (%d days)", dates[0], dates[-1], total_days)
    logger.info("  Chart endpoints: %d", len(CHART_ENDPOINTS))
    logger.info("  Estimated API calls: %d Chartmetric + ~%dk ingest", total_api_calls, est_records // 1000)
    logger.info("  Estimated time: ~%.0f minutes", est_minutes)
    logger.info("=" * 60)

    async with httpx.AsyncClient(timeout=30) as client:
        token = await authenticate(client)
        logger.info("Authenticated with Chartmetric")

        grand_created = 0
        grand_dupes = 0
        grand_errors = 0
        grand_empty = 0
        start_time = asyncio.get_event_loop().time()

        for day_idx, chart_date in enumerate(dates):
            day_records = []

            for endpoint in CHART_ENDPOINTS:
                await asyncio.sleep(CM_REQUEST_DELAY)
                entries = await fetch_chart(client, token, endpoint, chart_date)

                if not entries:
                    grand_empty += 1
                    continue

                for entry in entries:
                    record = parse_entry(entry, endpoint["source_platform"], endpoint["chart_type"], chart_date)
                    if record:
                        day_records.append(record)

            if day_records:
                created, dupes, errs = await ingest_batch(client, day_records)
                grand_created += created
                grand_dupes += dupes
                grand_errors += errs

            # Progress every 10 days
            if (day_idx + 1) % 10 == 0 or day_idx == total_days - 1:
                elapsed = asyncio.get_event_loop().time() - start_time
                rate = (day_idx + 1) / elapsed * 60 if elapsed > 0 else 0
                remaining = (total_days - day_idx - 1) / rate if rate > 0 else 0
                logger.info(
                    "Progress: %d/%d days (%.0f%%) | %d created, %d dupes | "
                    "%.1f days/min | ~%.0f min remaining",
                    day_idx + 1, total_days, (day_idx + 1) / total_days * 100,
                    grand_created, grand_dupes, rate, remaining,
                )

            # Re-authenticate periodically
            if (day_idx + 1) % TOKEN_REFRESH_INTERVAL == 0:
                try:
                    token = await authenticate(client)
                except Exception:
                    logger.warning("Re-auth failed, continuing with existing token")

        elapsed_total = asyncio.get_event_loop().time() - start_time

        logger.info("=" * 60)
        logger.info("BACKFILL COMPLETE")
        logger.info("  Days processed: %d", total_days)
        logger.info("  Records created: %d", grand_created)
        logger.info("  Duplicates skipped: %d", grand_dupes)
        logger.info("  Errors: %d", grand_errors)
        logger.info("  Empty responses: %d", grand_empty)
        logger.info("  Total time: %.1f minutes", elapsed_total / 60)
        logger.info("=" * 60)


def parse_args():
    parser = argparse.ArgumentParser(description="Deep historical backfill from Chartmetric")
    parser.add_argument("--days", type=int, default=730, help="Number of days to backfill (default: 730 = 2 years)")
    parser.add_argument("--start", type=str, help="Start date (YYYY-MM-DD). Overrides --days.")
    parser.add_argument("--end", type=str, help="End date (YYYY-MM-DD). Default: yesterday.")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    end = datetime.strptime(args.end, "%Y-%m-%d").date() if args.end else date.today() - timedelta(days=1)

    if args.start:
        start = datetime.strptime(args.start, "%Y-%m-%d").date()
    else:
        start = end - timedelta(days=args.days - 1)

    asyncio.run(backfill(start, end))
