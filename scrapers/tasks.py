"""
Celery tasks for SoundPulse scraper jobs.
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone

from scrapers.celery_app import app

logger = logging.getLogger(__name__)


def _get_credentials() -> dict:
    """Load credentials from environment."""
    from dotenv import load_dotenv
    load_dotenv()
    return {
        "spotify_client_id": os.environ.get("SPOTIFY_CLIENT_ID", ""),
        "spotify_client_secret": os.environ.get("SPOTIFY_CLIENT_SECRET", ""),
        "chartmetric_api_key": os.environ.get("CHARTMETRIC_API_KEY", ""),
        "shazam_rapidapi_key": os.environ.get("SHAZAM_RAPIDAPI_KEY", ""),
        "apple_music_team_id": os.environ.get("APPLE_MUSIC_TEAM_ID", ""),
        "apple_music_key_id": os.environ.get("APPLE_MUSIC_KEY_ID", ""),
        "apple_music_private_key_path": os.environ.get("APPLE_MUSIC_PRIVATE_KEY_PATH", ""),
        "tiktok_client_key": os.environ.get("TIKTOK_CLIENT_KEY", ""),
        "tiktok_client_secret": os.environ.get("TIKTOK_CLIENT_SECRET", ""),
    }


def _get_api_config() -> tuple[str, str]:
    """Return (api_base_url, admin_key)."""
    api_url = os.environ.get("SOUNDPULSE_API_URL", "http://localhost:8000")
    admin_key = os.environ.get("API_ADMIN_KEY", "")
    return api_url, admin_key


def _update_scraper_status(scraper_id: str, status: str, error: str | None = None):
    """Update scraper config in DB via API."""
    # This is a fire-and-forget update
    import httpx
    api_url, admin_key = _get_api_config()
    try:
        with httpx.Client(timeout=10) as client:
            client.put(
                f"{api_url}/api/v1/admin/scraper-config/{scraper_id}",
                json={"last_status": status, "last_error": error},
                headers={"X-API-Key": admin_key},
            )
    except Exception:
        pass  # non-critical


async def _run_scraper_async(scraper_id: str) -> dict:
    """Run a single scraper or fallback chain."""
    credentials = _get_credentials()
    api_url, admin_key = _get_api_config()

    # Try fallback chain first
    from scrapers.fallback import build_chains
    chains = build_chains(credentials, api_url, admin_key)

    if scraper_id in chains:
        data_points, quality, stats = await chains[scraper_id].run()
        return {**stats, "quality": quality.value}

    # Direct scraper for scrapers not in chains (e.g. musicbrainz)
    scraper = None
    if scraper_id == "musicbrainz":
        from scrapers.musicbrainz import MusicBrainzEnricher
        scraper = MusicBrainzEnricher(credentials={}, api_base_url=api_url, admin_key=admin_key)

    if scraper:
        try:
            stats = await scraper.run()
            return stats
        finally:
            await scraper.close()

    raise ValueError(f"Unknown scraper: {scraper_id}")


@app.task(name="scrapers.tasks.run_scraper", bind=True, max_retries=1)
def run_scraper(self, scraper_id: str):
    """Run a scraper via Celery. Wraps async code."""
    logger.info("Starting scraper: %s", scraper_id)
    _update_scraper_status(scraper_id, "running")

    try:
        loop = asyncio.new_event_loop()
        stats = loop.run_until_complete(_run_scraper_async(scraper_id))
        loop.close()

        _update_scraper_status(scraper_id, "success")
        logger.info("Scraper %s completed: %s", scraper_id, stats)
        return stats
    except Exception as e:
        error_msg = str(e)[:2000]
        _update_scraper_status(scraper_id, "error", error_msg)
        logger.exception("Scraper %s failed", scraper_id)
        raise


@app.task(name="scrapers.tasks.health_check")
def health_check():
    """Run health check on all scrapers."""
    try:
        from scrapers.health import check_all_scrapers
        loop = asyncio.new_event_loop()
        result = loop.run_until_complete(check_all_scrapers())
        loop.close()
        logger.info("Health check: %s", result)
        return result
    except Exception as e:
        logger.exception("Health check failed")
        return {"error": str(e)}
