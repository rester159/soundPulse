"""Provider-agnostic interface shared by every music-gen adapter."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class GenerationStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


@dataclass
class GenerateParams:
    """
    Provider-agnostic generation request.

    Every field here must have a sensible mapping across MusicGen, Suno,
    and Udio. Provider-specific knobs go in `extra` and are ignored by
    adapters that don't understand them.
    """
    prompt: str
    duration_seconds: int = 30
    genre_hint: str | None = None
    tempo_bpm: float | None = None
    key_hint: str | None = None
    mood_tags: list[str] = field(default_factory=list)
    reference_audio_url: str | None = None  # for §21 two-phase voice rule
    seed: int | None = None
    model_variant: str | None = None  # e.g. "stereo-melody-large"
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class GenerationTask:
    """Handle returned immediately from generate(). Poll with it."""
    provider: str
    task_id: str
    submitted_at: datetime
    estimated_cost_usd: float
    params_echo: dict[str, Any]


@dataclass
class GenerationResult:
    """Result of polling a task."""
    provider: str
    task_id: str
    status: GenerationStatus
    audio_url: str | None = None
    duration_seconds: float | None = None
    error: str | None = None
    actual_cost_usd: float | None = None
    raw_payload: dict[str, Any] = field(default_factory=dict)


class ProviderError(Exception):
    """Base class for any music-provider failure."""


class ProviderNotConfigured(ProviderError):
    """Raised when an adapter is called without its required credentials."""


class ProviderUnavailable(ProviderError):
    """Raised for providers deliberately disabled (e.g. Udio licensing)."""


class ProviderAdapter(ABC):
    """Every concrete adapter implements this tiny surface."""

    id: str = ""              # must match tools_registry.id
    display_name: str = ""
    live: bool = False        # True only if credentials present AND provider working

    @abstractmethod
    async def generate(self, params: GenerateParams) -> GenerationTask: ...

    @abstractmethod
    async def poll(self, task_id: str) -> GenerationResult: ...

    @abstractmethod
    def cost_estimate(self, params: GenerateParams) -> float: ...

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)
