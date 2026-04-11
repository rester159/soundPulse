"""
Deep US Chartmetric historical backfill — exhausts the paid-tier API.

Pulls every endpoint in `scrapers.chartmetric_deep_us.ENDPOINT_MATRIX`
across a date range, using the bulk-ingest endpoint for fast loading.

Usage:
    docker exec soundpulse-api-1 python scripts/backfill_chartmetric_deep_us.py
    docker exec soundpulse-api-1 python scripts/backfill_chartmetric_deep_us.py --days 365
    docker exec soundpulse-api-1 python scripts/backfill_chartmetric_deep_us.py --start 2024-01-01 --end 2026-04-01

Flags:
    --days N              Number of days to backfill (default: 730 = 2 years)
    --start YYYY-MM-DD    Start date (overrides --days)
    --end YYYY-MM-DD      End date (default: yesterday)
    --confirmed-only      Only run confirmed endpoints (skip speculative)

Estimated cost (730 days × ~6 confirmed endpoints):
    ~4,400 Chartmetric API calls
    ~12 hours at 0.55s/req (~1.8 req/sec, just under the 2 rps limit)
    ~880,000 chart entries before dedup
    ~250,000 unique tracks after dedup (estimate)

Memory-bounded: scraper flushes the bulk buffer every 500 records and on
each 5-day checkpoint.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from datetime import date, datetime, timedelta

from scrapers.chartmetric_deep_us import ChartmetricDeepUSScraper, ENDPOINT_MATRIX

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [deep-us-backfill] %(message)s",
    datefmt="%H:%M:%S",
)
# Quiet noisy libraries
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Deep US Chartmetric historical backfill")
    p.add_argument("--days", type=int, default=730,
                   help="Number of days to backfill (default: 730 = 2 years)")
    p.add_argument("--start", type=str,
                   help="Start date YYYY-MM-DD (overrides --days)")
    p.add_argument("--end", type=str,
                   help="End date YYYY-MM-DD (default: yesterday)")
    p.add_argument("--confirmed-only", action="store_true",
                   help="Only run confirmed endpoints (skip speculative)")
    return p.parse_args()


async def main() -> None:
    args = parse_args()

    cm_key = os.environ.get("CHARTMETRIC_API_KEY")
    api_admin_key = os.environ.get("API_ADMIN_KEY")
    api_base = os.environ.get("SOUNDPULSE_API_URL", "http://localhost:8000")

    if not cm_key:
        logger.error("CHARTMETRIC_API_KEY env var not set")
        sys.exit(1)
    if not api_admin_key:
        logger.error("API_ADMIN_KEY env var not set")
        sys.exit(1)

    end = datetime.strptime(args.end, "%Y-%m-%d").date() if args.end else (date.today() - timedelta(days=1))
    if args.start:
        start = datetime.strptime(args.start, "%Y-%m-%d").date()
    else:
        start = end - timedelta(days=args.days - 1)

    if args.confirmed_only:
        # Mutate the matrix in place: skip speculative entries
        global ENDPOINT_MATRIX
        ENDPOINT_MATRIX = [ep for ep in ENDPOINT_MATRIX if ep.confirmed]
        # Also patch the imported reference inside the scraper module
        import scrapers.chartmetric_deep_us as deep_mod
        deep_mod.ENDPOINT_MATRIX = ENDPOINT_MATRIX

    days = (end - start).days + 1
    n_endpoints = len([e for e in ENDPOINT_MATRIX if not e.requires_city])
    est_calls = days * n_endpoints
    est_minutes = est_calls * 0.55 / 60

    logger.info("=" * 70)
    logger.info("DEEP US CHARTMETRIC BACKFILL")
    logger.info("  Date range:    %s to %s (%d days)", start, end, days)
    logger.info("  Endpoints:     %d (%s)", n_endpoints,
                "confirmed only" if args.confirmed_only else "confirmed + speculative")
    logger.info("  Est. API calls: %d", est_calls)
    logger.info("  Est. duration:  %.0f minutes (~%.1f hours)", est_minutes, est_minutes / 60)
    logger.info("  Bulk batch size: 500 records/POST")
    logger.info("=" * 70)

    scraper = ChartmetricDeepUSScraper(
        credentials={"api_key": cm_key},
        api_base_url=api_base,
        admin_key=api_admin_key,
    )

    try:
        totals = await scraper.backfill(start, end)
        logger.info("=" * 70)
        logger.info("BACKFILL COMPLETE")
        logger.info("  Endpoints touched: %d", totals["endpoints"])
        logger.info("  Total API calls:   %d", totals["total_calls"])
        logger.info("  Entries pulled:    %d", totals["total_entries"])
        logger.info("  Empty responses:   %d", totals["total_empty"])
        logger.info("  Errors:            %d", totals["total_errors"])
        logger.info("=" * 70)

        # Per-endpoint detail
        per_ep = scraper.per_endpoint_stats()
        logger.info("\nPer-endpoint breakdown:")
        for key in sorted(per_ep.keys()):
            s = per_ep[key]
            logger.info("  %-40s calls=%-5d entries=%-7d empty=%-3d errors=%-3d",
                        key, s["calls"], s["entries"], s["empty"], s["errors"])
    finally:
        await scraper.close()


if __name__ == "__main__":
    asyncio.run(main())
