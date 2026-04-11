"""
Scraper registry — single source of truth for scraper_id → implementation.

Generality principle: the scheduler must not know about specific scrapers.
Adding a new scraper should be a one-line edit to this dict, not a new
`elif scraper_id == "..."` branch in `scheduler.py`.

Each entry maps:
    scraper_id → {
        "module":      dotted import path of the scraper module
        "class":       class name to instantiate
        "credentials": dict of {constructor_field_name → env_var_name}
    }

`_run_scraper_job` in scheduler.py resolves this with importlib and builds
the credentials dict by reading each env var at call time (so key rotation
in the environment is picked up on the next run without a restart).
"""
from __future__ import annotations


SCRAPER_REGISTRY: dict[str, dict] = {
    "spotify": {
        "module": "scrapers.spotify",
        "class": "SpotifyScraper",
        "credentials": {
            "client_id": "SPOTIFY_CLIENT_ID",
            "client_secret": "SPOTIFY_CLIENT_SECRET",
        },
    },
    "chartmetric": {
        "module": "scrapers.chartmetric",
        "class": "ChartmetricScraper",
        "credentials": {
            "api_key": "CHARTMETRIC_API_KEY",
        },
    },
    "chartmetric_deep_us": {
        "module": "scrapers.chartmetric_deep_us",
        "class": "ChartmetricDeepUSScraper",
        "credentials": {
            "api_key": "CHARTMETRIC_API_KEY",
        },
    },
    "chartmetric_playlist_crawler": {
        "module": "scrapers.chartmetric_playlist_crawler",
        "class": "ChartmetricPlaylistCrawler",
        "credentials": {
            "api_key": "CHARTMETRIC_API_KEY",
        },
    },
    "chartmetric_artist_tracks": {
        "module": "scrapers.chartmetric_artist_tracks",
        "class": "ChartmetricArtistTracksScraper",
        "credentials": {
            "api_key": "CHARTMETRIC_API_KEY",
        },
    },
    "chartmetric_us_cities": {
        "module": "scrapers.chartmetric_us_cities",
        "class": "ChartmetricUSCitiesScraper",
        "credentials": {
            "api_key": "CHARTMETRIC_API_KEY",
        },
    },
    "chartmetric_artist_stats": {
        "module": "scrapers.chartmetric_artist_stats",
        "class": "ChartmetricArtistStatsScraper",
        "credentials": {
            "api_key": "CHARTMETRIC_API_KEY",
        },
    },
    "chartmetric_artists": {
        "module": "scrapers.chartmetric_artists",
        "class": "ChartmetricArtistsScraper",
        "credentials": {
            "api_key": "CHARTMETRIC_API_KEY",
        },
    },
    "shazam": {
        "module": "scrapers.shazam",
        "class": "ShazamScraper",
        "credentials": {
            "rapidapi_key": "SHAZAM_RAPIDAPI_KEY",
        },
    },
    "apple_music": {
        "module": "scrapers.apple_music",
        "class": "AppleMusicScraper",
        "credentials": {
            "team_id": "APPLE_MUSIC_TEAM_ID",
            "key_id": "APPLE_MUSIC_KEY_ID",
            "private_key_path": "APPLE_MUSIC_PRIVATE_KEY_PATH",
        },
    },
    "musicbrainz": {
        "module": "scrapers.musicbrainz",
        "class": "MusicBrainzEnricher",
        "credentials": {},
    },
    "radio": {
        "module": "scrapers.radio",
        "class": "RadioScraper",
        "credentials": {},
    },
    "kworb": {
        "module": "scrapers.kworb",
        "class": "KworbScraper",
        "credentials": {},
    },
    "spotify_audio": {
        "module": "scrapers.spotify_audio",
        "class": "SpotifyAudioScraper",
        "credentials": {
            "client_id": "SPOTIFY_CLIENT_ID",
            "client_secret": "SPOTIFY_CLIENT_SECRET",
        },
    },
    "genius_lyrics": {
        "module": "scrapers.genius_lyrics",
        "class": "GeniusLyricsScraper",
        "credentials": {
            "api_key": "GENIUS_API_KEY",
        },
    },
}


def load_scraper(scraper_id: str, *, api_base_url: str, admin_key: str):
    """
    Resolve `scraper_id` via the registry and return an instantiated scraper.

    Returns None if the scraper_id is unknown. Callers should log and skip.
    Raises ImportError / AttributeError if the registry entry points at a
    module or class that doesn't exist — that's a programmer error, not a
    runtime condition to swallow.
    """
    import importlib
    import os

    spec = SCRAPER_REGISTRY.get(scraper_id)
    if spec is None:
        return None

    module = importlib.import_module(spec["module"])
    cls = getattr(module, spec["class"])
    credentials = {
        field: os.environ.get(env_var, "")
        for field, env_var in spec["credentials"].items()
    }
    return cls(
        credentials=credentials,
        api_base_url=api_base_url,
        admin_key=admin_key,
    )
