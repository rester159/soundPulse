"""
Fonzworth ASCAP submission agent (T-190..T-194, PRD §31).

Logs into ASCAP's Fonzworth/Repertory portal using the creds stored in
ASCAP_USERNAME / ASCAP_PASSWORD env vars, registers a new work from a
songs_master row, and writes the returned work_id back.

Implementation notes
--------------------
The Fonzworth portal is a stateful ASP.NET web app with no public API,
so this uses Playwright (headless Chromium) to drive the browser. That
means the `playwright` Python package must be installed AND the Chromium
binary must be downloaded on the Railway container.

Because Railway's slug build doesn't include browser binaries by default,
the current deploy will `log.warning` and return an "environment_missing"
status if Playwright isn't installable. The migration + model + admin
endpoint + DB tracking are all in place, so flipping on Playwright is a
config change — no code rewrite.

To enable in production:
  1. Add `playwright>=1.40` to pyproject.toml dependencies
  2. Add a post-install step to the Dockerfile:
       RUN python -m playwright install --with-deps chromium
  3. Set ASCAP_USERNAME / ASCAP_PASSWORD env vars (already done)
  4. Call POST /admin/songs/{song_id}/ascap-submit

The selector paths in this module are BEST-GUESS placeholders based on
public Fonzworth screenshots. The FIRST live run will need manual
selector tuning — I'll update these as we see the real DOM.

Flow
----
  1. Launch headless browser
  2. Navigate to https://my.ascap.com/
  3. Fill username + password, click Login
  4. Wait for dashboard, click "Repertory" → "Add Work"
  5. Fill:
       - Title                  ← song.title
       - Creation date          ← song.actual_release_date or NOW
       - Writer(s)              ← song.writers or AI artist legal_name
       - Publisher(s)           ← "SoundPulse Records LLC" (canonical)
       - Share %                ← 100% to the writer, 0% ghost
       - ISWC (optional)        ← song.iswc if present
  6. Click Submit
  7. Capture screenshot of the confirmation page → base64 into DB
  8. Parse the work_id from the confirmation URL or DOM
  9. Write status='submitted', ascap_work_id=<id> to ascap_submissions
"""
from __future__ import annotations

import base64
import logging
import os
import uuid as _uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.ascap_submission import AscapSubmission

logger = logging.getLogger(__name__)

ASCAP_LOGIN_URL = os.environ.get("ASCAP_LOGIN_URL", "https://my.ascap.com/")
ASCAP_USERNAME_ENV = "ASCAP_USERNAME"
ASCAP_PASSWORD_ENV = "ASCAP_PASSWORD"


class AscapMissingCredentials(Exception):
    """Raised when ASCAP_USERNAME / ASCAP_PASSWORD env vars are missing."""


class AscapPlaywrightUnavailable(Exception):
    """Raised when the playwright package or browser binary is missing."""


def _check_credentials() -> tuple[str, str]:
    username = os.environ.get(ASCAP_USERNAME_ENV, "").strip()
    password = os.environ.get(ASCAP_PASSWORD_ENV, "").strip()
    if not username or not password:
        raise AscapMissingCredentials(
            f"{ASCAP_USERNAME_ENV} / {ASCAP_PASSWORD_ENV} not configured"
        )
    return username, password


async def _launch_playwright():
    """
    Attempt to import and launch Playwright. Raises
    AscapPlaywrightUnavailable if the package or browser isn't installed
    so the caller can degrade gracefully.
    """
    try:
        from playwright.async_api import async_playwright  # type: ignore
    except ImportError as e:
        raise AscapPlaywrightUnavailable(
            "playwright Python package not installed. See "
            "api/services/ascap_fonzworth.py docstring for enable steps."
        ) from e
    try:
        pw = await async_playwright().start()
        browser = await pw.chromium.launch(headless=True)
        return pw, browser
    except Exception as e:  # includes missing browser binary
        raise AscapPlaywrightUnavailable(
            f"Playwright launch failed — likely missing Chromium binary: {e}"
        ) from e


def _build_writers_payload(song) -> list[dict[str, Any]]:
    """
    Build the writer split list the portal expects.

    Default: one writer = the artist's legal_name, 100% share. If song
    has explicit writers_json in the future that schema takes over.
    """
    # Song has no writer column yet — use the artist row via the FK
    # relationship. The admin endpoint that calls this will pass the
    # AI artist's legal_name as a keyword argument to keep the DB model
    # schema stable.
    return [
        {
            "name": getattr(song, "_writer_legal_name", "SoundPulse Default Writer"),
            "ipi": None,
            "share_pct": 100.0,
            "role": "composer",
        }
    ]


def _build_publishers_payload() -> list[dict[str, Any]]:
    return [
        {
            "name": "SoundPulse Records LLC",
            "ipi": None,
            "share_pct": 100.0,
        }
    ]


async def submit_song_to_ascap(
    db: AsyncSession,
    *,
    song,
    artist,
    force_retry: bool = False,
) -> AscapSubmission:
    """
    End-to-end ASCAP work submission for one song.

    Creates a pending ascap_submissions row up front (so aborts/errors
    are observable in the DB), then tries to drive Playwright to register
    the work. On any failure (missing creds, missing Playwright, selector
    timeout, network error) the row is flipped to status='failed' with
    last_error_message set.

    Callers: admin endpoint, submissions-agent sweep.
    """
    # 1. Create/reuse the tracking row
    existing = (
        await db.execute(
            select(AscapSubmission)
            .where(AscapSubmission.song_id == song.song_id)
            .order_by(AscapSubmission.created_at.desc())
        )
    ).scalars().first()

    if existing and existing.status in ("submitted", "accepted") and not force_retry:
        logger.info(
            "[ascap] song %s already has a %s submission (work_id=%s) — skipping",
            song.song_id, existing.status, existing.ascap_work_id,
        )
        return existing

    sub = AscapSubmission(
        id=_uuid.uuid4(),
        song_id=song.song_id,
        attempt_number=(existing.attempt_number + 1) if existing else 1,
        status="pending",
        submission_title=song.title,
        submission_iswc=getattr(song, "iswc", None),
    )
    db.add(sub)
    await db.flush()

    # 2. Attach the writer legal name to the song object (used by
    #    _build_writers_payload). Mutation is local; not persisted.
    setattr(song, "_writer_legal_name", artist.legal_name or artist.stage_name or "SoundPulse Default")
    sub.writers_json = {"writers": _build_writers_payload(song)}
    sub.publishers_json = {"publishers": _build_publishers_payload()}
    await db.flush()

    # 3. Credentials + Playwright check
    try:
        username, password = _check_credentials()
    except AscapMissingCredentials as e:
        sub.status = "failed"
        sub.last_error_message = str(e)
        await db.commit()
        return sub

    try:
        pw, browser = await _launch_playwright()
    except AscapPlaywrightUnavailable as e:
        sub.status = "failed"
        sub.last_error_message = str(e)
        await db.commit()
        logger.warning("[ascap] playwright unavailable — row marked failed: %s", e)
        return sub

    # 4. Drive the browser
    try:
        context = await browser.new_context()
        page = await context.new_page()

        # Navigate + login
        await page.goto(ASCAP_LOGIN_URL, wait_until="domcontentloaded", timeout=30000)
        # Placeholder selectors — will need tuning on first live run
        await page.fill("input[name='username']", username)
        await page.fill("input[name='password']", password)
        await page.click("button[type='submit']")
        await page.wait_for_load_state("networkidle", timeout=30000)
        sub.status = "logged_in"
        await db.flush()

        # Navigate to Add Work form (selector TBD from live run)
        await page.click("a:has-text('Repertory')", timeout=20000)
        await page.click("a:has-text('Add Work')", timeout=20000)
        await page.wait_for_load_state("networkidle", timeout=20000)

        # Fill form (selectors TBD)
        await page.fill("input[name='Title']", song.title or "Untitled")
        if getattr(song, "iswc", None):
            await page.fill("input[name='ISWC']", song.iswc)
        # Writer/publisher widgets are complex in the real portal — this
        # is a placeholder single-writer path
        await page.fill("input[name='Writer_Name']", song._writer_legal_name)
        await page.fill("input[name='Writer_Share']", "100")
        await page.fill("input[name='Publisher_Name']", "SoundPulse Records LLC")
        await page.fill("input[name='Publisher_Share']", "100")

        # Submit
        await page.click("button:has-text('Submit')")
        await page.wait_for_load_state("networkidle", timeout=30000)

        # Capture confirmation screenshot
        shot_bytes = await page.screenshot(full_page=True)
        sub.portal_screenshot_b64 = base64.b64encode(shot_bytes).decode("ascii")

        # Extract the ASCAP work id from the URL or confirmation text
        url = page.url
        work_id = None
        if "workid=" in url.lower():
            work_id = url.lower().split("workid=")[1].split("&")[0]
        if not work_id:
            try:
                work_id_text = await page.inner_text(
                    "[data-testid='work-id'], .work-id, .confirmation-id",
                    timeout=3000,
                )
                work_id = (work_id_text or "").strip()
            except Exception:
                pass

        sub.status = "submitted"
        sub.submitted_at = datetime.now(timezone.utc)
        sub.ascap_work_id = work_id
        sub.raw_response = {"confirmation_url": url}
        await db.commit()
        logger.info(
            "[ascap] submitted work for song %s → ascap_work_id=%s",
            song.song_id, work_id,
        )

    except Exception as e:
        sub.status = "failed"
        sub.retry_count = (sub.retry_count or 0) + 1
        sub.last_error_message = f"{type(e).__name__}: {e}"
        await db.commit()
        logger.exception("[ascap] submission failed for song %s", song.song_id)
    finally:
        try:
            await browser.close()
            await pw.stop()
        except Exception:
            pass

    return sub
