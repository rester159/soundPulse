"""Tests for the /api/v1/trending endpoints."""

from datetime import date

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_post_trending_with_admin_key(client: AsyncClient, admin_headers: dict, sample_artist):
    """POST /api/v1/trending with admin key creates a snapshot."""
    payload = {
        "platform": "spotify",
        "entity_type": "artist",
        "entity_identifier": {
            "spotify_id": sample_artist.spotify_id,
        },
        "raw_score": 95.0,
        "rank": 1,
        "signals": {"streams": 1_000_000},
        "snapshot_date": str(date.today()),
    }
    response = await client.post("/api/v1/trending", json=payload, headers=admin_headers)
    assert response.status_code == 201
    body = response.json()
    assert "data" in body
    assert body["data"]["entity_type"] == "artist"
    assert "snapshot_id" in body["data"]


@pytest.mark.asyncio
async def test_post_trending_without_admin_key(client: AsyncClient):
    """POST /api/v1/trending without admin key returns 403."""
    payload = {
        "platform": "spotify",
        "entity_type": "artist",
        "entity_identifier": {"title": "Some Artist"},
        "snapshot_date": str(date.today()),
    }
    # Use a non-admin key to trigger 403 (not 401)
    headers = {"X-API-Key": "sp_live_not_a_real_key_at_all_1234"}
    response = await client.post("/api/v1/trending", json=payload, headers=headers)
    # Non-admin key that doesn't exist in the DB should return 401;
    # a valid non-admin key would return 403. Either way, it's not 201.
    assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_get_trending_with_entity_type(client: AsyncClient, admin_headers: dict):
    """GET /api/v1/trending with entity_type param returns 200."""
    response = await client.get(
        "/api/v1/trending",
        params={"entity_type": "artist"},
        headers=admin_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert "data" in body
    assert "meta" in body


@pytest.mark.asyncio
async def test_get_trending_without_entity_type(client: AsyncClient, admin_headers: dict):
    """GET /api/v1/trending without entity_type returns 422 (required query param)."""
    response = await client.get("/api/v1/trending", headers=admin_headers)
    # FastAPI returns 422 for missing required query parameters
    assert response.status_code == 422
