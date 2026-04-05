"""
Fallback chain for scraper resilience.
Tries scrapers in order, tags data with quality level.
"""
from __future__ import annotations

import logging
from enum import Enum
from typing import Any

from scrapers.base import BaseScraper, RawDataPoint

logger = logging.getLogger(__name__)


class DataQuality(Enum):
    LIVE = "live"          # Direct API access
    AGGREGATED = "aggregated"  # Via aggregator like Chartmetric
    SCRAPED = "scraped"    # Web scraping
    CACHED = "cached"      # Stale cached data


class FallbackChain:
    """
    Try multiple data sources for a platform in priority order.
    First successful source wins. Tags data with quality level.
    """

    def __init__(
        self,
        platform: str,
        chain: list[tuple[BaseScraper, DataQuality]],
    ):
        self.platform = platform
        self.chain = chain

    async def run(self) -> tuple[list[RawDataPoint], DataQuality, dict[str, int]]:
        """
        Run the fallback chain. Returns (data_points, quality_level, stats).
        Tries each source in order. First to return data wins.
        """
        for scraper, quality in self.chain:
            try:
                logger.info("[fallback:%s] Trying %s (quality=%s)", self.platform, type(scraper).__name__, quality.value)
                await scraper.authenticate()
                data_points = await scraper.collect_trending()

                if not data_points:
                    logger.warning("[fallback:%s] %s returned 0 data points, trying next", self.platform, type(scraper).__name__)
                    await scraper.close()
                    continue

                # Tag each data point with quality level
                for point in data_points:
                    point.signals["data_quality"] = quality.value
                    point.signals["data_source"] = type(scraper).__name__

                # Ingest the data
                stats = {"success": 0, "failed": 0, "skipped": 0, "total": len(data_points)}
                for point in data_points:
                    try:
                        result = await scraper._post_to_api(point)
                        if result == "created":
                            stats["success"] += 1
                        else:
                            stats["skipped"] += 1
                    except Exception as e:
                        logger.error("[fallback:%s] Ingest failed: %s", self.platform, e)
                        stats["failed"] += 1

                await scraper.close()
                logger.info("[fallback:%s] Success via %s: %s", self.platform, type(scraper).__name__, stats)
                return data_points, quality, stats

            except Exception as e:
                logger.warning("[fallback:%s] %s failed: %s, trying next", self.platform, type(scraper).__name__, e)
                try:
                    await scraper.close()
                except Exception:
                    pass
                continue

        logger.error("[fallback:%s] All sources failed", self.platform)
        return [], DataQuality.CACHED, {"success": 0, "failed": 0, "skipped": 0, "total": 0}


def build_chains(credentials: dict, api_base_url: str, admin_key: str) -> dict[str, FallbackChain]:
    """Build fallback chains for all platforms using available credentials."""
    from scrapers.spotify import SpotifyScraper

    chains = {}

    # Spotify chain
    if credentials.get("spotify_client_id"):
        spotify = SpotifyScraper(
            credentials={"client_id": credentials["spotify_client_id"], "client_secret": credentials.get("spotify_client_secret", "")},
            api_base_url=api_base_url, admin_key=admin_key,
        )
        chain_items = [(spotify, DataQuality.LIVE)]

        # If Chartmetric is available, add as fallback
        if credentials.get("chartmetric_api_key"):
            from scrapers.chartmetric import ChartmetricScraper
            cm = ChartmetricScraper(
                credentials={"api_key": credentials["chartmetric_api_key"]},
                api_base_url=api_base_url, admin_key=admin_key,
            )
            chain_items.append((cm, DataQuality.AGGREGATED))

        chains["spotify"] = FallbackChain("spotify", chain_items)

    # Shazam chain
    if credentials.get("shazam_rapidapi_key"):
        from scrapers.shazam import ShazamScraper
        shazam = ShazamScraper(
            credentials={"rapidapi_key": credentials["shazam_rapidapi_key"]},
            api_base_url=api_base_url, admin_key=admin_key,
        )
        chain_items = [(shazam, DataQuality.LIVE)]

        if credentials.get("chartmetric_api_key"):
            from scrapers.chartmetric import ChartmetricScraper
            cm = ChartmetricScraper(
                credentials={"api_key": credentials["chartmetric_api_key"]},
                api_base_url=api_base_url, admin_key=admin_key,
            )
            chain_items.append((cm, DataQuality.AGGREGATED))

        chains["shazam"] = FallbackChain("shazam", chain_items)

    # Apple Music chain
    if credentials.get("apple_music_team_id"):
        from scrapers.apple_music import AppleMusicScraper
        apple = AppleMusicScraper(
            credentials={
                "team_id": credentials["apple_music_team_id"],
                "key_id": credentials.get("apple_music_key_id", ""),
                "private_key_path": credentials.get("apple_music_private_key_path", ""),
            },
            api_base_url=api_base_url, admin_key=admin_key,
        )
        chain_items = [(apple, DataQuality.LIVE)]

        if credentials.get("chartmetric_api_key"):
            from scrapers.chartmetric import ChartmetricScraper
            cm = ChartmetricScraper(
                credentials={"api_key": credentials["chartmetric_api_key"]},
                api_base_url=api_base_url, admin_key=admin_key,
            )
            chain_items.append((cm, DataQuality.AGGREGATED))

        chains["apple_music"] = FallbackChain("apple_music", chain_items)

    # Radio chain
    from scrapers.radio import RadioScraper
    radio = RadioScraper(credentials={}, api_base_url=api_base_url, admin_key=admin_key)
    chains["radio"] = FallbackChain("radio", [(radio, DataQuality.SCRAPED)])

    # Chartmetric as standalone
    if credentials.get("chartmetric_api_key"):
        from scrapers.chartmetric import ChartmetricScraper
        cm = ChartmetricScraper(
            credentials={"api_key": credentials["chartmetric_api_key"]},
            api_base_url=api_base_url, admin_key=admin_key,
        )
        chains["chartmetric"] = FallbackChain("chartmetric", [(cm, DataQuality.LIVE)])

    # Spotify Audio Enrichment (enriches tracks already in DB with audio features)
    if credentials.get("spotify_client_id"):
        from scrapers.spotify_audio import SpotifyAudioScraper
        spotify_audio = SpotifyAudioScraper(
            credentials={
                "client_id": credentials["spotify_client_id"],
                "client_secret": credentials.get("spotify_client_secret", ""),
            },
            api_base_url=api_base_url,
            admin_key=admin_key,
        )
        chains["spotify_audio"] = FallbackChain("spotify_audio", [(spotify_audio, DataQuality.LIVE)])

    return chains
