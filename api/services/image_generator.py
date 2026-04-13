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


HEX_NAMES = {
    # Enough to translate typical persona palettes into words gpt-image-1
    # can reason about. Approximate match — closest primary name wins.
    "red": [(255, 0, 0)], "coral": [(255, 111, 97), (255, 127, 80)],
    "crimson": [(220, 20, 60)], "burgundy": [(128, 0, 32)],
    "orange": [(255, 165, 0)], "peach": [(255, 218, 185)],
    "amber": [(255, 191, 0)], "gold": [(255, 215, 0)],
    "yellow": [(255, 255, 0)], "cream": [(255, 253, 208)],
    "olive": [(128, 128, 0)], "mint": [(189, 252, 201)],
    "green": [(0, 128, 0)], "emerald": [(80, 200, 120)],
    "forest": [(34, 139, 34)], "teal": [(0, 128, 128)],
    "cyan": [(0, 255, 255)], "sky": [(135, 206, 235)],
    "blue": [(0, 0, 255)], "navy": [(0, 0, 128)],
    "slate-blue": [(106, 90, 205)], "indigo": [(75, 0, 130)],
    "violet": [(138, 43, 226)], "purple": [(128, 0, 128)],
    "lavender": [(230, 230, 250)], "magenta": [(255, 0, 255)],
    "pink": [(255, 192, 203)], "hot-pink": [(255, 105, 180)],
    "brown": [(139, 69, 19)], "tan": [(210, 180, 140)],
    "beige": [(245, 245, 220)], "ivory": [(255, 255, 240)],
    "white": [(255, 255, 255)], "gray": [(128, 128, 128)],
    "charcoal": [(54, 69, 79)], "black": [(0, 0, 0)],
    "silver": [(192, 192, 192)], "chrome": [(218, 223, 225)],
}


def _hex_to_name(hex_str: str) -> str:
    """Translate '#RRGGBB' to the closest human color word. Used so gpt-image-1
    gets 'coral, slate-blue, gold' instead of three opaque hex strings."""
    s = hex_str.strip().lstrip("#")
    if len(s) == 3:
        s = "".join(c * 2 for c in s)
    if len(s) != 6:
        return hex_str
    try:
        r, g, b = int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)
    except ValueError:
        return hex_str
    best_name = hex_str
    best_dist = float("inf")
    for name, refs in HEX_NAMES.items():
        for (rr, gg, bb) in refs:
            d = (r - rr) ** 2 + (g - gg) ** 2 + (b - bb) ** 2
            if d < best_dist:
                best_dist = d
                best_name = name
    return best_name


def _format_palette(palette: Any) -> str | None:
    """Turn a color_palette list into a natural-language descriptor."""
    if not isinstance(palette, list) or not palette:
        return None
    names: list[str] = []
    for p in palette:
        if not isinstance(p, str):
            continue
        if p.startswith("#"):
            names.append(_hex_to_name(p))
        else:
            names.append(p)
    if not names:
        return None
    # Dedupe preserving order
    seen = set()
    unique = [n for n in names if not (n in seen or seen.add(n))]
    return ", ".join(unique)


def _subject_description(persona: dict) -> str:
    """
    Compose the full "real human being, X" descriptor used by every prompt.
    Pulls ALL the rich visual/fashion fields — face, body, hair, ethnicity,
    gender, age, signature outfit, color palette, fabric inspirations,
    silhouette, styling mood, accessories, footwear. Ignored fields just
    get skipped — no "if one is present" shortcut like the old builder.
    """
    visual = persona.get("visual_dna") or {}
    fashion = persona.get("fashion_dna") or {}

    parts: list[str] = []
    if (gender := persona.get("gender_presentation")):
        parts.append(gender)
    if (age := persona.get("age")):
        parts.append(f"{age} years old")
    if (ethnicity := persona.get("ethnicity_heritage")):
        parts.append(ethnicity)
    if (face := visual.get("face_description")):
        parts.append(face)
    if (body := visual.get("body_presentation")):
        parts.append(body)
    if (hair := visual.get("hair_signature")):
        parts.append(hair)

    subject = ", ".join(parts) if parts else "musician"

    # OUTFIT — exploit every fashion field the schema defines.
    # Bug fix: fashion_style_summary lives in visual_dna, NOT fashion_dna.
    # The old builder looked in fashion_dna and silently dropped it.
    outfit_bits: list[str] = []
    if (summary := visual.get("fashion_style_summary")):
        outfit_bits.append(summary)
    if isinstance(fashion.get("core_garments"), list) and fashion["core_garments"]:
        outfit_bits.append("core pieces: " + ", ".join(fashion["core_garments"]))
    if isinstance(fashion.get("fabric_inspirations"), list) and fashion["fabric_inspirations"]:
        outfit_bits.append("fabrics: " + ", ".join(fashion["fabric_inspirations"]))
    if (silhouette := fashion.get("silhouette")):
        outfit_bits.append(f"silhouette: {silhouette}")
    if isinstance(fashion.get("accessories"), list) and fashion["accessories"]:
        outfit_bits.append("accessories: " + ", ".join(fashion["accessories"]))
    if isinstance(fashion.get("footwear"), list) and fashion["footwear"]:
        outfit_bits.append("footwear: " + ", ".join(fashion["footwear"]))
    if (styling_mood := fashion.get("styling_mood")):
        outfit_bits.append(f"styling mood: {styling_mood}")

    outfit = ""
    if outfit_bits:
        outfit = " — OUTFIT: " + "; ".join(outfit_bits)

    # PALETTE — translate hex codes to color names the model understands.
    palette_str = _format_palette(visual.get("color_palette"))
    palette = f" COLOR PALETTE: {palette_str} (these colors MUST appear in the outfit, backdrop, or lighting)." if palette_str else ""

    return subject + outfit + palette


def build_artist_portrait_prompt(persona: dict) -> str:
    """
    Turn a persona dict into a gpt-image-1 portrait prompt that produces
    a PHOTOREALISTIC result — a candid editorial photograph of an actual
    person, not illustration or AI art.

    gpt-image-1 (like DALL-E before it) has a strong default tendency
    toward illustrative output. Countering that requires: explicit
    "photograph" language, camera specifics (body + lens), lighting,
    skin-texture cues, AND explicit anti-illustration directives.

    Every rich field in the persona — fashion_style_summary, color_palette,
    fabric_inspirations, silhouette, accessories, footwear, styling_mood,
    art_direction — flows through _subject_description. Dropping any of
    them is a bug; the persona schema exists to drive real distinctiveness.
    """
    visual = persona.get("visual_dna") or {}
    subject = _subject_description(persona)

    # The art_direction field often says things like "moody urban night
    # photography" which IS photographic — fold it in as scene context.
    scene = visual.get("art_direction") or "natural daylight studio setting"

    return (
        f"I NEED a real, unedited candid editorial photograph. "
        f"Subject: a real human being — {subject}. "
        f"Scene / art direction: {scene}. "
        f"The outfit must be clearly visible and styled with intent — "
        f"this is a FASHION EDITORIAL shoot where the wardrobe is the point, "
        f"not a passport photo. Hero garment reads first, accessories "
        f"support, palette carries through the whole frame. "
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
        f"DO NOT default to a generic plain t-shirt + blazer look if "
        f"the persona specifies richer styling. "
        f"This MUST look like an actual photograph of a real person "
        f"that could appear in a physical magazine. "
        f"No text, no watermarks, no logos, no graphic overlays."
    )


def build_8_view_prompts(persona: dict) -> list[tuple[str, str]]:
    """
    PRD §20 — produce 8 per-angle prompts that describe the SAME subject
    from 8 canonical angles. Used to build the artist reference sheet.

    Every view uses the same rich _subject_description so outfit, color
    palette, fabric, silhouette, and accessories stay consistent across
    all 8 angles. Face consistency is locked via gpt-image-1's /edits
    endpoint with a reference image (handled in the router).
    """
    subject = _subject_description(persona)
    visual = persona.get("visual_dna") or {}
    scene = visual.get("art_direction") or "natural daylight studio setting"

    # Shared photo-realism preamble (same across all 8 views)
    photo_style = (
        "Shot on Canon EOS R5 with 85mm f/1.4 prime lens, full frame, "
        "natural soft lighting, sharp focus, visible skin texture and pores, "
        "authentic human details, documentary realism, editorial magazine quality"
    )

    anti_illustration = (
        "DO NOT generate illustration, cartoon, 3D render, CGI, or AI-art plastic skin. "
        "DO NOT default to a plain t-shirt + blazer if the persona specifies richer styling. "
        "This MUST look like an actual photograph of a real person. "
        "No text, no watermarks, no graphic overlays."
    )

    preamble = (
        f"I NEED a real candid editorial photograph. Subject: a real human being — {subject}. "
        f"Scene / art direction: {scene}. "
        f"The outfit is the point of this shoot — clearly visible, styled with intent, "
        f"hero garment reads first, palette carries through. "
    )

    views: list[tuple[str, str]] = [
        ("front",
         f"{preamble}Framing: straight-on FRONT view, head and shoulders, subject facing the camera directly, "
         f"eyes looking into the lens. {photo_style}. {anti_illustration}"),

        ("side_l",
         f"{preamble}Framing: LEFT PROFILE side view, subject facing to the camera's right, showing the left side of the face clearly, "
         f"head and shoulders framing. {photo_style}. {anti_illustration}"),

        ("side_r",
         f"{preamble}Framing: RIGHT PROFILE side view, subject facing to the camera's left, showing the right side of the face clearly, "
         f"head and shoulders framing. {photo_style}. {anti_illustration}"),

        ("back",
         f"{preamble}Framing: BACK view, subject facing away from the camera, showing the back of the head and shoulders, "
         f"hair and neckline visible. {photo_style}. {anti_illustration}"),

        ("top_l",
         f"{preamble}Framing: HIGH-ANGLE shot from UPPER LEFT, camera positioned above and to the left, looking down at the subject, "
         f"subject's face tilted up slightly toward the lens. {photo_style}. {anti_illustration}"),

        ("top_r",
         f"{preamble}Framing: HIGH-ANGLE shot from UPPER RIGHT, camera positioned above and to the right, looking down at the subject, "
         f"subject's face tilted up slightly toward the lens. {photo_style}. {anti_illustration}"),

        ("bottom_l",
         f"{preamble}Framing: LOW-ANGLE shot from LOWER LEFT, camera positioned below and to the left, looking up at the subject, "
         f"dramatic heroic angle. {photo_style}. {anti_illustration}"),

        ("bottom_r",
         f"{preamble}Framing: LOW-ANGLE shot from LOWER RIGHT, camera positioned below and to the right, looking up at the subject, "
         f"dramatic heroic angle. {photo_style}. {anti_illustration}"),
    ]
    return views


def composite_8_view_sheet(view_bytes_by_angle: dict[str, bytes]) -> bytes | None:
    """
    Stitch 8 per-view PNGs into a single 4×2 composite sheet.

    Input dict keys must match the canonical angle codes:
      front, side_l, side_r, back, top_l, top_r, bottom_l, bottom_r

    Layout:
      row 1 (top):    front    side_l   side_r   back
      row 2 (bottom): top_l    top_r    bottom_l bottom_r

    Each cell is resized to 512×512 so the final sheet is 2048×1024.
    Returns PNG bytes, or None if PIL isn't available or all views are
    missing.
    """
    try:
        from PIL import Image
    except ImportError:
        logger.error("[composite] PIL not installed — pip install Pillow")
        return None

    CANONICAL_ORDER = [
        "front", "side_l", "side_r", "back",
        "top_l", "top_r", "bottom_l", "bottom_r",
    ]
    CELL = 512
    COLS = 4
    ROWS = 2

    sheet = Image.new("RGB", (CELL * COLS, CELL * ROWS), color=(15, 15, 17))
    placed = 0
    for i, angle in enumerate(CANONICAL_ORDER):
        view_bytes = view_bytes_by_angle.get(angle)
        if not view_bytes:
            continue
        try:
            img = Image.open(io.BytesIO(view_bytes)).convert("RGB")
            img.thumbnail((CELL, CELL), Image.LANCZOS)
            # Center within the cell
            col = i % COLS
            row = i // COLS
            x = col * CELL + (CELL - img.width) // 2
            y = row * CELL + (CELL - img.height) // 2
            sheet.paste(img, (x, y))
            placed += 1
        except Exception:
            logger.exception("[composite] failed to place %s", angle)

    if placed == 0:
        return None

    out = io.BytesIO()
    sheet.save(out, format="PNG", optimize=True)
    return out.getvalue()


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
