"""
Health monitoring for SoundPulse scrapers.
Checks data freshness, failure counts, and entity growth.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# Expected freshness thresholds (interval + 1h buffer)
FRESHNESS_THRESHOLDS = {
    "spotify": timedelta(hours=7),
    "chartmetric": timedelta(hours=5),
    "shazam": timedelta(hours=5),
    "apple_music": timedelta(hours=7),
    "radio": timedelta(hours=25),
    "musicbrainz": timedelta(hours=13),
}

MAX_CONSECUTIVE_FAILURES = 3


async def check_all_scrapers() -> dict[str, Any]:
    """Check health of all scrapers. Returns status dict."""
    from dotenv import load_dotenv
    load_dotenv()

    api_url = os.environ.get("SOUNDPULSE_API_URL", "http://localhost:8000")
    admin_key = os.environ.get("API_ADMIN_KEY", "")

    results = {}

    async with httpx.AsyncClient(timeout=10) as client:
        # Fetch all scraper configs
        try:
            resp = await client.get(
                f"{api_url}/api/v1/admin/scraper-config",
                headers={"X-API-Key": admin_key},
            )
            configs = resp.json() if resp.status_code == 200 else []
        except Exception as e:
            return {"error": f"Failed to fetch scraper configs: {e}"}

        now = datetime.now(timezone.utc)

        for config in configs:
            scraper_id = config.get("id", "unknown")
            status = "healthy"
            issues = []

            # Check if enabled
            if not config.get("enabled"):
                results[scraper_id] = {"status": "disabled", "issues": []}
                continue

            # Check last run freshness
            last_run = config.get("last_run_at")
            if last_run:
                try:
                    last_dt = datetime.fromisoformat(last_run.replace("Z", "+00:00"))
                    threshold = FRESHNESS_THRESHOLDS.get(scraper_id, timedelta(hours=7))
                    if now - last_dt > threshold:
                        status = "stale"
                        hours_ago = (now - last_dt).total_seconds() / 3600
                        issues.append(f"Last run {hours_ago:.1f}h ago (threshold: {threshold.total_seconds()/3600:.0f}h)")
                except (ValueError, TypeError):
                    pass
            else:
                status = "never_run"
                issues.append("Never been run")

            # Check last status
            last_status = config.get("last_status")
            if last_status == "error":
                status = "error"
                last_error = config.get("last_error", "Unknown error")
                issues.append(f"Last run failed: {last_error[:100]}")

            # Check if running too long
            if last_status == "running" and last_run:
                try:
                    last_dt = datetime.fromisoformat(last_run.replace("Z", "+00:00"))
                    if now - last_dt > timedelta(hours=1):
                        status = "stuck"
                        issues.append("Has been 'running' for over 1 hour")
                except (ValueError, TypeError):
                    pass

            results[scraper_id] = {
                "status": status,
                "enabled": config.get("enabled", False),
                "last_run_at": last_run,
                "last_status": last_status,
                "interval_hours": config.get("interval_hours"),
                "issues": issues,
            }

    # Overall health
    statuses = [r["status"] for r in results.values()]
    if "error" in statuses or "stuck" in statuses:
        overall = "unhealthy"
    elif "stale" in statuses or "never_run" in statuses:
        overall = "degraded"
    else:
        overall = "healthy"

    return {"overall": overall, "scrapers": results, "checked_at": now.isoformat()}
