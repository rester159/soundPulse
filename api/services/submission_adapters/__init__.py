"""
Submission adapters — register each target with the external_submission
dispatcher.

Two kinds of adapter exist:

  1. PURE-API adapters (no browser): call external HTTP APIs directly
     from the Python process. These live as individual modules and
     register themselves with @register_adapter.
       Examples: mlc, submithub, youtube_content_id, press_release_agent,
                 social_media_agent.

  2. PORTAL adapters (browser automation needed): DO NOT run Playwright
     in-process. Instead they call _enqueue_for_worker() which creates a
     pending external_submissions row. The portal-worker Railway service
     (services/portal-worker/, Node.js + BlackTip) polls for these via
     /admin/worker/claim-next and drives the real portal flow outside
     of this process. Results come back via /admin/worker/ack|fail.

  The full list of portal targets is in PORTAL_TARGETS below — every
  entry becomes a registered enqueue stub.

Import this package from api/main.py at boot time so the
@register_adapter decorators run.
"""
from __future__ import annotations

import logging
import uuid as _uuid
from datetime import datetime, timezone
from typing import Any

from api.services.external_submission_agent import register_adapter

logger = logging.getLogger(__name__)

# Portal-based targets — each gets a thin enqueue-only adapter that marks
# the external_submissions row as pending (status already 'in_progress'
# when the dispatcher calls the adapter; we flip it back to 'pending' so
# the portal-worker picks it up via claim-next).
PORTAL_TARGETS = [
    # Distributors
    "distrokid", "tunecore", "cd-baby", "amuse", "unitedmasters",
    # PROs + rights
    "bmi", "soundexchange",
    # Sync marketplaces
    "musicbed", "marmoset", "artlist",
    # Playlist pitching
    "groover", "playlistpush", "spotify_editorial", "apple_music_for_artists",
    # Marketing
    "tiktok_upload",
]


def _make_enqueue_adapter(target_service: str):
    """Build a thin enqueue-only adapter for a portal target. Returns
    a status of 'pending' (not 'submitted') so the portal-worker
    ingests it via claim-next."""

    async def _enqueue(db, subject_row, target):
        logger.info(
            "[%s] enqueued subject %s for portal-worker",
            target_service, getattr(subject_row, "song_id", "?"),
        )
        return (
            "pending",  # NOT 'submitted' — worker hasn't run yet
            None,
            {
                "enqueued_at": datetime.now(timezone.utc).isoformat(),
                "target_service": target_service,
                "worker": "portal-worker (services/portal-worker/)",
                "note": (
                    "Row is waiting for portal-worker to claim it via "
                    "POST /admin/worker/claim-next. Check worker logs on "
                    "Railway if this stays 'pending' for more than 30 min."
                ),
            },
        )

    return _enqueue


# Register every portal target with its enqueue stub
for _target in PORTAL_TARGETS:
    register_adapter(_target)(_make_enqueue_adapter(_target))


# Pure-API adapters still register via their own modules
from . import mlc  # noqa: F401,E402
from . import submithub  # noqa: F401,E402
from . import youtube_content_id  # noqa: F401,E402
