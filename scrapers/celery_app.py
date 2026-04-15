"""
Celery application configuration for SoundPulse scrapers.
Broker and result backend: Redis.
"""
from __future__ import annotations

import os
from celery import Celery
from celery.schedules import crontab

# Load .env
from dotenv import load_dotenv
load_dotenv()

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
CELERY_BROKER = os.environ.get("CELERY_BROKER_URL", REDIS_URL)
CELERY_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", REDIS_URL)

app = Celery("soundpulse_scrapers")

app.config_from_object({
    "broker_url": CELERY_BROKER,
    "result_backend": CELERY_BACKEND,
    "task_serializer": "json",
    "result_serializer": "json",
    "accept_content": ["json"],
    "timezone": "UTC",
    "enable_utc": True,
    "task_track_started": True,
    "task_acks_late": True,
    "worker_prefetch_multiplier": 1,
    "beat_schedule": {
        # ----- LEGACY SCRAPER BEAT ENTRIES (DISABLED 2026-04-15) -----
        # Every one of the scraper fallback chains in scrapers/fallback.py
        # has ChartmetricScraper as a fallback tier. That means each of
        # these Celery beat tasks (spotify/chartmetric/shazam/apple_music/
        # spotify_audio) ends up hitting the Chartmetric API independently
        # of scraper_configs.enabled, because run_scraper() doesn't check
        # that flag. Result: a stream of legacy requests hitting
        # Chartmetric behind the fetcher's back, driving calls_last_1h to
        # 3x what the token bucket should allow and triggering a steady
        # 429 bounce on the new pipeline.
        #
        # The chartmetric_ingest pipeline is the replacement. These beat
        # entries stay commented-out in source until we have a reason
        # to reinstate them (direct DSP API, not via Chartmetric).
        # "spotify-every-6h": {
        #     "task": "scrapers.tasks.run_scraper",
        #     "schedule": crontab(minute=0, hour="0,6,12,18"),
        #     "args": ("spotify",),
        # },
        # "chartmetric-every-4h": {
        #     "task": "scrapers.tasks.run_scraper",
        #     "schedule": crontab(minute=15, hour="*/4"),
        #     "args": ("chartmetric",),
        # },
        # "shazam-every-4h": {
        #     "task": "scrapers.tasks.run_scraper",
        #     "schedule": crontab(minute=30, hour="*/4"),
        #     "args": ("shazam",),
        # },
        # "apple-music-every-6h": {
        #     "task": "scrapers.tasks.run_scraper",
        #     "schedule": crontab(minute=0, hour="1,7,13,19"),
        #     "args": ("apple_music",),
        # },
        # radio + musicbrainz are direct, non-Chartmetric fetches, so
        # they stay enabled.
        "radio-daily": {
            "task": "scrapers.tasks.run_scraper",
            "schedule": crontab(minute=0, hour=6),
            "args": ("radio",),
        },
        "musicbrainz-enrich": {
            "task": "scrapers.tasks.run_scraper",
            "schedule": crontab(minute=0, hour=2),
            "args": ("musicbrainz",),
        },
        "health-check-15m": {
            "task": "scrapers.tasks.health_check",
            "schedule": crontab(minute="*/15"),
        },
        # --- Model training & prediction loop ---
        "train-model-daily": {
            "task": "scrapers.tasks.train_model",
            "schedule": crontab(minute=0, hour=3),  # 3am UTC daily
        },
        "generate-predictions-6h": {
            "task": "scrapers.tasks.generate_predictions",
            "schedule": crontab(minute=45, hour="*/6"),  # After scrape cycles
        },
        "backtest-daily": {
            "task": "scrapers.tasks.run_backtest",
            "schedule": crontab(minute=30, hour=4),  # 4:30am UTC daily, after training
        },
        # spotify-audio-enrich-daily DISABLED 2026-04-15 — fallback
        # chain routes through Chartmetric's audio-features endpoint.
        # "spotify-audio-enrich-daily": {
        #     "task": "scrapers.tasks.run_scraper",
        #     "schedule": crontab(minute=0, hour=5),
        #     "args": ("spotify_audio",),
        # },

        # --- Phase 3 production pipeline autonomous sweeps ---
        "audio-qa-full-every-2h": {
            "task": "scrapers.tasks.run_audio_qa_full_sweep",
            "schedule": crontab(minute=5, hour="*/2"),
        },
        "metadata-projection-every-2h": {
            "task": "scrapers.tasks.run_metadata_projection_sweep",
            "schedule": crontab(minute=10, hour="*/2"),
        },
        "duplicate-detection-daily": {
            "task": "scrapers.tasks.run_duplicate_detection_sweep",
            "schedule": crontab(minute=20, hour=2),
        },
        "downstream-pipeline-every-3h": {
            "task": "scrapers.tasks.run_downstream_pipeline_sweep",
            "schedule": crontab(minute=30, hour="*/3"),
        },
        "pop-culture-refresh-weekly": {
            "task": "scrapers.tasks.run_pop_culture_refresh",
            "schedule": crontab(minute=0, hour=9, day_of_week=1),
        },
    },
})
