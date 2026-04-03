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
        "spotify-every-6h": {
            "task": "scrapers.tasks.run_scraper",
            "schedule": crontab(minute=0, hour="0,6,12,18"),
            "args": ("spotify",),
        },
        "chartmetric-every-4h": {
            "task": "scrapers.tasks.run_scraper",
            "schedule": crontab(minute=15, hour="*/4"),
            "args": ("chartmetric",),
        },
        "shazam-every-4h": {
            "task": "scrapers.tasks.run_scraper",
            "schedule": crontab(minute=30, hour="*/4"),
            "args": ("shazam",),
        },
        "apple-music-every-6h": {
            "task": "scrapers.tasks.run_scraper",
            "schedule": crontab(minute=0, hour="1,7,13,19"),
            "args": ("apple_music",),
        },
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
    },
})
