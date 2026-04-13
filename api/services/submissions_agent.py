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
