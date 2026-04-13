"""
Image generation via openai_cli_proxy (preferred) or direct OpenAI (fallback).

Used for artist portraits (§20 visual reference sheets) and song covers.
Writes bytes into visual_asset_blobs + a metadata row in
artist_visual_assets. If neither the proxy nor OpenAI is configured,
logs a warning and returns None so the caller can proceed with a
NULL portrait/cover field and escalate to the CEO.
"""
from __future__ import annotations

import base64
import json
import logging
import os
import uuid as _uuid
from dataclasses import dataclass
from typing import Any

import httpx
from sqlalchemy import text as _text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


PROXY_URL_ENV = "OPENAI_CLI_PROXY_URL"
PROXY_KEY_ENV = "OPENAI_CLI_PROXY_KEY"
DIRECT_KEY_ENV = "OPENAI_API_KEY"

# DALL-E 3 defaults — standard quality is $0.040/image at 1024x1024.
DEFAULT_MODEL = "dall-e-3"
DEFAULT_SIZE = "1024x1024"
DEFAULT_QUALITY = "standard"


@dataclass
class ImageResult:
    asset_id: _uuid.UUID
    storage_url: str  # backend-relative streaming path
    provider: str
    bytes_len: int


def _get_client_config() -> tuple[str, str, str] | None:
    """Return (base_url, auth_header_value, provider_label) or None if unavailable."""
    proxy_url = os.environ.get(PROXY_URL_ENV, "").strip()
    proxy_key = os.environ.get(PROXY_KEY_ENV, "").strip()
    if proxy_url and proxy_key:
        return (proxy_url.rstrip("/"), f"Bearer {proxy_key}", "openai_cli_proxy")
    direct_key = os.environ.get(DIRECT_KEY_ENV, "").strip()
    if direct_key:
        return ("https://api.openai.com", f"Bearer {direct_key}", "openai_direct")
    return None


async def _call_image_api(
    prompt: str,
    *,
    model: str = DEFAULT_MODEL,
    size: str = DEFAULT_SIZE,
    quality: str = DEFAULT_QUALITY,
) -> tuple[bytes, str] | None:
    """
    Call the image API. Returns (bytes, content_type) on success, None
    on failure. Supports both a proxy and direct OpenAI at the standard
    POST /v1/images/generations shape.
    """
    config = _get_client_config()
    if config is None:
        logger.warning("[image-gen] no OpenAI proxy or direct key configured — skipping")
        return None
    base_url, auth, provider = config

    payload = {
        "model": model,
        "prompt": prompt[:4000],  # DALL-E 3 hard cap
        "n": 1,
        "size": size,
        "quality": quality,
        "response_format": "b64_json",  # get bytes inline, no second fetch
    }
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            r = await client.post(
                f"{base_url}/v1/images/generations",
                json=payload,
                headers={"Authorization": auth, "Content-Type": "application/json"},
            )
            if r.status_code != 200:
                logger.error("[image-gen] %s returned %s: %s", provider, r.status_code, r.text[:400])
                return None
            body = r.json()
            data = body.get("data") or []
            if not data:
                logger.error("[image-gen] %s returned no data: %s", provider, body)
                return None
            b64 = data[0].get("b64_json")
            if not b64:
                # Some providers return `url` instead — fetch it
                url = data[0].get("url")
                if not url:
                    return None
                fr = await client.get(url)
                if fr.status_code != 200:
                    return None
                return fr.content, fr.headers.get("content-type", "image/png")
            image_bytes = base64.b64decode(b64)
            return image_bytes, "image/png"
    except Exception:
        logger.exception("[image-gen] %s call failed", provider)
        return None


async def generate_and_store_image(
    db: AsyncSession,
    *,
    artist_id: _uuid.UUID,
    asset_type: str,         # 'reference_sheet' | 'song_artwork' | 'avatar' | 'promo'
    prompt: str,
    parent_sheet_id: _uuid.UUID | None = None,
    view_angle: str | None = None,
) -> ImageResult | None:
    """
    Generate an image, persist an artist_visual_assets row, store the
    bytes in visual_asset_blobs, and return the asset_id + streaming
    URL. Returns None on any failure (caller decides whether to proceed
    without an image or escalate).
    """
    result = await _call_image_api(prompt)
    if result is None:
        return None
    image_bytes, content_type = result

    asset_id = _uuid.uuid4()
    provider = "openai_dalle3"
    config = _get_client_config()
    if config:
        provider = config[2]  # openai_cli_proxy or openai_direct

    # Write the metadata row
    await db.execute(
        _text("""
            INSERT INTO artist_visual_assets (
                asset_id, artist_id, asset_type, view_angle, parent_sheet_id,
                storage_url, storage_checksum, generation_provider,
                source_prompt, is_canonical_sheet
            ) VALUES (
                :asset_id, :artist_id, :asset_type, :view, :parent,
                :storage_url, :checksum, :provider, :prompt, :canonical
            )
        """),
        {
            "asset_id": asset_id,
            "artist_id": artist_id,
            "asset_type": asset_type,
            "view": view_angle,
            "parent": parent_sheet_id,
            "storage_url": f"/api/v1/admin/visual/{asset_id}.png",
            "checksum": None,
            "provider": provider,
            "prompt": prompt[:2000],
            "canonical": asset_type == "reference_sheet",
        },
    )
    # Write the blob
    await db.execute(
        _text("""
            INSERT INTO visual_asset_blobs
              (asset_id, content_type, size_bytes, image_bytes, source_url)
            VALUES (:asset_id, :ct, :sz, :bytes, :url)
        """),
        {
            "asset_id": asset_id,
            "ct": content_type,
            "sz": len(image_bytes),
            "bytes": image_bytes,
            "url": None,  # b64-inline, no source URL
        },
    )

    logger.info(
        "[image-gen] stored %s for artist=%s size=%d provider=%s",
        asset_type, str(artist_id)[:8], len(image_bytes), provider,
    )
    return ImageResult(
        asset_id=asset_id,
        storage_url=f"/api/v1/admin/visual/{asset_id}.png",
        provider=provider,
        bytes_len=len(image_bytes),
    )


def build_artist_portrait_prompt(persona: dict) -> str:
    """Turn a persona dict into a DALL-E 3 portrait prompt."""
    visual = persona.get("visual_dna") or {}
    fashion = persona.get("fashion_dna") or {}
    parts: list[str] = []
    if (face := visual.get("face_description")):
        parts.append(face)
    if (body := visual.get("body_presentation")):
        parts.append(body)
    if (hair := visual.get("hair_signature")):
        parts.append(hair)
    if fashion.get("style_summary") or fashion.get("core_garments"):
        style = fashion.get("style_summary") or ", ".join(fashion.get("core_garments") or [])
        if style:
            parts.append(f"wearing {style}")
    if (palette := visual.get("color_palette")):
        if isinstance(palette, list):
            parts.append(f"color palette {', '.join(palette)}")
    if (art_dir := visual.get("art_direction")):
        parts.append(art_dir)

    if not parts:
        parts.append("portrait of a music artist")

    descriptor = ", ".join(parts)
    return (
        f"Professional editorial portrait of {descriptor}. "
        f"Single subject, head and shoulders framing, direct gaze, "
        f"high-end magazine lighting, sharp focus, photorealistic, "
        f"neutral studio background. No text, no watermarks."
    )


def build_song_cover_prompt(
    *,
    title: str,
    genre: str,
    artist_visual: dict | None,
    themes: list[str] | None,
) -> str:
    """Turn a song into a cover-art prompt."""
    mood_parts: list[str] = []
    if themes:
        mood_parts.extend(themes[:3])
    if artist_visual:
        if (pal := artist_visual.get("color_palette")):
            if isinstance(pal, list):
                mood_parts.append(f"palette {', '.join(pal)}")
        if (art_dir := artist_visual.get("art_direction")):
            mood_parts.append(art_dir)

    mood = " | ".join(mood_parts) if mood_parts else f"{genre} mood"
    return (
        f"Album cover art for a {genre} song titled '{title}'. "
        f"Mood: {mood}. "
        f"Square composition, bold visual hook, suitable for thumbnail "
        f"at 300px. No text overlay, no watermarks, editorial album art "
        f"quality. Instagram-ready."
    )
