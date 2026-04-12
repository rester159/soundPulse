"""
Suno via EvoLink — third-party wrapper adapter.

Suno does not expose an official public API. EvoLink (and peers like
apiframe.ai, piapi.ai, sunoapi.org) resell Suno access via a standard
REST wrapper. This adapter speaks the EvoLink shape, documented at
https://docs.sunoapi.org/.

Pricing reference: ~$0.111/song via EvoLink tiers; ~8 credits/song on
apiframe at $19/mo = ~50 songs.

Status: scaffolded and key-gated. Without SUNO_EVOLINK_API_KEY the
adapter instantiates but generate() raises ProviderNotConfigured. The
endpoint shape matches the EvoLink docs but has not been smoke-tested
against a live account; when the key is provisioned, run the probe
endpoint in admin.py before putting this on the hot path.
"""
from __future__ import annotations

import logging
import os
from typing import Any

import httpx

from .base import (
    GenerateParams,
    GenerationResult,
    GenerationStatus,
    GenerationTask,
    ProviderAdapter,
    ProviderNotConfigured,
)

logger = logging.getLogger(__name__)

EVOLINK_BASE = os.environ.get("SUNO_EVOLINK_BASE_URL", "https://api.sunoapi.org")
COST_PER_SONG_USD = 0.111


class SunoEvolinkAdapter(ProviderAdapter):
    id = "suno_evolink"
    display_name = "Suno via EvoLink"

    def __init__(self) -> None:
        self.api_key = os.environ.get("SUNO_EVOLINK_API_KEY", "").strip()
        self.live = bool(self.api_key)

    def _client(self) -> httpx.AsyncClient:
        if not self.api_key:
            raise ProviderNotConfigured(
                "SUNO_EVOLINK_API_KEY env var is not set — cannot call Suno via EvoLink. "
                "Sign up at https://sunoapi.org and add the key to Railway env."
            )
        return httpx.AsyncClient(
            base_url=EVOLINK_BASE,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )

    def _build_payload(self, params: GenerateParams) -> dict[str, Any]:
        """Map GenerateParams → EvoLink /v1/audios/generations shape."""
        prompt_parts = [params.prompt]
        if params.genre_hint:
            prompt_parts.append(f"[genre: {params.genre_hint}]")
        if params.tempo_bpm:
            prompt_parts.append(f"[tempo: {int(params.tempo_bpm)} BPM]")
        if params.key_hint:
            prompt_parts.append(f"[key: {params.key_hint}]")
        if params.mood_tags:
            prompt_parts.append(f"[mood: {', '.join(params.mood_tags)}]")

        payload: dict[str, Any] = {
            "prompt": " ".join(prompt_parts),
            "model": params.model_variant or "suno-v5-beta",
            "duration": params.duration_seconds,
            "instrumental": False,
            "make_instrumental": False,
            "wait_audio": False,  # async — returns task id, we poll
        }
        if params.genre_hint:
            payload["tags"] = params.genre_hint
        if params.reference_audio_url:
            # Reference-audio slot used for §21 two-phase voice conditioning.
            payload["reference_audio_url"] = params.reference_audio_url
        if params.seed is not None:
            payload["seed"] = params.seed
        return payload

    async def generate(self, params: GenerateParams) -> GenerationTask:
        async with self._client() as client:
            payload = self._build_payload(params)
            r = await client.post("/v1/audios/generations", json=payload)
            if r.status_code >= 400:
                logger.error("[suno_evolink] create failed %s: %s", r.status_code, r.text[:500])
                r.raise_for_status()
            body = r.json()

            # EvoLink returns {data: {task_id: "...", ...}} or {task_id: "..."}
            # depending on wrapper version. Be permissive.
            task_id = (
                body.get("task_id")
                or (body.get("data") or {}).get("task_id")
                or body.get("id")
            )
            if not task_id:
                raise RuntimeError(f"EvoLink response missing task_id: {body}")

            logger.info(
                "[suno_evolink] submitted task %s (cost ~$%.3f)",
                task_id,
                COST_PER_SONG_USD,
            )
            return GenerationTask(
                provider=self.id,
                task_id=task_id,
                submitted_at=self._now(),
                estimated_cost_usd=COST_PER_SONG_USD,
                params_echo=payload,
            )

    async def poll(self, task_id: str) -> GenerationResult:
        async with self._client() as client:
            r = await client.get(f"/v1/tasks/{task_id}")
            if r.status_code == 404:
                return GenerationResult(
                    provider=self.id,
                    task_id=task_id,
                    status=GenerationStatus.FAILED,
                    error=f"EvoLink task {task_id} not found",
                )
            r.raise_for_status()
            body = r.json()

        # EvoLink status strings per docs
        status_map = {
            "pending": GenerationStatus.PENDING,
            "queued": GenerationStatus.PENDING,
            "processing": GenerationStatus.PROCESSING,
            "running": GenerationStatus.PROCESSING,
            "succeeded": GenerationStatus.SUCCEEDED,
            "success": GenerationStatus.SUCCEEDED,
            "completed": GenerationStatus.SUCCEEDED,
            "failed": GenerationStatus.FAILED,
            "error": GenerationStatus.FAILED,
        }
        raw_status = (body.get("status") or body.get("data", {}).get("status") or "").lower()
        status = status_map.get(raw_status, GenerationStatus.PENDING)

        audio_url: str | None = None
        duration_seconds: float | None = None
        if status == GenerationStatus.SUCCEEDED:
            data = body.get("data") or body
            audio_url = (
                data.get("audio_url")
                or data.get("url")
                or (data.get("clips") or [{}])[0].get("audio_url")
            )
            duration_seconds = data.get("duration") or data.get("duration_seconds")

        error = None
        if status == GenerationStatus.FAILED:
            error = body.get("error") or body.get("message") or "unknown error"

        return GenerationResult(
            provider=self.id,
            task_id=task_id,
            status=status,
            audio_url=audio_url,
            duration_seconds=float(duration_seconds) if duration_seconds else None,
            error=error,
            actual_cost_usd=COST_PER_SONG_USD if status == GenerationStatus.SUCCEEDED else None,
            raw_payload=body,
        )

    def cost_estimate(self, params: GenerateParams) -> float:
        return COST_PER_SONG_USD
