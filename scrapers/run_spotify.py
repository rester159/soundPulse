"""
Run the Spotify scraper manually.

Usage:
    python -m scrapers.run_spotify [--dry-run]
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys

from dotenv import load_dotenv

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def main(dry_run: bool = False):
    load_dotenv()

    client_id = os.environ.get("SPOTIFY_CLIENT_ID", "")
    client_secret = os.environ.get("SPOTIFY_CLIENT_SECRET", "")
    api_url = os.environ.get("SOUNDPULSE_API_URL", "http://localhost:8000")
    # Generality principle: do NOT fall back to the documented default
    # admin key. Require it via env var. If missing, fail loudly.
    admin_key = os.environ.get("API_ADMIN_KEY", "")

    if not client_id or not client_secret:
        logger.error("SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET must be set")
        sys.exit(1)
    if not admin_key:
        logger.error("API_ADMIN_KEY env var is required; refusing to use a hardcoded default")
        sys.exit(1)

    from scrapers.spotify import SpotifyScraper

    scraper = SpotifyScraper(
        credentials={"client_id": client_id, "client_secret": client_secret},
        api_base_url=api_url,
        admin_key=admin_key,
    )

    try:
        if dry_run:
            await scraper.authenticate()
            data_points = await scraper.collect_trending()
            logger.info("DRY RUN: Would ingest %d data points", len(data_points))
            for dp in data_points[:5]:
                logger.info("  %s %s: %s (score=%.2f)", dp.entity_type, dp.entity_identifier.get("title") or dp.entity_identifier.get("artist_name"), dp.platform, dp.raw_score or 0)
        else:
            stats = await scraper.run()
            logger.info("Done. Stats: %s", stats)
    finally:
        await scraper.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the SoundPulse Spotify scraper")
    parser.add_argument("--dry-run", action="store_true", help="Collect data but don't ingest")
    args = parser.parse_args()
    asyncio.run(main(dry_run=args.dry_run))
