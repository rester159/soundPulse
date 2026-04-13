"""
Udio via PiAPI — real adapter (replaces the udio_stub.py scaffolding).

PiAPI exposes Udio (and many other music models) via a unified task API:
  POST /api/v1/task                → submit a generation task
  GET  /api/v1/task/{task_id}      → poll for status + output

Udio is reached via the `music-u` model id. $0.05 per generation per
PiAPI's published pricing.

Docs: https://piapi.ai/docs/music-api/create-task
      https://piapi.ai/docs/suno-api/get-task
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

PIAPI_BASE = os.environ.get("PIAPI_BASE_URL", "https://api.piapi.ai")
COST_PER_SONG_USD = 0.05


class UdioPiAPIAdapter(ProviderAdapter):
    id = "udio"
    display_name = "Udio via PiAPI"

    def __init__(self) -> None:
        self.api_key = os.environ.get("PIAPI_KEY", "").strip()
        self.live = bool(self.api_key)

    def _client(self) -> httpx.AsyncClient:
        if not self.api_key:
            raise ProviderNotConfigured(
                "PIAPI_KEY env var is not set — cannot call Udio via PiAPI. "
                "Sign up at https://piapi.ai/workspace, generate a key, "
                "and add it as PIAPI_KEY in Railway env."
            )
        return httpx.AsyncClient(
            base_url=PIAPI_BASE,
            headers={
                "x-api-key": self.api_key,
                "Content-Type": "application/json",
            },
            timeout=60.0,
        )

    def _build_payload(self, params: GenerateParams) -> dict[str, Any]:
        """Map GenerateParams → PiAPI /api/v1/task body for music-u (Udio)."""
        # PiAPI supports two lyrics_type modes: "instrumental" or "generate"
        # (generate lyrics from prompt). We use generate by default since
        # Udio's strength is vocal tracks — MusicGen already handles
        # instrumental use cases.
        gpt_prompt_parts = [params.prompt]
        if params.genre_hint:
            gpt_prompt_parts.append(f"Genre: {params.genre_hint}")
        if params.tempo_bpm:
            gpt_prompt_parts.append(f"Tempo: {int(params.tempo_bpm)} BPM")
        if params.key_hint:
            gpt_prompt_parts.append(f"Key: {params.key_hint}")
        if params.mood_tags:
            gpt_prompt_parts.append(f"Mood: {', '.join(params.mood_tags)}")

        # Negative tags — we explicitly don't want generic cues
        negative_tags = "generic, sample, demo, low quality"

        payload: dict[str, Any] = {
            "model": "music-u",
            "task_type": "generate_music",
            "input": {
                "gpt_description_prompt": ". ".join(gpt_prompt_parts),
                "negative_tags": negative_tags,
                "lyrics_type": "generate",  # let Udio write lyrics from the prompt
            },
        }
        if params.seed is not None:
            payload["input"]["seed"] = params.seed
        return payload

    async def generate(self, params: GenerateParams) -> GenerationTask:
        async with self._client() as client:
            payload = self._build_payload(params)
            r = await client.post("/api/v1/task", json=payload)
            if r.status_code >= 400:
                logger.error(
                    "[udio_piapi] create failed %s: %s",
                    r.status_code, r.text[:500],
                )
                raise RuntimeError(
                    f"PiAPI returned {r.status_code}: {r.text[:500]}"
                )
            body = r.json()

            # PiAPI response shape:
            #   {code: 200, message: "success", data: {task_id: "...", status: "pending", ...}}
            data = body.get("data") or body
            task_id = data.get("task_id") or data.get("id")
            if not task_id:
                raise RuntimeError(f"PiAPI response missing task_id: {body}")

            logger.info(
                "[udio_piapi] submitted task %s (cost ~$%.3f)",
                task_id, COST_PER_SONG_USD,
            )
            return GenerationTask(
                provider=self.id,
                task_id=task_id,
                submitted_at=self._now(),
                estimated_cost_usd=COST_PER_SONG_USD,
                params_echo=payload["input"],
            )

    async def poll(self, task_id: str) -> GenerationResult:
        async with self._client() as client:
            r = await client.get(f"/api/v1/task/{task_id}")
            if r.status_code == 404:
                return GenerationResult(
                    provider=self.id,
                    task_id=task_id,
                    status=GenerationStatus.FAILED,
                    error=f"PiAPI task {task_id} not found",
                )
            if r.status_code >= 400:
                return GenerationResult(
                    provider=self.id,
                    task_id=task_id,
                    status=GenerationStatus.FAILED,
                    error=f"PiAPI poll returned {r.status_code}: {r.text[:300]}",
                )
            body = r.json()

        # PiAPI task states: pending | starting | processing | success | failed | retry
        data = body.get("data") or body
        raw_status = (data.get("status") or "").lower()
        status_map = {
            "pending":    GenerationStatus.PENDING,
            "starting":   GenerationStatus.PENDING,
            "processing": GenerationStatus.PROCESSING,
            "retry":      GenerationStatus.PROCESSING,
            "success":    GenerationStatus.SUCCEEDED,
            "completed":  GenerationStatus.SUCCEEDED,
            "failed":     GenerationStatus.FAILED,
            "error":      GenerationStatus.FAILED,
        }
        status = status_map.get(raw_status, GenerationStatus.PENDING)

        audio_url: str | None = None
        duration_seconds: float | None = None
        if status == GenerationStatus.SUCCEEDED:
            output = data.get("output") or {}
            # Udio via PiAPI returns:
            #   output.songs = [ {song_path, image_path, duration, title, lyrics, tags, ...}, ... ]
            # Two clips per call. We take the first one as the master
            # candidate. song_path is the audio URL, image_path is cover art.
            songs = []
            if isinstance(output, dict):
                songs = output.get("songs") or []
            elif isinstance(output, list):
                songs = output

            if songs:
                first = songs[0] if isinstance(songs[0], dict) else {}
                audio_url = (
                    first.get("song_path")      # Udio specific
                    or first.get("audio_url")   # Suno compatibility
                    or first.get("url")
                )
                duration_seconds = first.get("duration") or first.get("duration_seconds")

        error = None
        if status == GenerationStatus.FAILED:
            error = data.get("error") or data.get("message") or "unknown error"

        return GenerationResult(
            provider=self.id,
            task_id=task_id,
            status=status,
            audio_url=audio_url,
            duration_seconds=float(duration_seconds) if duration_seconds else None,
            error=str(error) if error else None,
            actual_cost_usd=COST_PER_SONG_USD if status == GenerationStatus.SUCCEEDED else None,
            raw_payload=body,
        )

    def cost_estimate(self, params: GenerateParams) -> float:
        return COST_PER_SONG_USD
