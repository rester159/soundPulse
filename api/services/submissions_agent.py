"""
Submissions Agent (§43.N, Agent N).

Responsibilities per user spec:
  1. Submits to PROs via browser automation (Fonzworth pattern) unless
     the PRO exposes a real API wrapper.
  2. Submits to streaming services via distributor connectors (LabelGrid,
     Revelator, SonoSuite).
  3. Reminds CEO to create profiles / provision accounts when a required
     prerequisite is missing. Blockers trigger a CEO decision via §23.

For every song in status='assigned_to_release' this agent:
  - Identifies the required submission lanes for its release
  - Checks each lane's prerequisites (env vars, social accounts, PRO
    memberships, etc.)
  - For each missing prereq: creates a ceo_decisions row with
    decision_type='setup_required' so the CEO queue shows it
  - For each satisfied prereq: attempts the actual submission
    (currently stubbed — real submission logic lands in T-182 LabelGrid
    and T-190 Fonzworth ASCAP)
  - Tracks per-song submission progress in the existing
    song_submissions + royalty_registrations tables

Escalated CEO decisions are idempotent — running the agent twice for
the same artist + lane + missing prereq won't create duplicates.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text as _text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lane configuration — what each submission lane needs before it can run
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LaneRequirement:
    code: str
    description: str
    resolution_hint: str
    # If the missing item is an env var, list it here so the UI can show
    # exactly what the CEO needs to set.
    env_var: str | None = None
    # If the missing item is a social_accounts row, list the platform.
    social_platform: str | None = None


@dataclass(frozen=True)
class SubmissionLane:
    id: str
    display_name: str
    category: str                 # distribution | pro | mechanical | neighboring | ugc_cid | social
    prerequisites: tuple[LaneRequirement, ...]
    # How the agent would actually submit when prerequisites are met.
    # Either 'api' (has a wrapper) or 'browser' (needs Fonzworth-pattern
    # automation) or 'distributor' (routes through distributor connector).
    submission_mode: str
    # Task ID that will implement real submission logic
    implementation_task: str
    # Whether this lane is mandatory for every release or optional
    mandatory: bool = True


LANES: tuple[SubmissionLane, ...] = (
    SubmissionLane(
        id="distribution_labelgrid",
        display_name="LabelGrid distribution",
        category="distribution",
        prerequisites=(
            LaneRequirement(
                code="labelgrid_account",
                description="LabelGrid account with API access enabled",
                resolution_hint="Sign up at labelgrid.com, request API access, generate a key",
                env_var="LABELGRID_API_KEY",
            ),
            LaneRequirement(
                code="labelgrid_label_registered",
                description="SoundPulse Records LLC registered as a label in LabelGrid",
                resolution_hint="Upload W-9 + IPI + bank details in LabelGrid admin",
                env_var="LABELGRID_LABEL_ID",
            ),
        ),
        submission_mode="distributor",
        implementation_task="T-182",
        mandatory=True,
    ),
    SubmissionLane(
        id="pro_ascap",
        display_name="ASCAP performance rights",
        category="pro",
        prerequisites=(
            LaneRequirement(
                code="ascap_publisher",
                description="SoundPulse Records LLC registered as ASCAP publisher",
                resolution_hint="Register at ascap.com/publishers ($50 one-time + IPI application)",
                env_var="ASCAP_PUBLISHER_ID",
            ),
            LaneRequirement(
                code="fonzworth_service",
                description="Fonzworth browser-automation service URL + API key",
                resolution_hint="Deploy fonzworth (separate repo) and set the URL + key",
                env_var="FONZWORTH_BASE_URL",
            ),
            LaneRequirement(
                code="fonzworth_key",
                description="Fonzworth API key",
                resolution_hint="Set after deploying fonzworth",
                env_var="FONZWORTH_API_KEY",
            ),
        ),
        submission_mode="browser",
        implementation_task="T-190",
        mandatory=True,
    ),
    SubmissionLane(
        id="pro_bmi",
        display_name="BMI performance rights",
        category="pro",
        prerequisites=(
            LaneRequirement(
                code="bmi_publisher",
                description="SoundPulse Records LLC registered as BMI publisher",
                resolution_hint="Register at bmi.com/publishers",
                env_var="BMI_PUBLISHER_ID",
            ),
        ),
        submission_mode="browser",
        implementation_task="T-200",
        mandatory=False,  # optional — ASCAP first, BMI as backup
    ),
    SubmissionLane(
        id="mlc_mechanical",
        display_name="MLC mechanical rights",
        category="mechanical",
        prerequisites=(
            LaneRequirement(
                code="mlc_membership",
                description="MLC publisher membership",
                resolution_hint="Apply at themlc.com/members — free for publishers",
                env_var="MLC_MEMBER_ID",
            ),
        ),
        submission_mode="api",
        implementation_task="T-201",
        mandatory=True,
    ),
    SubmissionLane(
        id="soundex_neighboring",
        display_name="SoundExchange neighboring rights",
        category="neighboring",
        prerequisites=(
            LaneRequirement(
                code="soundex_account",
                description="SoundExchange account with label registration",
                resolution_hint="Register at soundexchange.com (free)",
                env_var="SOUNDEX_ACCOUNT_ID",
            ),
        ),
        submission_mode="browser",
        implementation_task="T-202",
        mandatory=True,
    ),
    SubmissionLane(
        id="youtube_content_id",
        display_name="YouTube Content ID",
        category="ugc_cid",
        prerequisites=(
            LaneRequirement(
                code="youtube_cms_partnership",
                description="YouTube CMS partnership — partner-gated, not a free signup",
                resolution_hint="Apply at youtube.com/ads/content_id — likely rejected for indie labels",
                env_var="YOUTUBE_CMS_PARTNER_ID",
            ),
        ),
        submission_mode="api",
        implementation_task="T-205",
        mandatory=False,  # explicitly optional — most indie labels can't get partnership
    ),
    SubmissionLane(
        id="social_tiktok",
        display_name="TikTok posting",
        category="social",
        prerequisites=(
            LaneRequirement(
                code="tiktok_account",
                description="TikTok account for the artist",
                resolution_hint="CEO creates a TikTok account under the artist stage name",
                social_platform="tiktok",
            ),
            LaneRequirement(
                code="tiktok_api_audit",
                description="TikTok Content Posting API audit approval",
                resolution_hint="Apply via TikTok developer portal — ~2-4 weeks review",
                env_var="TIKTOK_CLIENT_KEY",
            ),
        ),
        submission_mode="api",
        implementation_task="T-240",
        mandatory=False,
    ),
    SubmissionLane(
        id="social_instagram",
        display_name="Instagram posting",
        category="social",
        prerequisites=(
            LaneRequirement(
                code="instagram_account",
                description="Instagram business account for the artist",
                resolution_hint="CEO creates an IG business account + converts to professional",
                social_platform="instagram",
            ),
            LaneRequirement(
                code="instagram_graph_scope",
                description="instagram_content_publish scope approved on the Meta app",
                resolution_hint="Submit app for review in Meta developer portal",
                env_var="INSTAGRAM_GRAPH_TOKEN",
            ),
        ),
        submission_mode="api",
        implementation_task="T-241",
        mandatory=False,
    ),
    SubmissionLane(
        id="social_youtube",
        display_name="YouTube upload",
        category="social",
        prerequisites=(
            LaneRequirement(
                code="youtube_channel",
                description="YouTube channel for the artist",
                resolution_hint="CEO creates a YouTube channel under the artist stage name",
                social_platform="youtube",
            ),
            LaneRequirement(
                code="youtube_oauth",
                description="YouTube Data API v3 OAuth credentials",
                resolution_hint="Set up OAuth client in Google Cloud Console",
                env_var="YOUTUBE_OAUTH_TOKEN",
            ),
        ),
        submission_mode="api",
        implementation_task="T-242",
        mandatory=False,
    ),
)


# ---------------------------------------------------------------------------
# Prerequisite checking
# ---------------------------------------------------------------------------

async def _has_social_account(db: AsyncSession, artist_id, platform: str) -> bool:
    r = await db.execute(
        _text("""
            SELECT 1 FROM social_accounts
            WHERE artist_id = :aid AND platform = :plat AND status = 'active'
            LIMIT 1
        """),
        {"aid": artist_id, "plat": platform},
    )
    return r.scalar() is not None


async def check_prerequisites_for_artist(
    db: AsyncSession, artist_id, *, include_optional: bool = False
) -> list[dict[str, Any]]:
    """
    Walk every lane and return a list of missing-prereq reports.

    Each entry is shaped:
      {
        "lane_id": "pro_ascap",
        "lane_display_name": "ASCAP performance rights",
        "category": "pro",
        "mandatory": True,
        "missing": [
          {"code": "ascap_publisher", "description": "...",
           "resolution_hint": "...", "env_var": "ASCAP_PUBLISHER_ID",
           "social_platform": null},
          ...
        ],
      }
    Lanes with zero missing items are omitted.
    """
    reports: list[dict[str, Any]] = []
    for lane in LANES:
        if not lane.mandatory and not include_optional:
            continue
        missing: list[dict[str, Any]] = []
        for req in lane.prerequisites:
            satisfied = False
            if req.env_var:
                satisfied = bool(os.environ.get(req.env_var, "").strip())
            elif req.social_platform:
                satisfied = await _has_social_account(db, artist_id, req.social_platform)
            if not satisfied:
                missing.append({
                    "code": req.code,
                    "description": req.description,
                    "resolution_hint": req.resolution_hint,
                    "env_var": req.env_var,
                    "social_platform": req.social_platform,
                })
        if missing:
            reports.append({
                "lane_id": lane.id,
                "lane_display_name": lane.display_name,
                "category": lane.category,
                "mandatory": lane.mandatory,
                "submission_mode": lane.submission_mode,
                "implementation_task": lane.implementation_task,
                "missing": missing,
            })
    return reports


# ---------------------------------------------------------------------------
# CEO escalation
# ---------------------------------------------------------------------------

async def _existing_setup_decision_for(
    db: AsyncSession, artist_id, lane_id: str
) -> str | None:
    """Return the decision_id if a pending setup_required decision
    already exists for this (artist, lane). Avoids duplicates."""
    r = await db.execute(
        _text("""
            SELECT decision_id FROM ceo_decisions
            WHERE decision_type = 'setup_required'
              AND status = 'pending'
              AND entity_type = 'ai_artist'
              AND entity_id = :aid
              AND data->>'lane_id' = :lane
            LIMIT 1
        """),
        {"aid": artist_id, "lane": lane_id},
    )
    row = r.fetchone()
    return str(row[0]) if row else None


async def escalate_missing_prereqs_to_ceo(
    db: AsyncSession,
    *,
    artist_id,
    artist_name: str,
    reports: list[dict[str, Any]],
    song_id=None,
) -> list[str]:
    """
    For every lane in `reports` that doesn't already have a pending
    setup_required decision, create one. Returns the list of new
    decision_ids (already-existing ones are not counted).
    """
    created: list[str] = []
    for report in reports:
        lane_id = report["lane_id"]
        existing = await _existing_setup_decision_for(db, artist_id, lane_id)
        if existing:
            continue

        data = {
            "lane_id": lane_id,
            "lane_display_name": report["lane_display_name"],
            "category": report["category"],
            "mandatory": report["mandatory"],
            "submission_mode": report["submission_mode"],
            "implementation_task": report["implementation_task"],
            "missing": report["missing"],
            "artist_id": str(artist_id),
            "artist_name": artist_name,
            "blocking_song_id": str(song_id) if song_id else None,
            "summary": f"{report['lane_display_name']} blocked — "
                       f"{len(report['missing'])} item(s) need CEO setup",
        }
        r = await db.execute(
            _text("""
                INSERT INTO ceo_decisions
                  (decision_type, entity_type, entity_id, proposal, data, status)
                VALUES
                  ('setup_required', 'ai_artist', :aid, 'provision', CAST(:data AS jsonb), 'pending')
                RETURNING decision_id
            """),
            {"aid": artist_id, "data": json.dumps(data)},
        )
        created.append(str(r.scalar()))

    if created:
        await db.commit()

        # T-150 auto-notify: dispatch each newly-created decision to the
        # CEO's configured channel (Telegram if preferred_channel='telegram')
        try:
            from api.models.ceo_profile import CeoProfile
            from sqlalchemy import select as _select
            from api.services.telegram_bot import send_ceo_decision

            profile_row = (await db.execute(_select(CeoProfile).limit(1))).scalar_one_or_none()
            if profile_row:
                # Pull the decisions we just created by id to get full shape
                for decision_id in created:
                    r = await db.execute(
                        _text("SELECT decision_id, decision_type, proposal, data, created_at "
                              "FROM ceo_decisions WHERE decision_id = :did"),
                        {"did": decision_id},
                    )
                    row = r.fetchone()
                    if row is None:
                        continue
                    decision_dict = {
                        "decision_id": str(row[0]),
                        "decision_type": row[1],
                        "proposal": row[2],
                        "data": row[3],
                        "created_at": row[4].isoformat() if row[4] else None,
                    }
                    await send_ceo_decision(decision_dict, profile_row)
        except Exception:
            logger.exception("[submissions-agent] CEO notify batch failed (non-fatal)")

    return created


# ---------------------------------------------------------------------------
# The sweep — called by scheduler + on-demand endpoint
# ---------------------------------------------------------------------------

async def sweep_submissions(db: AsyncSession, *, include_optional: bool = False) -> dict[str, Any]:
    """
    Scan every song in status='assigned_to_release' and either:
      - Submit it via the appropriate lane (currently stubbed), OR
      - Escalate missing prereqs to the CEO via setup_required decisions

    Idempotent — running twice won't create duplicate escalations, and
    stubbed submission attempts are no-ops once a song has already been
    marked submitted.
    """
    stats = {
        "songs_scanned": 0,
        "lanes_checked": 0,
        "prereq_gaps": 0,
        "ceo_decisions_created": 0,
        "submissions_stubbed": 0,
        "elapsed_ms": 0,
    }
    started = datetime.now(timezone.utc)

    # Per-artist prereq cache so we don't re-check the same artist N times
    artist_reports_cache: dict = {}

    songs = await db.execute(
        _text("""
            SELECT s.song_id, s.title, s.primary_artist_id, a.stage_name
            FROM songs_master s
            LEFT JOIN ai_artists a ON a.artist_id = s.primary_artist_id
            WHERE s.status = 'assigned_to_release'
            LIMIT 500
        """)
    )
    for song_id, title, artist_id, stage_name in songs.fetchall():
        stats["songs_scanned"] += 1

        if artist_id not in artist_reports_cache:
            reports = await check_prerequisites_for_artist(
                db, artist_id, include_optional=include_optional
            )
            artist_reports_cache[artist_id] = reports
        else:
            reports = artist_reports_cache[artist_id]

        stats["lanes_checked"] += len(LANES)
        stats["prereq_gaps"] += len(reports)

        if reports:
            created = await escalate_missing_prereqs_to_ceo(
                db,
                artist_id=artist_id,
                artist_name=stage_name or "unknown",
                reports=reports,
                song_id=song_id,
            )
            stats["ceo_decisions_created"] += len(created)
            # Don't try to submit a song whose prereqs are missing
            continue

        # Prereqs satisfied — attempt submission. Real logic lives in
        # the lane-specific modules, which aren't built yet.
        for lane in LANES:
            if not lane.mandatory and not include_optional:
                continue
            # All stubs right now — log and skip until implementation_task ships
            logger.info(
                "[submissions-agent] SKIP %s for song %s — "
                "submission path %s not yet implemented (%s)",
                lane.id, title, lane.submission_mode, lane.implementation_task,
            )
            stats["submissions_stubbed"] += 1

    stats["elapsed_ms"] = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
    logger.info("[submissions-agent] sweep %s", stats)
    return stats


# ---------------------------------------------------------------------
# DOWNSTREAM PIPELINE SWEEP (PRD §28-29) — added after T-190..T-229 ship
#
# sweep_all_ready_songs() walks qa_passed songs that have metadata
# projected and dispatches them through the downstream pipeline via the
# generic external_submission_agent + the ASCAP Fonzworth agent. Uses
# the SUBMISSION_DEPS graph so playlist pitches wait for distributors,
# SoundExchange waits for distribution, etc.
# ---------------------------------------------------------------------

SUBMISSION_DEPS: dict[str, list[str]] = {
    # Distributors: no deps — audio goes live first
    "distrokid": [], "tunecore": [], "cd-baby": [],
    "amuse": [], "unitedmasters": [],
    # PRO writer side + MLC publisher side: parallel to distributors
    "bmi": [], "mlc": [],
    # SoundExchange + Content ID need distributor live
    "soundexchange": ["distrokid"],
    "youtube_content_id": ["distrokid"],
    # Playlist pitches need distributor live
    "spotify_editorial": ["distrokid"],
    "apple_music_for_artists": ["distrokid"],
    "groover": ["distrokid"],
    "playlistpush": ["distrokid"],
    # Sync marketplaces: independent
    "musicbed": [], "marmoset": [], "artlist": [], "submithub": [],
    # Marketing: runs after distribution
    "press_release_agent": ["distrokid"],
    "social_media_agent": ["distrokid"],
    "tiktok_upload": ["distrokid"],
}

_PIPELINE_TARGET_ORDER = [
    "distrokid", "tunecore", "cd-baby", "amuse", "unitedmasters",
    "bmi", "mlc",
    "soundexchange", "youtube_content_id",
    "musicbed", "marmoset", "artlist", "submithub",
    "spotify_editorial", "apple_music_for_artists",
    "groover", "playlistpush",
    "press_release_agent", "social_media_agent", "tiktok_upload",
]


async def _downstream_deps_satisfied(
    db: AsyncSession, target_service: str, subject_id
) -> tuple[bool, str]:
    """Check prereq external_submissions rows."""
    from sqlalchemy import select as _select
    from api.models.external_submission import ExternalSubmission
    deps = SUBMISSION_DEPS.get(target_service, [])
    if not deps:
        return True, ""
    for dep in deps:
        row = (
            await db.execute(
                _select(ExternalSubmission)
                .where(
                    ExternalSubmission.target_service == dep,
                    ExternalSubmission.subject_id == subject_id,
                )
                .order_by(ExternalSubmission.created_at.desc())
                .limit(1)
            )
        ).scalars().first()
        if row is None or row.status not in ("submitted", "accepted"):
            return False, f"waiting on {dep}"
    return True, ""


async def _target_is_enabled(db: AsyncSession, target_service: str) -> bool:
    from sqlalchemy import select as _select
    from api.models.external_submission import SubmissionTarget
    t = (
        await db.execute(
            _select(SubmissionTarget).where(SubmissionTarget.target_service == target_service)
        )
    ).scalar_one_or_none()
    return bool(t and t.is_enabled)


async def sweep_downstream_pipeline(
    db: AsyncSession,
    limit: int = 20,
) -> dict[str, Any]:
    """
    Walk every qa_passed song that has metadata projected (ISRC set)
    and dispatch it through the downstream pipeline. Respects
    dependency graph + enabled/disabled flags on submission_targets.

    Returns a per-song report of what was attempted and what was
    deferred. Non-destructive — idempotent submit_subject calls reuse
    existing rows for already-submitted targets.
    """
    from sqlalchemy import select as _select
    from api.models.ai_artist import AIArtist
    from api.models.ascap_submission import AscapSubmission
    from api.models.songs_master import SongMaster
    from api.services.ascap_fonzworth import submit_song_to_ascap
    from api.services.external_submission_agent import submit_subject

    stmt = (
        _select(SongMaster)
        .where(
            SongMaster.status == "qa_passed",
            SongMaster.isrc.isnot(None),
        )
        .limit(limit)
    )
    songs = (await db.execute(stmt)).scalars().all()

    results: list[dict[str, Any]] = []
    for song in songs:
        steps: dict[str, str] = {}
        errors: list[str] = []

        # ASCAP first (own agent, own table)
        existing_ascap = (
            await db.execute(
                _select(AscapSubmission)
                .where(AscapSubmission.song_id == song.song_id)
                .order_by(AscapSubmission.created_at.desc())
                .limit(1)
            )
        ).scalars().first()
        if existing_ascap and existing_ascap.status in ("submitted", "accepted"):
            steps["ascap"] = "already_done"
        else:
            artist = (
                await db.execute(
                    _select(AIArtist).where(AIArtist.artist_id == song.primary_artist_id)
                )
            ).scalar_one_or_none()
            if artist:
                try:
                    asub = await submit_song_to_ascap(db, song=song, artist=artist)
                    steps["ascap"] = asub.status
                except Exception as e:
                    steps["ascap"] = "failed"
                    errors.append(f"ascap: {type(e).__name__}: {e}")

        # External targets in pipeline order
        for svc in _PIPELINE_TARGET_ORDER:
            try:
                if not await _target_is_enabled(db, svc):
                    steps[svc] = "disabled"
                    continue
                ok, reason = await _downstream_deps_satisfied(db, svc, song.song_id)
                if not ok:
                    steps[svc] = f"deferred: {reason}"
                    continue
                sub = await submit_subject(
                    db,
                    target_service=svc,
                    submission_subject_type="song",
                    subject_id=song.song_id,
                )
                steps[svc] = sub.status
            except Exception as e:
                steps[svc] = "failed"
                errors.append(f"{svc}: {type(e).__name__}: {e}")

        results.append({
            "song_id": str(song.song_id),
            "title": song.title,
            "steps": steps,
            "errors": errors,
        })

    return {
        "scanned": len(songs),
        "results": results,
    }
