"""
Udio — deliberately stubbed.

Udio is in a licensing transition: UMG (Oct 2025) and WMG (Nov 2025)
settlements require Udio to rebuild as a "fully licensed" platform.
Audio downloads are disabled across all plans as of April 2026 while
the new platform launches later in the year.

This stub exists so the registry can list Udio without blowing up.
Every method raises ProviderUnavailable with a clear ETA.
"""
from __future__ import annotations

from .base import (
    GenerateParams,
    GenerationResult,
    GenerationTask,
    ProviderAdapter,
    ProviderUnavailable,
)

UDIO_UNAVAILABLE_MSG = (
    "Udio is unavailable: licensing transition (UMG + WMG settlements "
    "Oct-Nov 2025). Downloads disabled across all plans. Expected ETA "
    "for re-launch: H2 2026."
)


class UdioStubAdapter(ProviderAdapter):
    id = "udio"
    display_name = "Udio (unavailable — licensing transition)"
    live = False

    async def generate(self, params: GenerateParams) -> GenerationTask:
        raise ProviderUnavailable(UDIO_UNAVAILABLE_MSG)

    async def poll(self, task_id: str) -> GenerationResult:
        raise ProviderUnavailable(UDIO_UNAVAILABLE_MSG)

    def cost_estimate(self, params: GenerateParams) -> float:
        return 0.0
