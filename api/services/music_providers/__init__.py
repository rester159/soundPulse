"""
Music generation provider abstraction (§24, §61).

Unified interface over multiple music-gen backends so upstream code
(SongLab UI, generation pipeline, CEO action agent) can pick a provider
by id without caring about REST shape differences or credential loading.

Adapters:
  - musicgen           → MusicGen via Replicate (live, $0.064/run)
  - suno_evolink       → Suno via EvoLink 3P wrapper (scaffolded, key-gated)
  - udio               → Udio (stubbed — licensing transition, ETA H2 2026)

All adapter ids match rows in `tools_registry` (§17) so grants wire up
without translation.
"""
from .base import (
    ProviderAdapter,
    GenerateParams,
    GenerationTask,
    GenerationResult,
    GenerationClip,
    GenerationStatus,
    ProviderError,
    ProviderNotConfigured,
    ProviderUnavailable,
)
from .registry import get_provider, list_providers, list_available_providers

__all__ = [
    "ProviderAdapter",
    "GenerateParams",
    "GenerationTask",
    "GenerationResult",
    "GenerationClip",
    "GenerationStatus",
    "ProviderError",
    "ProviderNotConfigured",
    "ProviderUnavailable",
    "get_provider",
    "list_providers",
    "list_available_providers",
]
