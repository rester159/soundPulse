"""Tests for the /api/v1/trending/bulk endpoint and the deferred sweeps."""

import uuid
from datetime import date, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from api.models.track import Track
from api.models.trending_snapshot import TrendingSnapshot


def _make_item(
    spotify_id: str | None = None,
    title: str | None = None,
    artist_name: str | None = "Test Artist",
    rank: int = 1,
    raw_score: float = 95.0,
    snapshot_date_str: str | None = None,
    platform: str = "chartmetric",
) -> dict:
    """Build a TrendingIngest dict suitable for the bulk endpoint."""
    return {
        "platform": platform,
        "entity_type": "track",
        "entity_identifier": {
            "spotify_id": spotify_id,
            "title": title,
            "artist_name": artist_name,
        },
        "raw_score": raw_score,
        "rank": rank,
        "signals": {"chart_type": "test", "source_platform": "test"},
        "snapshot_date": snapshot_date_str or str(date.today()),
    }


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_bulk_ingest_creates_snapshots_and_entities(
    client: AsyncClient, admin_headers: dict
):
    """POST /trending/bulk with 5 brand new items creates 5 snapshots + 5 entities."""
    items = [
        _make_item(
            spotify_id=f"sp_test_bulk_{uuid.uuid4().hex[:18]}",
            title=f"Bulk Test Track {i}",
            rank=i + 1,
        )
        for i in range(5)
    ]
    resp = await client.post(
        "/api/v1/trending/bulk", json={"items": items}, headers=admin_headers
    )
    assert resp.status_code == 201
    body = resp.json()["data"]
    assert body["received"] == 5
    assert body["ingested"] == 5
    assert body["duplicates"] == 0
    assert body["errors"] == 0
    assert body["entities_created"] == 5
    assert body["elapsed_ms"] > 0


@pytest.mark.asyncio
async def test_bulk_ingest_dedups_on_repeat(
    client: AsyncClient, admin_headers: dict
):
    """POSTing the same items twice ingests them on the first call and skips on the second."""
    item = _make_item(
        spotify_id=f"sp_test_dedup_{uuid.uuid4().hex[:18]}",
        title="Dedup Test Track",
        rank=1,
    )
    payload = {"items": [item]}

    first = await client.post("/api/v1/trending/bulk", json=payload, headers=admin_headers)
    assert first.status_code == 201
    assert first.json()["data"]["ingested"] == 1
    assert first.json()["data"]["duplicates"] == 0

    second = await client.post("/api/v1/trending/bulk", json=payload, headers=admin_headers)
    assert second.status_code == 201
    body2 = second.json()["data"]
    assert body2["received"] == 1
    assert body2["ingested"] == 0
    assert body2["duplicates"] == 1


# ---------------------------------------------------------------------------
# Validation errors
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_bulk_rejects_invalid_platform(client: AsyncClient, admin_headers: dict):
    """An item with an unknown platform fails the whole batch with a 400."""
    items = [_make_item(spotify_id=f"sp_{uuid.uuid4().hex[:20]}", title="x", platform="not_a_platform")]
    resp = await client.post(
        "/api/v1/trending/bulk", json={"items": items}, headers=admin_headers
    )
    assert resp.status_code == 400
    assert "invalid platform" in resp.text.lower()


@pytest.mark.asyncio
async def test_bulk_rejects_no_identifier(client: AsyncClient, admin_headers: dict):
    """An item with no usable identifier fails the whole batch with a 422."""
    items = [{
        "platform": "chartmetric",
        "entity_type": "track",
        "entity_identifier": {},  # nothing usable
        "snapshot_date": str(date.today()),
    }]
    resp = await client.post(
        "/api/v1/trending/bulk", json={"items": items}, headers=admin_headers
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_bulk_rejects_empty_items(client: AsyncClient, admin_headers: dict):
    """An empty items array is rejected by Pydantic min_length=1."""
    resp = await client.post(
        "/api/v1/trending/bulk", json={"items": []}, headers=admin_headers
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_bulk_rejects_oversize_batch(client: AsyncClient, admin_headers: dict):
    """A batch larger than 1000 items is rejected by Pydantic max_length=1000."""
    items = [_make_item(spotify_id=f"sp_{i:020}", title=f"t{i}") for i in range(1001)]
    resp = await client.post(
        "/api/v1/trending/bulk", json={"items": items}, headers=admin_headers
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Deferred classification + composite markers
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_bulk_marks_entities_needs_classification(
    client: AsyncClient, admin_headers: dict, db_session
):
    """After bulk ingest, every newly created track has needs_classification=true."""
    sp_id = f"sp_test_cls_{uuid.uuid4().hex[:18]}"
    items = [_make_item(spotify_id=sp_id, title="Classification Marker Track")]
    resp = await client.post(
        "/api/v1/trending/bulk", json={"items": items}, headers=admin_headers
    )
    assert resp.status_code == 201

    # Look up the track via spotify_id and verify the marker
    result = await db_session.execute(
        select(Track).where(Track.spotify_id == sp_id)
    )
    track = result.scalar_one_or_none()
    assert track is not None, "track was not created by bulk ingest"
    assert track.metadata_json is not None
    assert track.metadata_json.get("needs_classification") is True


@pytest.mark.asyncio
async def test_bulk_snapshots_have_zero_normalized_score(
    client: AsyncClient, admin_headers: dict, db_session
):
    """Bulk-ingested snapshots are inserted with normalized_score=0 (deferred)."""
    sp_id = f"sp_test_norm_{uuid.uuid4().hex[:18]}"
    items = [_make_item(spotify_id=sp_id, title="Normalize Marker Track", rank=42, raw_score=88.0)]
    resp = await client.post(
        "/api/v1/trending/bulk", json={"items": items}, headers=admin_headers
    )
    assert resp.status_code == 201

    result = await db_session.execute(
        select(Track).where(Track.spotify_id == sp_id)
    )
    track = result.scalar_one_or_none()
    assert track is not None

    snap_result = await db_session.execute(
        select(TrendingSnapshot).where(TrendingSnapshot.entity_id == track.id)
    )
    snapshots = snap_result.scalars().all()
    assert len(snapshots) >= 1
    for snap in snapshots:
        assert snap.normalized_score == 0.0
        # The original raw values must be preserved for the sweep to use later
        assert snap.platform_score == 88.0
        assert snap.platform_rank == 42


# ---------------------------------------------------------------------------
# Deferred sweeps — verify they actually clear the flags
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_classification_sweep_processes_pending_entities(
    client: AsyncClient, admin_headers: dict, db_session
):
    """After bulk ingest + classification sweep, the needs_classification flag is cleared."""
    from api.services.classification_sweep import sweep_unclassified_entities

    sp_id = f"sp_test_sweep_{uuid.uuid4().hex[:18]}"
    items = [_make_item(
        spotify_id=sp_id,
        title="Sweep Test Track",
    )]
    items[0]["signals"]["spotify_genres"] = ["pop", "dance pop"]  # give the classifier something to chew on

    resp = await client.post(
        "/api/v1/trending/bulk", json={"items": items}, headers=admin_headers
    )
    assert resp.status_code == 201

    # Run the sweep against the same DB session the test client uses
    stats = await sweep_unclassified_entities(db_session, batch_size=10)
    assert stats["tracks_processed"] >= 1

    # Verify the flag is cleared
    result = await db_session.execute(
        select(Track).where(Track.spotify_id == sp_id)
    )
    track = result.scalar_one_or_none()
    assert track is not None
    assert track.metadata_json.get("needs_classification") is False
    assert "classified_at" in track.metadata_json


@pytest.mark.asyncio
async def test_composite_sweep_normalizes_zero_scores(
    client: AsyncClient, admin_headers: dict, db_session
):
    """After bulk ingest + composite sweep, normalized_score is no longer 0."""
    from api.services.composite_sweep import sweep_zero_normalized_snapshots

    sp_id = f"sp_test_comp_{uuid.uuid4().hex[:18]}"
    items = [_make_item(
        spotify_id=sp_id,
        title="Composite Sweep Track",
        rank=10,
        raw_score=80.0,
    )]
    resp = await client.post(
        "/api/v1/trending/bulk", json={"items": items}, headers=admin_headers
    )
    assert resp.status_code == 201

    stats = await sweep_zero_normalized_snapshots(db_session, batch_size=10)
    assert stats["snapshots_processed"] >= 1

    # The snapshot should now have normalized_at set in signals_json
    result = await db_session.execute(
        select(Track).where(Track.spotify_id == sp_id)
    )
    track = result.scalar_one_or_none()
    assert track is not None

    snap_result = await db_session.execute(
        select(TrendingSnapshot).where(TrendingSnapshot.entity_id == track.id)
    )
    snapshots = snap_result.scalars().all()
    assert len(snapshots) >= 1
    for snap in snapshots:
        assert (snap.signals_json or {}).get("normalized_at") is not None
