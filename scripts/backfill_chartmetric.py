"""
Backfill historical chart data from Chartmetric.

Pulls 90 days of daily Spotify and Shazam chart data and ingests it into
SoundPulse via the admin API. This builds the historical dataset needed
to train the prediction model without waiting 8+ weeks.

Usage (from inside Docker container):
    python scripts/backfill_chartmetric.py

Or from host:
    docker exec soundpulse-api-1 python scripts/backfill_chartmetric.py

Estimated time: ~15 minutes for 90 days × 4 chart types.
Estimated API calls: ~720 (well within 170k/day paid tier limit).
"""

import asyncio
import logging
import os
import sys
from datetime import date, timedelta
from typing import Any

import httpx

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [backfill] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# --- Config ---
CHARTMETRIC_API_BASE = "https://api.chartmetric.com"
SOUNDPULSE_API_BASE = os.environ.get("SOUNDPULSE_API_URL", "http://localhost:8000")
ADMIN_KEY = os.environ.get("API_ADMIN_KEY", "")
if not ADMIN_KEY:
    logger.error("API_ADMIN_KEY env var is required; refusing to fall back to a hardcoded default")
    sys.exit(1)
CHARTMETRIC_API_KEY = os.environ.get("CHARTMETRIC_API_KEY", "")

BACKFILL_DAYS = 90
RATE_LIMIT_DELAY = 1.0  # seconds between Chartmetric requests
INGEST_DELAY = 0.1  # seconds between SoundPulse ingest calls

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
    """Exchange refresh token for bearer token."""
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
) -> list[dict[str, Any]]:
    """Fetch a single chart for a given date."""
    url = f"{CHARTMETRIC_API_BASE}{endpoint['path']}"
    params = {"date": chart_date, "country_code": "us"}
    params.update(endpoint.get("params", {}))

    resp = await client.get(
        url,
        headers={"Authorization": f"Bearer {token}"},
        params=params,
    )

    if resp.status_code == 429:
        retry_after = max(2, int(float(resp.headers.get("Retry-After", 5))))
        logger.warning("Rate limited, waiting %ds", retry_after)
        await asyncio.sleep(retry_after)
        # Retry once
        resp = await client.get(
            url,
            headers={"Authorization": f"Bearer {token}"},
            params=params,
        )

    if resp.status_code != 200:
        logger.warning("Chart %s %s on %s: HTTP %d", endpoint["source_platform"], endpoint["chart_type"], chart_date, resp.status_code)
        return []

    data = resp.json()
    obj = data.get("obj", {})
    if isinstance(obj, dict) and "data" in obj:
        return obj["data"]
    return []


def parse_entry(entry: dict[str, Any], source_platform: str, chart_type: str, snapshot_date: str) -> dict | None:
    """Parse a chart entry into SoundPulse ingest format."""
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
    """Post records to SoundPulse API. Returns (created, duplicates, errors)."""
    created = 0
    duplicates = 0
    errors = 0

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
                duplicates += 1
            else:
                errors += 1
            await asyncio.sleep(INGEST_DELAY)
        except Exception as e:
            errors += 1
            logger.debug("Ingest error: %s", e)

    return created, duplicates, errors


async def backfill():
    """Main backfill loop."""
    if not CHARTMETRIC_API_KEY:
        logger.error("CHARTMETRIC_API_KEY not set")
        sys.exit(1)

    today = date.today()
    dates = [(today - timedelta(days=i)).isoformat() for i in range(1, BACKFILL_DAYS + 1)]
    dates.reverse()  # oldest first

    logger.info("Starting backfill: %d days × %d charts = %d API calls",
                len(dates), len(CHART_ENDPOINTS), len(dates) * len(CHART_ENDPOINTS))
    logger.info("Date range: %s to %s", dates[0], dates[-1])

    async with httpx.AsyncClient(timeout=30) as client:
        token = await authenticate(client)
        logger.info("Authenticated with Chartmetric")

        total_created = 0
        total_duplicates = 0
        total_errors = 0
        total_empty = 0

        for day_idx, chart_date in enumerate(dates):
            day_records = []

            for endpoint in CHART_ENDPOINTS:
                await asyncio.sleep(RATE_LIMIT_DELAY)

                entries = await fetch_chart(client, token, endpoint, chart_date)

                if not entries:
                    total_empty += 1
                    continue

                for entry in entries:
                    record = parse_entry(entry, endpoint["source_platform"], endpoint["chart_type"], chart_date)
                    if record:
                        day_records.append(record)

            if day_records:
                created, dupes, errs = await ingest_batch(client, day_records)
                total_created += created
                total_duplicates += dupes
                total_errors += errs

                logger.info(
                    "Day %d/%d [%s]: %d records → %d created, %d dupes, %d errors",
                    day_idx + 1, len(dates), chart_date,
                    len(day_records), created, dupes, errs,
                )
            else:
                logger.info("Day %d/%d [%s]: no data available", day_idx + 1, len(dates), chart_date)

            # Re-authenticate every 30 days to avoid token expiry
            if (day_idx + 1) % 30 == 0:
                token = await authenticate(client)
                logger.info("Re-authenticated")

        logger.info("=" * 60)
        logger.info("BACKFILL COMPLETE")
        logger.info("  Days processed: %d", len(dates))
        logger.info("  Empty chart responses: %d", total_empty)
        logger.info("  Records created: %d", total_created)
        logger.info("  Duplicates skipped: %d", total_duplicates)
        logger.info("  Errors: %d", total_errors)
        logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(backfill())
