import json
import logging
from pathlib import Path

_logger = logging.getLogger(__name__)

_DEFAULT_PLATFORM_WEIGHTS: dict[str, float] = {
    "chartmetric": 0.40,
    "spotify": 0.30,
    "shazam": 0.20,
    "apple_music": 0.05,
    "kworb": 0.05,
    "tiktok": 0.00,
    "radio": 0.00,
}

# Resolve config/scoring.json relative to the project root (parent of shared/)
_SCORING_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "scoring.json"


def _load_weights_from_config() -> dict[str, float]:
    """Load platform weights from config/scoring.json, falling back to defaults."""
    try:
        if _SCORING_CONFIG_PATH.exists():
            with open(_SCORING_CONFIG_PATH) as f:
                data = json.load(f)
            weights = data.get("platform_weights", {})
            if weights and isinstance(weights, dict):
                _logger.info("Loaded platform weights from %s", _SCORING_CONFIG_PATH)
                return {k: float(v) for k, v in weights.items()}
    except Exception:
        _logger.warning(
            "Failed to load scoring config from %s, using defaults",
            _SCORING_CONFIG_PATH,
            exc_info=True,
        )
    return dict(_DEFAULT_PLATFORM_WEIGHTS)


def reload_platform_weights() -> None:
    """Reload PLATFORM_WEIGHTS from the config file (called after saving new weights)."""
    global PLATFORM_WEIGHTS
    PLATFORM_WEIGHTS = _load_weights_from_config()


PLATFORM_WEIGHTS: dict[str, float] = _load_weights_from_config()

VALID_PLATFORMS = list(PLATFORM_WEIGHTS.keys())

VALID_ENTITY_TYPES = ["artist", "track"]
VALID_ENTITY_TYPES_WITH_GENRE = ["artist", "track", "genre"]

VALID_TIME_RANGES = ["today", "7d", "30d"]
VALID_HORIZONS = ["7d", "30d", "90d"]

VALID_TRENDING_SORT = ["composite_score", "velocity", "platform_rank"]
VALID_PREDICTION_SORT = ["predicted_change", "confidence", "predicted_score"]

RATE_LIMITS: dict[str, int] = {
    "free": 100,
    "pro": 1000,
    "admin": 0,  # 0 = unlimited
}

CACHE_TTL: dict[str, int] = {
    "trending_today": 900,      # 15 minutes
    "trending_7d": 3600,        # 1 hour
    "trending_30d": 21600,      # 6 hours
    "search": 300,              # 5 minutes
    "genres": 86400,            # 24 hours
    "predictions": 3600,        # 1 hour
    "backtesting": 21600,       # 6 hours
}

ROOT_CATEGORIES = [
    "pop", "rock", "electronic", "hip-hop", "r-and-b", "latin",
    "country", "jazz", "classical", "african", "asian", "caribbean",
]
