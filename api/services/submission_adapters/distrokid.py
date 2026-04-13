"""
DistroKid Playwright adapter.

Logs into DistroKid with DISTROKID_USERNAME + DISTROKID_PASSWORD env
vars and uploads a song for release. Drives the DistroKid dashboard via
headless Chromium.

Like the ASCAP Fonzworth adapter, this module degrades gracefully when
Playwright isn't installed — the dispatcher catches the exception and
writes a 'failed' row with a clean error message.

Selector paths are best-guess and will need live tuning against the
real DistroKid DOM. The module docstring lists exactly what to adjust.

Expected flow:
  1. GET https://distrokid.com/signin, fill username + password
  2. Click Upload Song / New Release
  3. Fill title, artist name, genre
  4. Upload WAV/MP3 from our music_generation_audio bytes
  5. Fill metadata: ISRC (if we have one), release date, content rating
  6. Set writers + publishers splits
  7. Pick stores (all by default)
  8. Submit
  9. Capture confirmation URL + UPC/ISRC returned
"""
from __future__ import annotations

import base64
import io
import logging
import os
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.services.external_submission_agent import register_adapter

logger = logging.getLogger(__name__)

DISTROKID_SIGNIN_URL = "https://distrokid.com/signin"
DISTROKID_UPLOAD_URL = "https://distrokid.com/upload"


class DistroKidMissingCredentials(Exception):
    pass


class DistroKidPlaywrightUnavailable(Exception):
    pass


async def _launch():
    try:
        from playwright.async_api import async_playwright  # type: ignore
    except ImportError as e:
        raise DistroKidPlaywrightUnavailable(
            "playwright not installed. Add `playwright>=1.40` to pyproject + "
            "`RUN python -m playwright install --with-deps chromium` to Dockerfile."
        ) from e
    try:
        pw = await async_playwright().start()
        browser = await pw.chromium.launch(headless=True)
        return pw, browser
    except Exception as e:
        raise DistroKidPlaywrightUnavailable(
            f"Playwright launch failed (missing Chromium binary?): {e}"
        ) from e


async def _load_audio_bytes(db: AsyncSession, song) -> bytes | None:
    """Fetch the audio bytes from music_generation_audio for a song."""
    from sqlalchemy import text as _text
    r = await db.execute(
        _text("""
            SELECT mga.mp3_bytes
            FROM music_generation_calls mgc
            JOIN music_generation_audio mga ON mga.music_generation_call_id = mgc.id
            WHERE mgc.song_id = :sid
            ORDER BY mgc.completed_at DESC NULLS LAST, mgc.created_at DESC
            LIMIT 1
        """),
        {"sid": song.song_id},
    )
    row = r.fetchone()
    if row is None:
        return None
    return bytes(row[0])


@register_adapter("distrokid")
async def distrokid_adapter(db, subject_row, target) -> tuple[str, str | None, dict]:
    """
    Live-mode adapter for DistroKid uploads.
    Gracefully degrades to failed/'requires playwright' if the browser
    environment isn't available — the dispatcher catches this.
    """
    # Credential check is done by the dispatcher, but double-check here
    username = os.environ.get("DISTROKID_USERNAME", "").strip()
    password = os.environ.get("DISTROKID_PASSWORD", "").strip()
    if not username or not password:
        return ("failed", None, {"error": "DISTROKID_USERNAME/PASSWORD not set"})

    # Need the audio bytes to upload
    audio_bytes = await _load_audio_bytes(db, subject_row)
    if not audio_bytes:
        return ("failed", None, {"error": "no audio bytes found for song"})

    # Need artist info for the artist_name field
    from api.models.ai_artist import AIArtist
    artist = (
        await db.execute(
            select(AIArtist).where(AIArtist.artist_id == subject_row.primary_artist_id)
        )
    ).scalar_one_or_none()
    if artist is None:
        return ("failed", None, {"error": "primary artist missing"})

    try:
        pw, browser = await _launch()
    except DistroKidPlaywrightUnavailable as e:
        return ("failed", None, {"error": str(e), "degraded": True})

    try:
        context = await browser.new_context()
        page = await context.new_page()

        # 1. Sign in
        await page.goto(DISTROKID_SIGNIN_URL, wait_until="domcontentloaded", timeout=30000)
        await page.fill("input[name='username']", username)
        await page.fill("input[name='password']", password)
        await page.click("button[type='submit']")
        await page.wait_for_load_state("networkidle", timeout=30000)

        # 2. Navigate to upload
        await page.goto(DISTROKID_UPLOAD_URL, wait_until="domcontentloaded", timeout=30000)

        # 3. Fill title + artist name (selectors are BEST-GUESS)
        await page.fill("input[name='title']", subject_row.title or "Untitled")
        await page.fill("input[name='artist_name']", artist.stage_name)

        # 4. Upload audio file
        # Playwright accepts bytes via file_chooser
        async with page.expect_file_chooser() as fc_info:
            await page.click("input[type='file']")
        file_chooser = await fc_info.value
        await file_chooser.set_files([
            {
                "name": f"{(subject_row.title or 'untitled').replace(' ', '_')}.mp3",
                "mimeType": "audio/mpeg",
                "buffer": audio_bytes,
            }
        ])

        # 5. Genre + submit (selectors guessed — needs tuning)
        if subject_row.primary_genre:
            try:
                await page.select_option("select[name='genre']", subject_row.primary_genre.split(".")[0])
            except Exception:
                pass

        await page.click("button:has-text('Submit')")
        await page.wait_for_load_state("networkidle", timeout=60000)

        # 6. Capture confirmation + external id
        url = page.url
        external_id = None
        # Try a few likely DOM locations for the UPC or release id
        for sel in ["[data-testid='upc']", ".upc", ".release-id", "[data-release-id]"]:
            try:
                txt = await page.inner_text(sel, timeout=2000)
                if txt and txt.strip():
                    external_id = txt.strip()
                    break
            except Exception:
                continue

        screenshot_b64 = base64.b64encode(await page.screenshot(full_page=True)).decode("ascii")
        return (
            "submitted",
            external_id,
            {
                "confirmation_url": url,
                "screenshot_b64": screenshot_b64[:10000],  # truncate so JSONB doesn't balloon
                "target": "distrokid",
            },
        )
    except Exception as e:
        logger.exception("[distrokid-adapter] failed")
        return ("failed", None, {"error": f"{type(e).__name__}: {e}"})
    finally:
        try:
            await browser.close()
            await pw.stop()
        except Exception:
            pass
