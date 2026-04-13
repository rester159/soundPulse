"""
Playwright-based distributor adapters — TuneCore, CD Baby, Amuse, UnitedMasters.

All four share the same Playwright pattern: sign in, navigate to upload,
fill metadata, upload audio, submit. Per-portal selectors differ; this
module defines a base class + four thin subclasses so adding the real
selector tuning is a one-class-per-service diff.

Each is registered as its own adapter with the shared dispatcher. The
base class degrades cleanly if Playwright isn't installed — returns
'failed' with a clean error message so the sweep logs it without crashing.
"""
from __future__ import annotations

import base64
import logging
import os
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.services.external_submission_agent import register_adapter

logger = logging.getLogger(__name__)


@dataclass
class PortalConfig:
    target_service: str
    signin_url: str
    upload_url: str
    username_env: str
    password_env: str
    # Selector vocabulary — override per portal after manual inspection
    username_selector: str = "input[name='username']"
    password_selector: str = "input[name='password']"
    signin_button: str = "button[type='submit']"
    title_selector: str = "input[name='title']"
    artist_selector: str = "input[name='artist_name']"
    file_selector: str = "input[type='file']"
    genre_selector: str = "select[name='genre']"
    submit_button: str = "button:has-text('Submit')"
    external_id_selectors: tuple[str, ...] = (
        "[data-upc]", ".upc", ".release-id", "[data-release-id]",
    )


PORTALS: dict[str, PortalConfig] = {
    "tunecore": PortalConfig(
        target_service="tunecore",
        signin_url="https://www.tunecore.com/signin",
        upload_url="https://www.tunecore.com/upload/new",
        username_env="TUNECORE_USERNAME",
        password_env="TUNECORE_PASSWORD",
    ),
    "cd-baby": PortalConfig(
        target_service="cd-baby",
        signin_url="https://members.cdbaby.com/login.aspx",
        upload_url="https://members.cdbaby.com/upload",
        username_env="CDBABY_USERNAME",
        password_env="CDBABY_PASSWORD",
    ),
    "amuse": PortalConfig(
        target_service="amuse",
        signin_url="https://amuse.io/login",
        upload_url="https://amuse.io/app/release/new",
        username_env="AMUSE_USERNAME",
        password_env="AMUSE_PASSWORD",
    ),
    "unitedmasters": PortalConfig(
        target_service="unitedmasters",
        signin_url="https://app.unitedmasters.com/login",
        upload_url="https://app.unitedmasters.com/upload",
        username_env="UNITEDMASTERS_USERNAME",
        password_env="UNITEDMASTERS_PASSWORD",
    ),
}


async def _load_audio_bytes(db: AsyncSession, song) -> bytes | None:
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
    return bytes(row[0]) if row else None


async def _run_portal_flow(db, subject_row, cfg: PortalConfig) -> tuple[str, str | None, dict]:
    """Shared Playwright flow for all four distributors."""
    try:
        from playwright.async_api import async_playwright  # type: ignore
    except ImportError:
        return ("failed", None, {"error": "playwright not installed", "target": cfg.target_service})

    username = os.environ.get(cfg.username_env, "").strip()
    password = os.environ.get(cfg.password_env, "").strip()
    if not username or not password:
        return ("failed", None, {"error": f"{cfg.username_env}/{cfg.password_env} not set"})

    audio_bytes = await _load_audio_bytes(db, subject_row)
    if not audio_bytes:
        return ("failed", None, {"error": "no audio bytes for song"})

    from api.models.ai_artist import AIArtist
    artist = (
        await db.execute(
            select(AIArtist).where(AIArtist.artist_id == subject_row.primary_artist_id)
        )
    ).scalar_one_or_none()
    if artist is None:
        return ("failed", None, {"error": "primary artist missing"})

    try:
        pw = await async_playwright().start()
        browser = await pw.chromium.launch(headless=True)
    except Exception as e:
        return ("failed", None, {"error": f"playwright launch failed: {e}"})

    try:
        context = await browser.new_context()
        page = await context.new_page()

        await page.goto(cfg.signin_url, wait_until="domcontentloaded", timeout=30000)
        await page.fill(cfg.username_selector, username)
        await page.fill(cfg.password_selector, password)
        await page.click(cfg.signin_button)
        await page.wait_for_load_state("networkidle", timeout=30000)

        await page.goto(cfg.upload_url, wait_until="domcontentloaded", timeout=30000)
        await page.fill(cfg.title_selector, subject_row.title or "Untitled")
        await page.fill(cfg.artist_selector, artist.stage_name)

        async with page.expect_file_chooser() as fc_info:
            await page.click(cfg.file_selector)
        fc = await fc_info.value
        await fc.set_files([{
            "name": f"{(subject_row.title or 'untitled').replace(' ', '_')}.mp3",
            "mimeType": "audio/mpeg",
            "buffer": audio_bytes,
        }])

        if subject_row.primary_genre:
            try:
                await page.select_option(cfg.genre_selector, subject_row.primary_genre.split(".")[0])
            except Exception:
                pass

        await page.click(cfg.submit_button)
        await page.wait_for_load_state("networkidle", timeout=60000)

        external_id = None
        for sel in cfg.external_id_selectors:
            try:
                txt = await page.inner_text(sel, timeout=2000)
                if txt and txt.strip():
                    external_id = txt.strip()
                    break
            except Exception:
                continue

        shot = base64.b64encode(await page.screenshot(full_page=True)).decode("ascii")[:10000]
        return (
            "submitted",
            external_id,
            {
                "target": cfg.target_service,
                "confirmation_url": page.url,
                "screenshot_b64": shot,
            },
        )
    except Exception as e:
        logger.exception("[%s] portal flow raised", cfg.target_service)
        return ("failed", None, {"error": f"{type(e).__name__}: {e}"})
    finally:
        try:
            await browser.close()
            await pw.stop()
        except Exception:
            pass


# Register one adapter per portal
@register_adapter("tunecore")
async def _tunecore(db, subject_row, target):
    return await _run_portal_flow(db, subject_row, PORTALS["tunecore"])


@register_adapter("cd-baby")
async def _cdbaby(db, subject_row, target):
    return await _run_portal_flow(db, subject_row, PORTALS["cd-baby"])


@register_adapter("amuse")
async def _amuse(db, subject_row, target):
    return await _run_portal_flow(db, subject_row, PORTALS["amuse"])


@register_adapter("unitedmasters")
async def _unitedmasters(db, subject_row, target):
    return await _run_portal_flow(db, subject_row, PORTALS["unitedmasters"])
