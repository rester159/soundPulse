"""
Suno via Kie.ai — unofficial Suno API wrapper.

Kie.ai exposes Suno v5.5 (current flagship) via a clean REST interface.
Much better vocal/songwriting quality than Udio for most lyrical genres.

Docs: https://docs.kie.ai/suno-api
Base:   https://api.kie.ai
Create: POST /api/v1/generate
Poll:   GET  /api/v1/generate/record-info?taskId=<id>
Auth:   Bearer <KIE_API_KEY>
Models: V3_5, V4, V4_5, V4_5PLUS, V4_5ALL, V5, V5_5  (default: V5_5)
Cost:   ~$0.06 per song
"""
from __future__ import annotations

import logging
import os
from typing import Any

import httpx

from .base import (
    GenerateParams,
    GenerationClip,
    GenerationResult,
    GenerationStatus,
    GenerationTask,
    ProviderAdapter,
    ProviderNotConfigured,
)

logger = logging.getLogger(__name__)

KIE_BASE = os.environ.get("KIE_BASE_URL", "https://api.kie.ai")
COST_PER_SONG_USD = 0.06
DEFAULT_MODEL = "V5_5"  # Suno v5.5 — latest as of 2026-04


class SunoKieAdapter(ProviderAdapter):
    id = "suno_kie"
    display_name = "Suno v5.5 via Kie.ai"

    def __init__(self) -> None:
        self.api_key = os.environ.get("KIE_API_KEY", "").strip()
        self.live = bool(self.api_key)

    def _client(self) -> httpx.AsyncClient:
        if not self.api_key:
            raise ProviderNotConfigured(
                "KIE_API_KEY env var is not set — sign up at https://kie.ai "
                "and add the key to Railway env"
            )
        return httpx.AsyncClient(
            base_url=KIE_BASE,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            timeout=60.0,
        )

    def _build_payload(self, params: GenerateParams) -> dict[str, Any]:
        """Map GenerateParams → Kie.ai /api/v1/generate body."""
        # Kie.ai schema:
        #   prompt         (required)
        #   customMode     (required bool) — we use non-custom so Suno picks
        #                  structure/title/etc; set true for full control
        #   instrumental   (required bool)
        #   model          (optional string; default V5_5)
        #   style          (optional, only when customMode=true)
        #   title          (optional, max 80 chars)
        #   negativeTags   (optional)
        #   callBackUrl    (optional)
        prompt_parts = [params.prompt]
        if params.genre_hint:
            prompt_parts.append(f"Genre: {params.genre_hint}")
        if params.tempo_bpm:
            prompt_parts.append(f"Tempo: {int(params.tempo_bpm)} BPM")
        if params.key_hint:
            prompt_parts.append(f"Key: {params.key_hint}")
        if params.mood_tags:
            prompt_parts.append(f"Mood: {', '.join(params.mood_tags)}")

        payload: dict[str, Any] = {
            "prompt": ". ".join(prompt_parts)[:2000],
            "customMode": False,       # let Suno handle structure
            "instrumental": False,     # we want vocals
            "model": params.model_variant or DEFAULT_MODEL,
        }
        return payload

    async def generate(self, params: GenerateParams) -> GenerationTask:
        async with self._client() as client:
            payload = self._build_payload(params)
            r = await client.post("/api/v1/generate", json=payload)
            if r.status_code >= 400:
                logger.error(
                    "[suno_kie] create failed %s: %s",
                    r.status_code, r.text[:500],
                )
                raise RuntimeError(f"Kie.ai returned {r.status_code}: {r.text[:500]}")
            body = r.json()

        # Kie.ai response shape (observed from docs):
        #   { code: 200, msg: "...", data: { taskId: "..." } }
        # Be permissive in case the shape varies slightly.
        task_id = None
        if isinstance(body, dict):
            data = body.get("data") or body
            if isinstance(data, dict):
                task_id = (
                    data.get("taskId")
                    or data.get("task_id")
                    or data.get("id")
                )
            elif isinstance(data, str):
                task_id = data
        if not task_id:
            raise RuntimeError(f"Kie.ai response missing taskId: {body}")

        logger.info(
            "[suno_kie] submitted task %s (model=%s cost ~$%.3f)",
            task_id, payload.get("model"), COST_PER_SONG_USD,
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
            r = await client.get(
                "/api/v1/generate/record-info",
                params={"taskId": task_id},
            )
            if r.status_code == 404:
                return GenerationResult(
                    provider=self.id,
                    task_id=task_id,
                    status=GenerationStatus.FAILED,
                    error=f"Kie.ai task {task_id} not found",
                )
            if r.status_code >= 400:
                return GenerationResult(
                    provider=self.id,
                    task_id=task_id,
                    status=GenerationStatus.FAILED,
                    error=f"Kie.ai poll returned {r.status_code}: {r.text[:300]}",
                )
            body = r.json()

        # Kie.ai status strings per docs + observed usage:
        #   PENDING | TEXT_SUCCESS | FIRST_SUCCESS | SUCCESS |
        #   CREATE_TASK_FAILED | GENERATE_AUDIO_FAILED |
        #   CALLBACK_EXCEPTION | SENSITIVE_WORD_ERROR
        data = body.get("data") if isinstance(body, dict) else None
        if not isinstance(data, dict):
            data = body if isinstance(body, dict) else {}

        raw_status = (data.get("status") or "").upper()
        pending_states = {"PENDING", "TEXT_SUCCESS"}
        processing_states = {"FIRST_SUCCESS"}
        success_states = {"SUCCESS", "COMPLETED"}
        failed_states = {
            "CREATE_TASK_FAILED", "GENERATE_AUDIO_FAILED",
            "CALLBACK_EXCEPTION", "SENSITIVE_WORD_ERROR", "FAILED", "ERROR",
        }
        if raw_status in success_states:
            status = GenerationStatus.SUCCEEDED
        elif raw_status in failed_states:
            status = GenerationStatus.FAILED
        elif raw_status in processing_states:
            status = GenerationStatus.PROCESSING
        elif raw_status in pending_states:
            status = GenerationStatus.PENDING
        else:
            status = GenerationStatus.PENDING  # unknown → treat as still cooking

        audio_url: str | None = None
        duration_seconds: float | None = None
        clips: list[GenerationClip] = []

        if status == GenerationStatus.SUCCEEDED:
            # Kie.ai returns TWO clips per generation typically under
            # data.response.sunoData[] with fields:
            #   id, audioUrl, streamAudioUrl, imageUrl, sourceAudioUrl,
            #   sourceStreamAudioUrl, sourceImageUrl, prompt, modelName,
            #   title, tags, createTime, duration, sunoData?
            response_obj = data.get("response") or {}
            songs = response_obj.get("sunoData") or []
            if not songs and isinstance(data.get("output"), list):
                songs = data["output"]

            for s in songs if isinstance(songs, list) else []:
                if not isinstance(s, dict):
                    continue
                clip_url = (
                    s.get("audioUrl")
                    or s.get("audio_url")
                    or s.get("sourceAudioUrl")
                    or s.get("source_audio_url")
                    or s.get("streamAudioUrl")
                    or s.get("url")
                )
                if not clip_url:
                    continue
                clips.append(GenerationClip(
                    audio_url=clip_url,
                    duration_seconds=s.get("duration") or s.get("duration_seconds"),
                    title=s.get("title"),
                    lyrics=s.get("prompt") or s.get("lyrics"),  # Kie stores lyrics in prompt sometimes
                    image_url=s.get("imageUrl") or s.get("image_url") or s.get("sourceImageUrl"),
                    tags=(s.get("tags") or "").split(",") if isinstance(s.get("tags"), str) else (s.get("tags") or []),
                    provider_clip_id=s.get("id"),
                ))

            if clips:
                audio_url = clips[0].audio_url
                duration_seconds = clips[0].duration_seconds

        error = None
        if status == GenerationStatus.FAILED:
            error = (
                data.get("errorMessage")
                or data.get("error_message")
                or data.get("msg")
                or body.get("msg")
                or f"status={raw_status}"
            )

        return GenerationResult(
            provider=self.id,
            task_id=task_id,
            status=status,
            audio_url=audio_url,
            duration_seconds=float(duration_seconds) if duration_seconds else None,
            error=str(error) if error else None,
            actual_cost_usd=COST_PER_SONG_USD if status == GenerationStatus.SUCCEEDED else None,
            raw_payload=body,
            clips=clips,
        )

    def cost_estimate(self, params: GenerateParams) -> float:
        return COST_PER_SONG_USD
