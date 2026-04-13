"""
Adapter registry. Single dispatch point for every music-gen call.

Every id here matches a row in `tools_registry` so grants map without
translation.
"""
from __future__ import annotations

from functools import lru_cache

from .base import ProviderAdapter
from .replicate_musicgen import ReplicateMusicgenAdapter
from .suno_kie import SunoKieAdapter
from .udio_piapi import UdioPiAPIAdapter


@lru_cache(maxsize=1)
def _instances() -> dict[str, ProviderAdapter]:
    return {
        "musicgen": ReplicateMusicgenAdapter(),
        "suno_kie": SunoKieAdapter(),
        "udio": UdioPiAPIAdapter(),
    }


def get_provider(provider_id: str) -> ProviderAdapter:
    """Return the adapter by id, or raise KeyError."""
    instances = _instances()
    if provider_id not in instances:
        raise KeyError(
            f"Unknown music provider '{provider_id}'. "
            f"Known: {sorted(instances)}"
        )
    return instances[provider_id]


def list_providers() -> list[dict]:
    """All registered providers + their live/configured state."""
    return [
        {
            "id": adapter.id,
            "display_name": adapter.display_name,
            "live": adapter.live,
        }
        for adapter in _instances().values()
    ]


def list_available_providers() -> list[dict]:
    """Only providers that are live (have credentials AND aren't stubbed)."""
    return [p for p in list_providers() if p["live"]]
