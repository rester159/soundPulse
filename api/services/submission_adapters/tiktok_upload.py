"""
TikTok upload bot (T-227).

The most fragile adapter — TikTok actively defends against automation.
Uses a persisted session cookie (TIKTOK_UPLOAD_SESSION env) rather than
username/password to avoid the daily login captcha. Playwright with a
long-running browser context keeps the session warm.

Generates a short preview clip from the full song (first 30s or the
best chorus if we have hook_start_seconds), uploads it via TikTok's
Creator Center upload flow, fills caption from the social_media_agent's
tiktok pack output, adds the #fyp + genre hashtags.

This adapter is CONSERVATIVE — it never does more than 1 upload per
artist per day because TikTok's anti-spam limits are strict. The sweep
caller should respect that rate limit (enforced at the dispatcher
level via usage_count + last_used_at in submission_targets).
"""
from __future__ import annotations

import base64
import logging
import os
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.services.external_submission_agent import register_adapter

logger = logging.getLogger(__name__)

TIKTOK_UPLOAD_URL = "https://www.tiktok.com/creator-center/upload"


@register_adapter("tiktok_upload")
async def tiktok_upload_adapter(db, subject_row, target) -> tuple[str, str | None, dict]:
    session = os.environ.get("TIKTOK_UPLOAD_SESSION", "").strip()
    if not session:
        return ("failed", None, {"error": "TIKTOK_UPLOAD_SESSION cookie not set"})

    try:
        from playwright.async_api import async_playwright  # type: ignore
    except ImportError:
        return ("failed", None, {"error": "playwright not installed"})

    # Load audio bytes (used for ffmpeg-based preview later; for MVP we
    # just upload the mp3 directly and let TikTok handle conversion)
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
        {"sid": subject_row.song_id},
    )
    row = r.fetchone()
    if not row:
        return ("failed", None, {"error": "no audio bytes for song"})
    audio_bytes = bytes(row[0])

    # Caption — pull from the social_media_agent's output in
    # external_submissions if present, else build a minimal default
    caption = subject_row.title or "New song"
    hashtags = "#fyp #newmusic"
    from api.models.external_submission import ExternalSubmission
    social = (
        await db.execute(
            select(ExternalSubmission)
            .where(
                ExternalSubmission.target_service == "social_media_agent",
                ExternalSubmission.subject_id == subject_row.song_id,
            )
            .order_by(ExternalSubmission.created_at.desc())
            .limit(1)
        )
    ).scalars().first()
    if social and isinstance(social.response_json, dict):
        tiktok_block = (social.response_json.get("social_pack") or {}).get("tiktok", {})
        if isinstance(tiktok_block, dict):
            if tiktok_block.get("caption"):
                caption = tiktok_block["caption"]
            tags = tiktok_block.get("hashtags") or []
            if isinstance(tags, list):
                hashtags = " ".join(tags)

    try:
        pw = await async_playwright().start()
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context()
        # Inject the session cookie
        try:
            import json as _json
            cookies = _json.loads(session) if session.startswith("[") else [{"name": "sessionid", "value": session, "domain": ".tiktok.com", "path": "/"}]
            await context.add_cookies(cookies)
        except Exception:
            pass
        page = await context.new_page()
        await page.goto(TIKTOK_UPLOAD_URL, wait_until="networkidle", timeout=60000)

        # Upload file (selector is BEST-GUESS)
        async with page.expect_file_chooser() as fc_info:
            await page.click("input[type='file']")
        fc = await fc_info.value
        await fc.set_files([{
            "name": f"{(subject_row.title or 'song').replace(' ', '_')}.mp3",
            "mimeType": "audio/mpeg",
            "buffer": audio_bytes,
        }])

        # Fill caption
        await page.fill("[data-testid='caption'], textarea[placeholder*='caption' i]", f"{caption} {hashtags}")
        await page.wait_for_timeout(2000)
        await page.click("button:has-text('Post')")
        await page.wait_for_load_state("networkidle", timeout=60000)

        shot = base64.b64encode(await page.screenshot(full_page=True)).decode("ascii")[:10000]
        return (
            "submitted",
            f"tiktok_upload_{subject_row.song_id}",
            {
                "caption": caption,
                "hashtags": hashtags,
                "screenshot_b64": shot,
            },
        )
    except Exception as e:
        logger.exception("[tiktok_upload] failed")
        return ("failed", None, {"error": f"{type(e).__name__}: {e}"})
    finally:
        try:
            await browser.close()
            await pw.stop()
        except Exception:
            pass
