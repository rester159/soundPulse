"""
Image generation via OpenAI gpt-image-1 (with openai_cli_proxy fallback).

gpt-image-1 is OpenAI's native multimodal image model — noticeably more
realistic than DALL-E 3 for human portraits, and the only OpenAI model
that supports reference-image conditioning via /v1/images/edits. That's
what makes face-locked 8-view reference sheets possible without adding
a third-party provider like Flux-PuLID.

Used for artist portraits (§20 visual reference sheets) and song covers.
Writes bytes into visual_asset_blobs + a metadata row in
artist_visual_assets. If no OpenAI credentials are configured, logs a
warning and returns None so the caller can proceed with a NULL field
and escalate to the CEO.
"""
from __future__ import annotations

import base64
import io
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

# gpt-image-1 defaults
#   - Quality tiers: 'low' | 'medium' | 'high' | 'auto'
#   - 'high' at 1024×1024 ≈ $0.167/image — worth it for portraits
#   - 'medium' ≈ $0.042/image — good for song covers
#   - Returns base64 JSON by default
DEFAULT_MODEL = "gpt-image-1"
DEFAULT_SIZE = "1024x1024"
DEFAULT_QUALITY = "high"


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
    reference_image_bytes: bytes | None = None,
) -> tuple[bytes, str] | None:
    """
    Call OpenAI gpt-image-1 for text-to-image OR reference-to-image.

    Without `reference_image_bytes`: hits /v1/images/generations
      body: {model, prompt, size, quality, n, output_format}
      response: {data: [{b64_json}]}  (gpt-image-1 always returns b64)

    With `reference_image_bytes`: hits /v1/images/edits (multipart)
      form: image=<png bytes>, prompt, model, size, quality, n
      response: {data: [{b64_json}]}

    Returns (bytes, content_type) or None on failure.
    """
    config = _get_client_config()
    if config is None:
        logger.warning("[image-gen] no OpenAI proxy or direct key configured — skipping")
        return None
    base_url, auth, provider = config

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            if reference_image_bytes is None:
                # Text-to-image via /v1/images/generations
                payload = {
                    "model": model,
                    "prompt": prompt[:32000],  # gpt-image-1 supports long prompts
                    "n": 1,
                    "size": size,
                    "quality": quality,
                }
                r = await client.post(
                    f"{base_url}/v1/images/generations",
                    json=payload,
                    headers={"Authorization": auth, "Content-Type": "application/json"},
                )
            else:
                # Reference-to-image via /v1/images/edits (multipart form-data)
                files = {
                    "image": ("reference.png", reference_image_bytes, "image/png"),
                }
                form_data = {
                    "model": model,
                    "prompt": prompt[:32000],
                    "n": "1",
                    "size": size,
                }
                # NOTE: the edits endpoint doesn't accept quality for
                # gpt-image-1 (community-reported). We omit it.
                r = await client.post(
                    f"{base_url}/v1/images/edits",
                    files=files,
                    data=form_data,
                    headers={"Authorization": auth},  # don't set Content-Type, httpx handles multipart
                )

            if r.status_code != 200:
                logger.error("[image-gen] %s returned %s: %s", provider, r.status_code, r.text[:600])
                return None
            body = r.json()
            data = body.get("data") or []
            if not data:
                logger.error("[image-gen] %s returned no data: %s", provider, body)
                return None
            b64 = data[0].get("b64_json")
            if not b64:
                # Fallback — some deployments return `url`
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
    quality: str = DEFAULT_QUALITY,
    reference_image_bytes: bytes | None = None,
) -> ImageResult | None:
    """
    Generate an image, persist an artist_visual_assets row, store the
    bytes in visual_asset_blobs, and return the asset_id + streaming
    URL. Returns None on any failure (caller decides whether to proceed
    without an image or escalate).

    Pass `reference_image_bytes` to hit /v1/images/edits with the
    reference locked (used by the face-locked 8-view sheet flow).
    """
    result = await _call_image_api(
        prompt,
        quality=quality,
        reference_image_bytes=reference_image_bytes,
    )
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
    """
    Turn a persona dict into a DALL-E 3 portrait prompt that produces
    a PHOTOREALISTIC result — a candid editorial photograph of an actual
    person, not illustration or AI art.

    DALL-E 3 has a strong default tendency toward illustrative output.
    Countering that requires: explicit "photograph" language, camera
    specifics (body + lens), lighting specifics, skin-texture cues,
    AND explicit anti-illustration directives. Without ALL of these
    the model drifts back to stylized output.
    """
    visual = persona.get("visual_dna") or {}
    fashion = persona.get("fashion_dna") or {}
    subject_parts: list[str] = []

    # Age + gender + ethnicity go first so DALL-E locks the person type
    if (gender := persona.get("gender_presentation")):
        subject_parts.append(gender)
    if (age := persona.get("age")):
        subject_parts.append(f"{age} years old")
    if (ethnicity := persona.get("ethnicity_heritage")):
        subject_parts.append(ethnicity)

    if (face := visual.get("face_description")):
        subject_parts.append(face)
    if (body := visual.get("body_presentation")):
        subject_parts.append(body)
    if (hair := visual.get("hair_signature")):
        subject_parts.append(hair)

    outfit_parts: list[str] = []
    if fashion.get("style_summary"):
        outfit_parts.append(fashion["style_summary"])
    elif fashion.get("core_garments"):
        outfit_parts.append(", ".join(fashion["core_garments"]))

    subject = ", ".join(subject_parts) if subject_parts else "musician"
    outfit = f" wearing {', '.join(outfit_parts)}" if outfit_parts else ""

    # The art_direction field often says things like "moody urban night
    # photography" which IS photographic — fold it in as scene context.
    scene = visual.get("art_direction") or "natural daylight studio setting"

    return (
        f"I NEED a real, unedited candid photograph. "
        f"Subject: a real human being, {subject}{outfit}. "
        f"Scene: {scene}. "
        f"This is a professional editorial portrait photograph, "
        f"shot on a Canon EOS R5 with an 85mm f/1.4 prime lens, "
        f"full frame, shallow depth of field, natural soft lighting, "
        f"golden hour or softbox key light, "
        f"head and shoulders framing, direct eye contact with the lens. "
        f"Skin shows natural texture, pores, subtle imperfections, "
        f"authentic human details. Sharp focus on the eyes. "
        f"Documentary realism, unretouched, film grain acceptable, "
        f"in the style of a Vogue or Rolling Stone cover shoot. "
        f"DO NOT generate illustration. "
        f"DO NOT generate cartoon, anime, or stylized art. "
        f"DO NOT generate 3D render, CGI, or digital painting. "
        f"DO NOT generate AI-art-looking smooth plastic skin. "
        f"This MUST look like an actual photograph of a real person "
        f"that could appear in a physical magazine. "
        f"No text, no watermarks, no logos, no graphic overlays."
    )


def build_8_view_prompts(persona: dict) -> list[tuple[str, str]]:
    """
    PRD §20 — produce 8 per-angle prompts that describe the SAME subject
    from 8 canonical angles. Used to build the artist reference sheet.

    Returns a list of (view_angle, prompt) tuples. Every prompt shares
    the same subject description to maximize face consistency (DALL-E 3
    doesn't support reference-image locking, so the only lever is
    describing the subject identically across prompts).

    For true face consistency we'll need Flux-PuLID via Replicate in a
    follow-up. For now DALL-E 3 gives good-enough per-view realism but
    face details will drift between angles.
    """
    visual = persona.get("visual_dna") or {}
    fashion = persona.get("fashion_dna") or {}

    subject_parts: list[str] = []
    if (gender := persona.get("gender_presentation")):
        subject_parts.append(gender)
    if (age := persona.get("age")):
        subject_parts.append(f"{age} years old")
    if (ethnicity := persona.get("ethnicity_heritage")):
        subject_parts.append(ethnicity)
    if (face := visual.get("face_description")):
        subject_parts.append(face)
    if (body := visual.get("body_presentation")):
        subject_parts.append(body)
    if (hair := visual.get("hair_signature")):
        subject_parts.append(hair)

    outfit_parts: list[str] = []
    if fashion.get("style_summary"):
        outfit_parts.append(fashion["style_summary"])
    elif fashion.get("core_garments"):
        outfit_parts.append(", ".join(fashion["core_garments"]))

    subject = ", ".join(subject_parts) if subject_parts else "musician"
    outfit = f" wearing {', '.join(outfit_parts)}" if outfit_parts else ""

    # Shared photo-realism preamble (same across all 8 views)
    photo_style = (
        "Shot on Canon EOS R5 with 85mm f/1.4 prime lens, full frame, "
        "natural soft lighting, sharp focus, visible skin texture and pores, "
        "authentic human details, documentary realism, editorial magazine quality"
    )

    anti_illustration = (
        "DO NOT generate illustration, cartoon, 3D render, CGI, or AI-art plastic skin. "
        "This MUST look like an actual photograph of a real person. "
        "No text, no watermarks, no graphic overlays."
    )

    views: list[tuple[str, str]] = [
        ("front",
         f"I NEED a real candid photograph. Subject: a real human being, {subject}{outfit}. "
         f"Framing: straight-on FRONT view, head and shoulders, subject facing the camera directly, "
         f"eyes looking into the lens. {photo_style}. {anti_illustration}"),

        ("side_l",
         f"I NEED a real candid photograph. Same subject as a multi-angle photoshoot: a real human being, {subject}{outfit}. "
         f"Framing: LEFT PROFILE side view, subject facing to the camera's right, showing the left side of the face clearly, "
         f"head and shoulders framing. {photo_style}. {anti_illustration}"),

        ("side_r",
         f"I NEED a real candid photograph. Same subject as a multi-angle photoshoot: a real human being, {subject}{outfit}. "
         f"Framing: RIGHT PROFILE side view, subject facing to the camera's left, showing the right side of the face clearly, "
         f"head and shoulders framing. {photo_style}. {anti_illustration}"),

        ("back",
         f"I NEED a real candid photograph. Same subject as a multi-angle photoshoot: a real human being, {subject}{outfit}. "
         f"Framing: BACK view, subject facing away from the camera, showing the back of the head and shoulders, "
         f"hair and neckline visible. {photo_style}. {anti_illustration}"),

        ("top_l",
         f"I NEED a real candid photograph. Same subject as a multi-angle photoshoot: a real human being, {subject}{outfit}. "
         f"Framing: HIGH-ANGLE shot from UPPER LEFT, camera positioned above and to the left, looking down at the subject, "
         f"subject's face tilted up slightly toward the lens. {photo_style}. {anti_illustration}"),

        ("top_r",
         f"I NEED a real candid photograph. Same subject as a multi-angle photoshoot: a real human being, {subject}{outfit}. "
         f"Framing: HIGH-ANGLE shot from UPPER RIGHT, camera positioned above and to the right, looking down at the subject, "
         f"subject's face tilted up slightly toward the lens. {photo_style}. {anti_illustration}"),

        ("bottom_l",
         f"I NEED a real candid photograph. Same subject as a multi-angle photoshoot: a real human being, {subject}{outfit}. "
         f"Framing: LOW-ANGLE shot from LOWER LEFT, camera positioned below and to the left, looking up at the subject, "
         f"dramatic heroic angle. {photo_style}. {anti_illustration}"),

        ("bottom_r",
         f"I NEED a real candid photograph. Same subject as a multi-angle photoshoot: a real human being, {subject}{outfit}. "
         f"Framing: LOW-ANGLE shot from LOWER RIGHT, camera positioned below and to the right, looking up at the subject, "
         f"dramatic heroic angle. {photo_style}. {anti_illustration}"),
    ]
    return views


def build_song_cover_prompt(
    *,
    title: str,
    genre: str,
    artist_visual: dict | None,
    themes: list[str] | None,
) -> str:
    """
    Turn a song into a cover-art prompt. Covers lean photographic for
    most contemporary genres (pop/hip-hop/country/rock/reggae/R&B)
    since that's what works on Spotify thumbnails. Instrumental/
    orchestral genres get stylized treatment.
    """
    mood_parts: list[str] = []
    if themes:
        mood_parts.extend(themes[:3])
    mood = ", ".join(mood_parts) if mood_parts else f"{genre} mood"

    # Decide photographic vs stylized based on genre
    genre_lower = (genre or "").lower()
    stylized_genres = ("classical", "ambient", "orchestral", "new-age",
                       "experimental", "soundtrack", "score")
    is_stylized = any(tok in genre_lower for tok in stylized_genres)

    scene_hint = ""
    if artist_visual:
        if (art_dir := artist_visual.get("art_direction")):
            scene_hint = f" Scene reference: {art_dir}."
        pal = artist_visual.get("color_palette")
        if isinstance(pal, list) and pal:
            scene_hint += f" Palette: {', '.join(pal)}."

    if is_stylized:
        return (
            f"Album cover artwork for an instrumental {genre} piece titled '{title}'. "
            f"Mood: {mood}.{scene_hint} "
            f"Square composition, atmospheric, evocative, editorial album art "
            f"quality. High detail, bold visual hook. "
            f"No text overlay, no watermarks, no logos."
        )

    # Photographic path for vocal/mainstream genres
    return (
        f"Photographic album cover for a {genre} song titled '{title}'. "
        f"Mood: {mood}.{scene_hint} "
        f"This is a real photograph in the style of a Spotify editorial "
        f"playlist cover — shot on 35mm film or a full-frame digital "
        f"camera, natural lighting, candid human or environmental scene, "
        f"sharp focus, documentary realism. Square 1:1 composition, "
        f"strong focal point that reads at 300px thumbnail size. "
        f"DO NOT include illustration, cartoon, 3D render, AI-art looking "
        f"plastic surfaces, or text overlays. "
        f"Real photograph aesthetic, magazine-grade quality, "
        f"no watermarks, no logos."
    )
