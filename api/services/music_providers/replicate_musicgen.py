"""
MusicGen (Meta) via Replicate REST API.

Pricing: $0.064 per run (flat rate on Replicate).
Model: meta/musicgen (stereo-melody-large by default).
Docs: https://replicate.com/meta/musicgen
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

REPLICATE_API_BASE = "https://api.replicate.com/v1"

# Model version hash. Replicate requires the specific version, not the
# latest tag. We resolve this at first call and cache it on the class.
# meta/musicgen latest stable as of April 2026.
MODEL_NAME = "meta/musicgen"

# Flat pricing per Replicate's published page.
COST_PER_RUN_USD = 0.064


class ReplicateMusicgenAdapter(ProviderAdapter):
    id = "musicgen"
    display_name = "MusicGen (Meta) via Replicate"
    _cached_version: str | None = None

    def __init__(self) -> None:
        self.api_key = os.environ.get("REPLICATE_API_TOKEN", "").strip()
        self.live = bool(self.api_key)

    def _client(self) -> httpx.AsyncClient:
        if not self.api_key:
            raise ProviderNotConfigured(
                "REPLICATE_API_TOKEN env var is not set — cannot call Replicate"
            )
        return httpx.AsyncClient(
            base_url=REPLICATE_API_BASE,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )

    async def _resolve_model_version(self, client: httpx.AsyncClient) -> str:
        """Look up the current pinned version of meta/musicgen."""
        if self._cached_version:
            return self._cached_version
        r = await client.get(f"/models/{MODEL_NAME}")
        r.raise_for_status()
        data = r.json()
        version = data.get("latest_version", {}).get("id")
        if not version:
            raise RuntimeError(f"Replicate returned no latest_version for {MODEL_NAME}")
        type(self)._cached_version = version
        return version

    def _build_input(self, params: GenerateParams) -> dict[str, Any]:
        """Map GenerateParams → MusicGen input schema."""
        prompt_parts = [params.prompt]
        if params.genre_hint:
            prompt_parts.append(f"Genre: {params.genre_hint}")
        if params.tempo_bpm:
            prompt_parts.append(f"Tempo: {int(params.tempo_bpm)} BPM")
        if params.key_hint:
            prompt_parts.append(f"Key: {params.key_hint}")
        if params.mood_tags:
            prompt_parts.append(f"Mood: {', '.join(params.mood_tags)}")

        musicgen_input: dict[str, Any] = {
            "prompt": ". ".join(prompt_parts),
            "duration": min(max(params.duration_seconds, 1), 30),  # MusicGen caps at 30s
            "model_version": params.model_variant or "stereo-melody-large",
            "output_format": "mp3",
            "normalization_strategy": "peak",
        }
        if params.seed is not None:
            musicgen_input["seed"] = params.seed
        if params.reference_audio_url:
            musicgen_input["input_audio"] = params.reference_audio_url
            musicgen_input["continuation"] = False  # reference-mode, not continuation
        return musicgen_input

    async def generate(self, params: GenerateParams) -> GenerationTask:
        async with self._client() as client:
            version = await self._resolve_model_version(client)
            payload = {
                "version": version,
                "input": self._build_input(params),
            }
            r = await client.post("/predictions", json=payload)
            if r.status_code >= 400:
                body_text = r.text[:1000]
                logger.error("[musicgen] create failed %s: %s", r.status_code, body_text)
                # Surface Replicate's actual error body to the caller — a bare
                # httpx HTTPStatusError just says "402 Payment Required" without
                # telling you WHY (no billing? spend limit? account locked?).
                raise RuntimeError(
                    f"Replicate returned {r.status_code}: {body_text}"
                )
            body = r.json()
            task_id = body["id"]
            logger.info(
                "[musicgen] submitted task %s (cost ~$%.3f)",
                task_id,
                COST_PER_RUN_USD,
            )
            return GenerationTask(
                provider=self.id,
                task_id=task_id,
                submitted_at=self._now(),
                estimated_cost_usd=COST_PER_RUN_USD,
                params_echo=payload["input"],
            )

    async def poll(self, task_id: str) -> GenerationResult:
        async with self._client() as client:
            r = await client.get(f"/predictions/{task_id}")
            if r.status_code == 404:
                return GenerationResult(
                    provider=self.id,
                    task_id=task_id,
                    status=GenerationStatus.FAILED,
                    error=f"Replicate prediction {task_id} not found",
                )
            r.raise_for_status()
            body = r.json()

        status_map = {
            "starting": GenerationStatus.PENDING,
            "processing": GenerationStatus.PROCESSING,
            "succeeded": GenerationStatus.SUCCEEDED,
            "failed": GenerationStatus.FAILED,
            "canceled": GenerationStatus.FAILED,
        }
        status = status_map.get(body.get("status", ""), GenerationStatus.PENDING)

        audio_url: str | None = None
        if status == GenerationStatus.SUCCEEDED:
            output = body.get("output")
            # MusicGen returns either a string URL or a list of URLs.
            if isinstance(output, str):
                audio_url = output
            elif isinstance(output, list) and output:
                audio_url = output[0]

        duration_seconds: float | None = None
        metrics = body.get("metrics") or {}
        if "predict_time" in metrics:
            duration_seconds = float(metrics["predict_time"])

        error = body.get("error") if status == GenerationStatus.FAILED else None

        return GenerationResult(
            provider=self.id,
            task_id=task_id,
            status=status,
            audio_url=audio_url,
            duration_seconds=duration_seconds,
            error=str(error) if error else None,
            actual_cost_usd=COST_PER_RUN_USD if status == GenerationStatus.SUCCEEDED else None,
            raw_payload=body,
        )

    def cost_estimate(self, params: GenerateParams) -> float:
        return COST_PER_RUN_USD
