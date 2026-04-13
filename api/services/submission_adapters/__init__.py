"""
Submission adapters — one module per downstream service.

Each adapter registers itself with the external_submission_agent
dispatcher via @register_adapter('<target_service>') and replaces the
default _stub_adapter. Importing this package at boot time (via
api/main.py) runs all the decorators.

Structure: each adapter exposes a single async function
(db, subject_row, target) -> (status, external_id, response_dict).
"""
from __future__ import annotations

# Import each adapter module so its @register_adapter decorators run.
# Order doesn't matter — all decorators are additive.
from . import distrokid  # noqa: F401
from . import mlc  # noqa: F401
from . import submithub  # noqa: F401
from . import youtube_content_id  # noqa: F401
from . import playwright_distributors  # noqa: F401  # tunecore, cd-baby, amuse, unitedmasters
from . import pros_and_rights  # noqa: F401  # bmi, soundexchange
from . import sync_and_playlists  # noqa: F401  # musicbed, marmoset, artlist, groover, playlistpush, spotify_editorial, apple_music_for_artists
from . import tiktok_upload  # noqa: F401
