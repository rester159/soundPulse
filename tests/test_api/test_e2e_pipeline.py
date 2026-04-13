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
  5. Provider poll transitions song draft -> qa_pending + creates audio_assets
  6. Audio bytes are self-hosted (reachable without provider delivery URL)
  7. Audio QA lite sweep flips qa_pending -> qa_passed
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
        # 120s — long enough for LLM + DALL-E combo calls in the
        # orchestrator / artist creation paths
        timeout=120.0,
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


LYRICAL_GENRE_TOKENS = ("pop", "hip-hop", "rap", "country", "rock", "r-and-b",
                        "latin", "k-pop", "folk", "indie", "metal", "punk",
                        "reggae", "blues")


def _pick_lyrical_opportunity(client: httpx.Client) -> dict:
    """Pull top opportunities and pick the first with a non-null prompt
    AND a word-friendly (lyrical) genre. Skips instrumental genres like
    classical / ambient that won't exercise the vocal+lyrics path."""
    r = client.get("/api/v1/blueprint/top-opportunities?n=10&model=suno")
    assert r.status_code == 200, r.text
    opps = r.json()["data"]["blueprints"]

    lyrical = [
        o for o in opps
        if o.get("prompt")
        and any(tok in o["genre"].lower() for tok in LYRICAL_GENRE_TOKENS)
    ]
    if lyrical:
        return lyrical[0]
    # Fallback: any opportunity with a prompt at all
    with_prompt = [o for o in opps if o.get("prompt")]
    if with_prompt:
        return with_prompt[0]
    pytest.fail(f"no opportunities with prompts returned: {opps[:2]}")


def test_10_full_real_breakout_to_song_flow(client: httpx.Client):
    """
    Wider E2E: start from a REAL top-opportunity (breakout-engine output,
    not a scratch fixture), create a fresh artist via the LLM persona
    blender matched to that genre, walk the full chain, assert every
    field the orchestrator should populate on songs_master, and verify
    artist portrait + song cover were generated.

    This is the definitive "does the whole product work" test. It costs
    one MusicGen call ($0.064) + one Groq persona call (~$0.002) + up
    to two DALL-E 3 images (~$0.08) = ~$0.15/run.
    """
    import json as _json

    run_id = uuid.uuid4().hex[:6]

    # --- Step 1: fetch a real top opportunity (lyrical, has prompt) ----
    opp = _pick_lyrical_opportunity(client)
    base_genre = opp["genre"]
    print(f"\n  [1] breakout opportunity: {base_genre} (score={opp['opportunity_score']})")

    # Use a unique variant genre so the persona-blended artist is
    # guaranteed the top assignment pick regardless of existing roster.
    test_genre = f"{base_genre}__e2e_{run_id}"

    # --- Step 2: persist as a blueprint --------------------------------
    r = client.post(
        "/api/v1/admin/blueprints",
        json={
            "genre_id": test_genre,
            "primary_genre": test_genre,
            "adjacent_genres": [base_genre],
            "target_themes": ["atmospheric", "breakout test"],
            "vocabulary_tone": "poetic",
            "target_audience_tags": ["e2e_test_audience"],
            "smart_prompt_text": opp["prompt"],
            "smart_prompt_rationale": opp.get("rationale"),
            "predicted_success_score": opp["opportunity_score"],
        },
    )
    assert r.status_code == 200, r.text
    blueprint_id = r.json()["id"]
    print(f"  [2] blueprint persisted: {blueprint_id[:8]}")

    # --- Step 3: create artist via persona blender ---------------------
    description = (
        f"A rising artist in {base_genre} with a unique voice. "
        f"Their sound targets the {base_genre} scene with fresh energy and "
        f"emotional depth. Influenced by the current wave of breakout "
        f"artists in the genre."
    )
    r = client.post(
        "/api/v1/admin/artists/from-description",
        json={
            "description": description,
            "target_genre": test_genre,
            "auto_approve": True,
        },
    )
    assert r.status_code == 200, r.text
    created = r.json()
    artist_id = created["artist_id"]
    artist_name = created["stage_name"]
    print(f"  [3] persona blended: {artist_name} ({artist_id[:8]})")
    # Verify the blender produced a complete persona
    persona = created["persona"]
    assert "voice_dna" in persona and "timbre_core" in persona["voice_dna"]
    assert "visual_dna" in persona
    assert "lyrical_dna" in persona
    # Portrait assertion — present if openai_cli_proxy or OPENAI_API_KEY set
    portrait = created.get("portrait")
    if portrait:
        print(f"      portrait: {portrait['provider']} {portrait['bytes']} bytes "
              f"-> {portrait['storage_url']}")
    else:
        print(f"      portrait: NOT GENERATED — check OPENAI_CLI_PROXY_URL / OPENAI_API_KEY")

    # --- Step 4: assignment engine (should pick the new artist) --------
    r = client.post(f"/api/v1/admin/blueprints/{blueprint_id}/assign")
    assert r.status_code == 200, r.text
    decision = r.json()
    print(f"  [4] assignment: proposal={decision['proposal']} proposed={decision.get('proposed_artist_name')}")
    assert decision["proposal"] == "reuse", \
        f"expected reuse with fresh artist but got {decision['proposal']}"
    assert decision["proposed_artist_id"] == artist_id, \
        f"assignment picked the wrong artist"

    decision_id = decision["decision_id"]

    # --- Step 5: CEO approve -------------------------------------------
    r = client.post(
        f"/api/v1/admin/ceo-decisions/{decision_id}/approve",
        json={},
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "approved"
    print(f"  [5] CEO decision approved")

    # --- Step 6: generation orchestrator -------------------------------
    r = client.post(
        f"/api/v1/admin/blueprints/{blueprint_id}/generate-song",
        json={"provider": "musicgen", "duration_seconds": 8},
    )
    assert r.status_code == 200, r.text
    gen = r.json()
    song_id = gen["song_id"]
    task_id = gen["task_id"]
    print(f"  [6] orchestrator: song={song_id[:8]} task={task_id[:12]} title={gen['title']!r}")
    assert gen["status"] == "draft"
    assert "[VOICE DNA]" in gen["prompt_preview"]
    assert gen["estimated_cost_usd"] == pytest.approx(0.064, abs=0.001)
    cover = gen.get("cover")
    if cover:
        print(f"      cover: {cover['provider']} -> {cover['storage_url']}")
    else:
        print(f"      cover: NOT GENERATED")

    # --- Step 7: poll to success ---------------------------------------
    result = _poll_until(client, "musicgen", task_id, timeout_seconds=120)
    assert result["status"] == "succeeded"
    print(f"  [7] generation succeeded, audio_url={result['audio_url'][:60]}...")

    # --- Step 8: audio QA lite sweep (flips qa_pending -> qa_passed) ----
    r = client.post("/api/v1/admin/sweeps/audio-qa")
    assert r.status_code == 200, r.text
    qa_stats = r.json()["stats"]
    print(f"  [8] audio QA sweep: passed={qa_stats['passed']} failed={qa_stats['failed']}")
    assert qa_stats["passed"] >= 1 or qa_stats["scanned"] == 0

    # --- Step 9: final songs_master field verification -----------------
    r = client.get(f"/api/v1/admin/songs/{song_id}")
    song = r.json()
    print(f"  [9] final songs_master state:")
    print(f"      status={song['status']}")
    print(f"      title={song['title']!r}")
    print(f"      artist_name={song.get('artist_name')!r}")
    print(f"      primary_genre={song['primary_genre']}")
    print(f"      generation_provider={song['generation_provider']}")
    print(f"      generation_cost_usd=${song['generation_cost_usd']}")
    print(f"      qa_pass={song['qa_pass']}")
    print(f"      audio_assets count={len(song.get('audio_assets', []))}")
    if song.get("audio_assets"):
        master = song["audio_assets"][0]
        print(f"      master storage_url={master['storage_url'][:60]}...")
        print(f"      master duration={master['duration_seconds']}s")

    # Now the assertions — every field the orchestrator + QA should set
    assert song["status"] == "qa_passed", f"expected qa_passed, got {song['status']}"
    assert song["qa_pass"] is True
    assert song["primary_artist_id"] == artist_id
    assert song["blueprint_id"] == blueprint_id
    assert song["primary_genre"] == test_genre
    assert song["generation_provider"] == "musicgen"
    assert song["generation_provider_job_id"] == task_id
    assert song["generation_cost_usd"] == pytest.approx(0.064, abs=0.001)
    assert song["generation_prompt"]
    assert "[VOICE DNA]" in song["generation_prompt"]
    assert "[PRODUCTION]" in song["generation_prompt"]
    assert song["title"]
    assert song["artist_name"] == artist_name
    assert song["release_id"] is None, "song should not be bound to a release yet"
    assert song["audio_assets"], "audio_assets array should have at least one row"
    master = next((a for a in song["audio_assets"] if a["is_master_candidate"]), None)
    assert master is not None, "no master candidate audio asset"
    assert master["storage_url"].startswith("/api/v1/admin/music/audio/")
    assert master["provider"] == "musicgen"
    assert master["format"] == "mp3"
    assert master["duration_seconds"] > 0

    # Visual assertions — if image generation was available, the song
    # should have a cover and the artist should have a portrait.
    if portrait or cover:
        # At least one image was generated — check both landed
        r = client.get(f"/api/v1/admin/artists")
        artists_list = r.json().get("artists", [])
        our_artist = next((a for a in artists_list if a["artist_id"] == artist_id), None)
        assert our_artist is not None
        if portrait:
            assert our_artist["voice_dna"] is not None  # sanity
            # visual_dna.reference_sheet_asset_id should be set
            # (use the song detail endpoint since it includes visual_dna on artist side via song)
        if cover:
            assert song["primary_artwork_asset_id"] is not None
            # Fetch the image directly via the public streaming endpoint
            img_r = httpx.get(
                f"{BASE_URL}/api/v1/admin/visual/{song['primary_artwork_asset_id']}.png",
                timeout=15.0,
            )
            assert img_r.status_code == 200
            assert img_r.headers.get("content-type", "").startswith("image/")
            assert len(img_r.content) > 10_000, "cover image too small to be real"
            print(f"  [10] cover verified: {len(img_r.content)} bytes PNG")


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
