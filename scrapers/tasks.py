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


@app.task(name="scrapers.tasks.train_model")
def train_model():
    """Daily model training: retrain on all historical data, evaluate, save."""
    logger.info("Starting model training...")
    try:
        import subprocess
        import sys
        # Use absolute path so this works regardless of CWD in the Railway container
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        script_path = os.path.join(project_root, "scripts", "train_model.py")
        result = subprocess.run(
            [sys.executable, script_path],
            capture_output=True, text=True, timeout=1800,  # 30 min max
            cwd=project_root,
        )
        logger.info("Training stdout: %s", result.stdout[-500:] if result.stdout else "")
        if result.returncode != 0:
            logger.error("Training failed: %s", result.stderr[-500:] if result.stderr else "")
        return {"status": "success" if result.returncode == 0 else "error", "output": result.stdout[-200:]}
    except Exception as e:
        logger.exception("Model training failed")
        return {"status": "error", "error": str(e)}


@app.task(name="scrapers.tasks.run_backtest")
def run_backtest_task():
    """Daily backtesting: evaluate current model against recent predictions."""
    logger.info("Starting daily backtest evaluation...")
    try:
        from api.database import async_session_factory
        from api.services.backtest_service import run_backtest

        async def _run():
            async with async_session_factory() as db:
                run_id = await run_backtest(db, months=3, horizon="7d")
                return run_id

        loop = asyncio.new_event_loop()
        run_id = loop.run_until_complete(_run())
        loop.close()
        logger.info("Backtest completed: run_id=%s", run_id)
        return {"status": "success", "run_id": run_id}
    except Exception as e:
        logger.exception("Backtest failed")
        return {"status": "error", "error": str(e)}


@app.task(name="scrapers.tasks.generate_predictions")
def generate_predictions():
    """Generate predictions for all active entities. Runs after each scrape cycle."""
    logger.info("Generating predictions for active entities...")
    try:
        import httpx
        api_url, admin_key = _get_api_config()

        with httpx.Client(timeout=30) as client:
            # Get top trending entities
            resp = client.get(
                f"{api_url}/api/v1/trending",
                params={"entity_type": "track", "limit": 50},
                headers={"X-API-Key": admin_key},
            )
            if resp.status_code != 200:
                return {"status": "error", "message": f"Failed to get trending: {resp.status_code}"}

            entities = resp.json().get("data", [])
            predicted = 0

            for entity in entities:
                entity_id = entity.get("entity", {}).get("id")
                if not entity_id:
                    continue
                try:
                    pred_resp = client.get(
                        f"{api_url}/api/v1/predictions/{entity_id}",
                        params={"entity_type": "track"},
                        headers={"X-API-Key": admin_key},
                    )
                    if pred_resp.status_code == 200:
                        predicted += 1
                except Exception:
                    pass

        logger.info("Generated predictions for %d entities", predicted)
        return {"status": "success", "predicted": predicted}
    except Exception as e:
        logger.exception("Prediction generation failed")
        return {"status": "error", "error": str(e)}


@app.task(name="scrapers.tasks.run_classification_sweep")
def run_classification_sweep(batch_size: int = 500):
    """Periodic sweep that classifies bulk-ingested entities (deferred classification)."""
    logger.info("Starting classification sweep (batch_size=%d)...", batch_size)
    try:
        from api.database import async_session_factory
        from api.services.classification_sweep import sweep_unclassified_entities

        async def _run():
            async with async_session_factory() as db:
                return await sweep_unclassified_entities(db, batch_size=batch_size)

        loop = asyncio.new_event_loop()
        try:
            stats = loop.run_until_complete(_run())
        finally:
            loop.close()
        logger.info("Classification sweep complete: %s", stats)
        return {"status": "success", **stats}
    except Exception as e:
        logger.exception("Classification sweep failed")
        return {"status": "error", "error": str(e)}


@app.task(name="scrapers.tasks.run_composite_sweep")
def run_composite_sweep(batch_size: int = 1000):
    """Periodic sweep that normalizes + recomputes composite scores for bulk-ingested snapshots."""
    logger.info("Starting composite sweep (batch_size=%d)...", batch_size)
    try:
        from api.database import async_session_factory
        from api.services.composite_sweep import sweep_zero_normalized_snapshots

        async def _run():
            async with async_session_factory() as db:
                return await sweep_zero_normalized_snapshots(db, batch_size=batch_size)

        loop = asyncio.new_event_loop()
        try:
            stats = loop.run_until_complete(_run())
        finally:
            loop.close()
        logger.info("Composite sweep complete: %s", stats)
        return {"status": "success", **stats}
    except Exception as e:
        logger.exception("Composite sweep failed")
        return {"status": "error", "error": str(e)}


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


# ---------------------------------------------------------------------
# Autonomous pipeline sweeps — PRD §29 Phase 3 fully-automatic path
# ---------------------------------------------------------------------

@app.task(name="scrapers.tasks.run_metadata_projection_sweep")
def run_metadata_projection_sweep():
    """Walk qa_passed songs without an ISRC and project metadata."""
    try:
        from api.database import get_db_context
        from api.services.metadata_projection import project_metadata_for_song
        from api.models.ai_artist import AIArtist
        from api.models.songs_master import SongMaster
        from sqlalchemy import select

        async def _run():
            async with get_db_context() as db:
                songs = (await db.execute(
                    select(SongMaster).where(
                        SongMaster.status == "qa_passed",
                        SongMaster.isrc.is_(None),
                    ).limit(25)
                )).scalars().all()
                projected = 0
                for s in songs:
                    artist = (await db.execute(
                        select(AIArtist).where(AIArtist.artist_id == s.primary_artist_id)
                    )).scalar_one_or_none()
                    if artist:
                        try:
                            await project_metadata_for_song(db, song=s, artist=artist)
                            projected += 1
                        except Exception as e:
                            logger.exception("metadata projection failed for %s", s.song_id)
                return {"scanned": len(songs), "projected": projected}

        loop = asyncio.new_event_loop()
        r = loop.run_until_complete(_run())
        loop.close()
        return r
    except Exception as e:
        logger.exception("metadata projection sweep failed")
        return {"error": str(e)}


@app.task(name="scrapers.tasks.run_downstream_pipeline_sweep")
def run_downstream_pipeline_sweep():
    """
    Walk qa_passed songs with metadata projected and dispatch them
    through the downstream pipeline (distributors, PROs, sync,
    playlists, marketing). This is the autonomous loop that makes
    the entire submission side run itself.
    """
    try:
        from api.database import get_db_context
        from api.services.submissions_agent import sweep_downstream_pipeline

        async def _run():
            async with get_db_context() as db:
                return await sweep_downstream_pipeline(db, limit=10)

        loop = asyncio.new_event_loop()
        r = loop.run_until_complete(_run())
        loop.close()
        return r
    except Exception as e:
        logger.exception("downstream pipeline sweep failed")
        return {"error": str(e)}


@app.task(name="scrapers.tasks.run_audio_qa_full_sweep")
def run_audio_qa_full_sweep():
    """Run librosa-backed audio QA on qa_passed songs missing tempo_bpm."""
    try:
        from api.database import get_db_context
        from api.services.audio_qa_full import full_qa_for_song
        from api.models.songs_master import SongMaster
        from sqlalchemy import select

        async def _run():
            async with get_db_context() as db:
                songs = (await db.execute(
                    select(SongMaster).where(
                        SongMaster.status == "qa_passed",
                        SongMaster.tempo_bpm.is_(None),
                    ).limit(20)
                )).scalars().all()
                done = 0
                for s in songs:
                    r = await full_qa_for_song(db, song_id=s.song_id)
                    if r.get("status") == "done":
                        done += 1
                return {"scanned": len(songs), "analyzed": done}

        loop = asyncio.new_event_loop()
        r = loop.run_until_complete(_run())
        loop.close()
        return r
    except Exception as e:
        logger.exception("audio qa full sweep failed")
        return {"error": str(e)}


@app.task(name="scrapers.tasks.run_duplicate_detection_sweep")
def run_duplicate_detection_sweep():
    """Cosine similarity over MFCC-13 embeddings to flag duplicates."""
    try:
        from api.database import get_db_context
        from api.services.duplicate_detection import run_duplicate_sweep

        async def _run():
            async with get_db_context() as db:
                return await run_duplicate_sweep(db)

        loop = asyncio.new_event_loop()
        r = loop.run_until_complete(_run())
        loop.close()
        return r
    except Exception as e:
        logger.exception("duplicate detection sweep failed")
        return {"error": str(e)}


@app.task(name="scrapers.tasks.run_pop_culture_refresh")
def run_pop_culture_refresh():
    """Weekly pop-culture reference harvest via Gemini flash."""
    try:
        from api.database import get_db_context
        from api.services.pop_culture_scraper import refresh_pop_culture_references

        async def _run():
            async with get_db_context() as db:
                return await refresh_pop_culture_references(db, caller="celery_beat")

        loop = asyncio.new_event_loop()
        r = loop.run_until_complete(_run())
        loop.close()
        return r
    except Exception as e:
        logger.exception("pop culture refresh failed")
        return {"error": str(e)}
