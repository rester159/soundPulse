"""
T-195 — End-to-end integration test for the full §15 13-step pipeline.

Exercises the entire critical path by hitting the live backend (Railway)
in sequence, so every endpoint + side effect gets validated against a
real Postgres and a real provider. Failures catch regressions in any
layer between breakout detection and release-track binding.

Steps proven:
  1. Assignment engine produces a scoring breakdown
  2. CEO gate decision row lands in ceo_decisions
  3. CEO approve endpoint flips blueprint to assigned + sets artist FK
  4. Generation orchestrator creates songs_master draft + submits to provider
  5. Provider poll transitions song draft → qa_pending + creates audio_assets
  6. Audio bytes are self-hosted (reachable without provider delivery URL)
  7. Audio QA lite sweep flips qa_pending → qa_passed
  8. Release creation + track binding transitions song to assigned_to_release

Uses only endpoints, no ORM. This is a smoke test, not a unit test.
Run against the live backend:
  pytest tests/test_api/test_e2e_pipeline.py -v

Or skip in CI if SOUNDPULSE_E2E_BASE_URL is not set.
"""
from __future__ import annotations

import os
import time
import uuid
from typing import Any

import httpx
import pytest

BASE_URL = os.environ.get(
    "SOUNDPULSE_E2E_BASE_URL",
    "https://soundpulse-production-5266.up.railway.app",
)
ADMIN_KEY = os.environ.get(
    "SOUNDPULSE_E2E_ADMIN_KEY",
    "sp_admin_0000000000000000000000000000dead",
)

# Skip everything if the base URL isn't configured — keeps CI happy when
# running offline unit tests.
pytestmark = pytest.mark.skipif(
    not BASE_URL.startswith("http"),
    reason="Set SOUNDPULSE_E2E_BASE_URL to run the E2E pipeline suite",
)


# --- Helpers ---------------------------------------------------------------

@pytest.fixture(scope="module")
def client():
    with httpx.Client(
        base_url=BASE_URL,
        headers={
            "X-API-Key": ADMIN_KEY,
            "Content-Type": "application/json",
        },
        timeout=30.0,
    ) as c:
        yield c


def _poll_until(client: httpx.Client, provider: str, task_id: str,
                *, timeout_seconds: int = 180) -> dict[str, Any]:
    """Poll the provider until the task reaches a terminal state."""
    deadline = time.time() + timeout_seconds
    last: dict[str, Any] = {}
    while time.time() < deadline:
        r = client.get(f"/api/v1/admin/music/generate/{provider}/{task_id}")
        r.raise_for_status()
        last = r.json()
        if last.get("status") in ("succeeded", "failed"):
            return last
        time.sleep(4)
    pytest.fail(f"task {task_id} did not reach terminal state in {timeout_seconds}s: {last}")


# --- Fixtures: scratch artists + blueprint for an isolated test run --------

# Unique genre per-run so the scratch artist is guaranteed to be the top
# assignment pick (otherwise pre-existing roster pollution from earlier
# runs wins on the real "ambient" genre).
RUN_SUFFIX = uuid.uuid4().hex[:8]
TEST_GENRE = f"ambient_e2e_{RUN_SUFFIX}"


@pytest.fixture(scope="module")
def test_artist(client: httpx.Client):
    """Create a scratch artist just for this test run."""
    stage_name = f"E2E Test Artist {RUN_SUFFIX}"
    r = client.post(
        "/api/v1/admin/artists",
        json={
            "stage_name": stage_name,
            "legal_name": stage_name,
            "primary_genre": TEST_GENRE,
            "adjacent_genres": ["electronic", "chillout"],
            "voice_dna": {
                "timbre_core": "soft airy synthetic pads",
                "delivery_style": ["instrumental", "atmospheric"],
            },
            "visual_dna": {
                "face_description": "N/A — ambient project",
                "art_direction": "minimalist gradient",
            },
            "lyrical_dna": {
                "recurring_themes": ["space", "quiet", "distance"],
                "vocab_level": "poetic",
            },
            "audience_tags": ["lo_fi_fans", "study_beats_fans"],
        },
    )
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture(scope="module")
def test_blueprint(client: httpx.Client):
    """Persist a blueprint matching the test artist so assignment picks it."""
    r = client.post(
        "/api/v1/admin/blueprints",
        json={
            "genre_id": TEST_GENRE,
            "primary_genre": TEST_GENRE,
            "adjacent_genres": ["electronic", "chillout"],
            "target_themes": ["space", "quiet", "distance"],
            "vocabulary_tone": "poetic",
            "target_audience_tags": ["lo_fi_fans", "study_beats_fans"],
            "voice_requirements": {
                "timbre": "soft airy synthetic",
                "delivery": ["instrumental"],
            },
            "smart_prompt_text": (
                "soft ambient piano and synth pads, atmospheric and dreamy, "
                "slow tempo around 70 BPM"
            ),
            "smart_prompt_rationale": {
                "sonic_targeting": "E2E test blueprint — ambient slow-tempo",
            },
            "predicted_success_score": 0.5,
        },
    )
    assert r.status_code == 200, r.text
    return r.json()


# --- The test cases --------------------------------------------------------

def test_01_assignment_engine_returns_scoring_breakdown(
    client: httpx.Client, test_blueprint, test_artist,
):
    r = client.post(f"/api/v1/admin/blueprints/{test_blueprint['id']}/assign")
    assert r.status_code == 200, r.text
    decision = r.json()
    assert decision["proposal"] in ("reuse", "create_new")
    assert test_artist["artist_id"] in decision["scores"]
    assert "breakdown" in decision
    # Live dimensions must exist in the breakdown
    breakdown = decision["breakdown"][test_artist["artist_id"]]
    for key in ("genre_match", "voice_fit", "lyrical_fit", "audience_fit"):
        assert key in breakdown
    # Persist decision_id on the test_blueprint for next step
    test_blueprint["_decision_id"] = decision["decision_id"]
    test_blueprint["_proposal"] = decision["proposal"]


def test_02_ceo_decision_logged_in_db(client: httpx.Client, test_blueprint):
    r = client.get("/api/v1/admin/ceo-decisions?status=pending&limit=20")
    assert r.status_code == 200
    decisions = r.json()["decisions"]
    ours = next((d for d in decisions if d["decision_id"] == test_blueprint["_decision_id"]), None)
    assert ours is not None, "assignment decision not found in pending list"
    assert ours["decision_type"] == "artist_assignment"
    assert ours["status"] == "pending"


def test_03_ceo_approve_sets_blueprint_assigned_artist(
    client: httpx.Client, test_blueprint, test_artist,
):
    r = client.post(
        f"/api/v1/admin/ceo-decisions/{test_blueprint['_decision_id']}/approve",
        json={},
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "approved"

    # Verify blueprint now has assigned_artist_id set (only if proposal was reuse)
    if test_blueprint["_proposal"] == "reuse":
        r = client.get("/api/v1/admin/blueprints?status=assigned&limit=50")
        bps = r.json()["blueprints"]
        ours = next((b for b in bps if b["id"] == test_blueprint["id"]), None)
        assert ours is not None, "blueprint not in assigned list after approval"
        assert ours["assigned_artist_id"] == test_artist["artist_id"]
    else:
        pytest.skip("create_new proposal — no artist binding to verify yet")


def test_04_generation_orchestrator_creates_draft_song(
    client: httpx.Client, test_blueprint,
):
    if test_blueprint.get("_proposal") != "reuse":
        pytest.skip("create_new path — orchestrator needs full creation pipeline")
    r = client.post(
        f"/api/v1/admin/blueprints/{test_blueprint['id']}/generate-song",
        json={"provider": "musicgen", "duration_seconds": 8},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "song_id" in body and "task_id" in body
    assert body["provider"] == "musicgen"
    assert body["status"] == "draft"
    assert body["estimated_cost_usd"] == pytest.approx(0.064, abs=0.001)
    assert "[VOICE DNA]" in body["prompt_preview"]
    test_blueprint["_song_id"] = body["song_id"]
    test_blueprint["_task_id"] = body["task_id"]


def test_05_draft_song_row_exists_with_expected_shape(
    client: httpx.Client, test_blueprint, test_artist,
):
    song_id = test_blueprint.get("_song_id")
    if not song_id:
        pytest.skip("no song_id from previous step")
    r = client.get(f"/api/v1/admin/songs/{song_id}")
    assert r.status_code == 200
    song = r.json()
    assert song["status"] == "draft"
    assert song["blueprint_id"] == test_blueprint["id"]
    assert song["primary_artist_id"] == test_artist["artist_id"]
    assert song["generation_provider"] == "musicgen"
    assert song["release_id"] is None


def test_06_poll_succeeds_and_flips_to_qa_pending(
    client: httpx.Client, test_blueprint,
):
    task_id = test_blueprint.get("_task_id")
    song_id = test_blueprint.get("_song_id")
    if not (task_id and song_id):
        pytest.skip("no task to poll")
    result = _poll_until(client, "musicgen", task_id, timeout_seconds=120)
    assert result["status"] == "succeeded", f"provider failed: {result}"
    assert result["audio_url"], "no audio_url after success"
    assert result["audio_url"].startswith("/api/v1/admin/music/audio/"), \
        "audio_url should be the self-hosted backend path"

    # After the terminal poll, songs_master should be qa_pending
    r = client.get(f"/api/v1/admin/songs/{song_id}")
    song = r.json()
    assert song["status"] == "qa_pending", f"expected qa_pending, got {song['status']}"
    assert song["audio_assets"], "audio_assets array empty"
    master = next((a for a in song["audio_assets"] if a["is_master_candidate"]), None)
    assert master is not None
    assert master["storage_url"].startswith("/api/v1/admin/music/audio/")


def test_07_stream_endpoint_returns_playable_bytes(
    client: httpx.Client, test_blueprint,
):
    task_id = test_blueprint.get("_task_id")
    if not task_id:
        pytest.skip("no task")
    # Anonymous — no API key header
    r = httpx.get(
        f"{BASE_URL}/api/v1/admin/music/audio/musicgen/{task_id}.mp3",
        timeout=30.0,
    )
    assert r.status_code == 200
    assert r.headers.get("content-type", "").startswith("audio/")
    assert len(r.content) > 5_000, "audio payload too small to be valid"


def test_08_audio_qa_lite_sweep_flips_to_qa_passed(
    client: httpx.Client, test_blueprint,
):
    song_id = test_blueprint.get("_song_id")
    if not song_id:
        pytest.skip("no song")
    r = client.post("/api/v1/admin/sweeps/audio-qa")
    assert r.status_code == 200, r.text
    stats = r.json()["stats"]
    assert stats["scanned"] >= 1
    # Verify our song flipped
    r = client.get(f"/api/v1/admin/songs/{song_id}")
    song = r.json()
    assert song["status"] == "qa_passed", f"expected qa_passed, got {song['status']}"
    assert song["qa_pass"] is True


def test_09_release_creation_and_track_binding(
    client: httpx.Client, test_blueprint, test_artist,
):
    song_id = test_blueprint.get("_song_id")
    if not song_id:
        pytest.skip("no song")

    # Create release
    r = client.post(
        "/api/v1/admin/releases",
        json={
            "artist_id": test_artist["artist_id"],
            "title": f"E2E Test Release {uuid.uuid4().hex[:6]}",
            "release_type": "single",
        },
    )
    assert r.status_code == 200, r.text
    release = r.json()
    assert release["status"] == "planning"
    release_id = release["id"]

    # Bind the song
    r = client.post(
        f"/api/v1/admin/releases/{release_id}/tracks",
        json={"song_id": song_id, "track_number": 1, "is_lead_single": True},
    )
    assert r.status_code == 200, r.text
    assert r.json()["song_status"] == "assigned_to_release"

    # Verify detail endpoint reports the binding
    r = client.get(f"/api/v1/admin/releases/{release_id}")
    detail = r.json()
    assert detail["track_count"] == 1
    track = detail["tracks"][0]
    assert track["song_id"] == song_id
    assert track["is_lead_single"] is True

    # Verify the song now shows assigned_to_release + release_id set
    r = client.get(f"/api/v1/admin/songs/{song_id}")
    song = r.json()
    assert song["status"] == "assigned_to_release"
    assert song["release_id"] == release_id
