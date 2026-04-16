"""
Admin CRUD + artist patch endpoints for genre structures (task #109 Phase 3).

Uses the project's HTTP test client + the rolled-back db_session fixture
from conftest. Endpoints are admin-key gated.
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text as _text
from sqlalchemy.ext.asyncio import AsyncSession


VALID_STRUCTURE = [
    {"name": "Intro", "bars": 8, "vocals": False},
    {"name": "Verse", "bars": 16, "vocals": True},
    {"name": "Chorus", "bars": 8, "vocals": True},
]


# --- Genre structures CRUD -------------------------------------------------


@pytest.mark.asyncio
async def test_list_genre_structures_returns_seeded_rows(client, admin_headers):
    resp = await client.get("/api/v1/admin/genre-structures", headers=admin_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] >= 20  # 20 seed rows from migration 033
    keys = {row["primary_genre"] for row in body["items"]}
    assert "pop" in keys
    assert "hip-hop.trap.drill" in keys


@pytest.mark.asyncio
async def test_get_genre_structure_seeded_row(client, admin_headers):
    resp = await client.get(
        "/api/v1/admin/genre-structures/pop", headers=admin_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["primary_genre"] == "pop"
    assert len(body["structure"]) == 10
    assert body["structure"][0]["name"] == "Intro"


@pytest.mark.asyncio
async def test_get_genre_structure_404_for_unknown(client, admin_headers):
    resp = await client.get(
        "/api/v1/admin/genre-structures/not-a-real-genre",
        headers=admin_headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_put_creates_new_genre_structure(client, admin_headers):
    pg = "test.put-create"
    resp = await client.put(
        f"/api/v1/admin/genre-structures/{pg}",
        headers=admin_headers,
        json={
            "structure": VALID_STRUCTURE,
            "notes": "phase3 test",
            "updated_by": "pytest",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["primary_genre"] == pg
    assert body["notes"] == "phase3 test"
    assert body["updated_by"] == "pytest"
    assert len(body["structure"]) == len(VALID_STRUCTURE)


@pytest.mark.asyncio
async def test_put_overwrites_existing_genre_structure(client, admin_headers):
    pg = "test.put-overwrite"
    await client.put(
        f"/api/v1/admin/genre-structures/{pg}",
        headers=admin_headers,
        json={"structure": [{"name": "Intro", "bars": 4, "vocals": False}], "notes": "v1"},
    )
    resp = await client.put(
        f"/api/v1/admin/genre-structures/{pg}",
        headers=admin_headers,
        json={"structure": VALID_STRUCTURE, "notes": "v2"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["notes"] == "v2"
    assert len(body["structure"]) == len(VALID_STRUCTURE)


@pytest.mark.asyncio
async def test_put_rejects_zero_bars_with_422(client, admin_headers):
    """Zero bars violates the Pydantic gt=0 validator at the API layer."""
    resp = await client.put(
        "/api/v1/admin/genre-structures/test.zero",
        headers=admin_headers,
        json={"structure": [{"name": "Intro", "bars": 0, "vocals": False}]},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_put_rejects_empty_structure_with_422(client, admin_headers):
    resp = await client.put(
        "/api/v1/admin/genre-structures/test.empty",
        headers=admin_headers,
        json={"structure": []},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_delete_removes_existing_row(client, admin_headers):
    pg = "test.delete-me"
    await client.put(
        f"/api/v1/admin/genre-structures/{pg}",
        headers=admin_headers,
        json={"structure": VALID_STRUCTURE},
    )
    resp = await client.delete(
        f"/api/v1/admin/genre-structures/{pg}", headers=admin_headers,
    )
    assert resp.status_code == 200
    assert resp.json() == {"deleted": pg}
    # confirm gone
    resp2 = await client.get(
        f"/api/v1/admin/genre-structures/{pg}", headers=admin_headers,
    )
    assert resp2.status_code == 404


@pytest.mark.asyncio
async def test_delete_404_for_unknown(client, admin_headers):
    resp = await client.delete(
        "/api/v1/admin/genre-structures/not-a-real-genre",
        headers=admin_headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_admin_endpoints_require_api_key(client):
    """Without a valid X-API-Key header the route must NOT return 200.
    FastAPI's header dependency may reject with 422 (missing required
    header) or 401/403 (handled by require_admin) — any non-200 is
    proof the auth gate is wired."""
    resp = await client.get("/api/v1/admin/genre-structures")
    assert resp.status_code in (401, 403, 422)


# --- Artist structure patch ------------------------------------------------


@pytest.fixture
async def sample_ai_artist(db_session: AsyncSession):
    """Insert a minimal ai_artists row + return its UUID. The conftest
    rolls back the session so this row never persists past the test."""
    aid = uuid.uuid4()
    await db_session.execute(
        _text("""
            INSERT INTO ai_artists (
                artist_id, stage_name, legal_name, primary_genre,
                voice_dna, visual_dna
            ) VALUES (
                :aid, :stage, :legal, 'pop', '{}'::jsonb, '{}'::jsonb
            )
        """),
        {"aid": aid, "stage": f"Test {aid.hex[:6]}", "legal": "Test Legal"},
    )
    await db_session.flush()
    return aid


@pytest.mark.asyncio
async def test_patch_artist_sets_structure_template(
    client, admin_headers, sample_ai_artist,
):
    aid = str(sample_ai_artist)
    resp = await client.patch(
        f"/api/v1/admin/artists/{aid}/structure",
        headers=admin_headers,
        json={"structure_template": VALID_STRUCTURE},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["artist_id"] == aid
    assert len(body["structure_template"]) == len(VALID_STRUCTURE)
    assert body["genre_structure_override"] is False  # untouched default


@pytest.mark.asyncio
async def test_patch_artist_sets_override_flag(
    client, admin_headers, sample_ai_artist,
):
    aid = str(sample_ai_artist)
    resp = await client.patch(
        f"/api/v1/admin/artists/{aid}/structure",
        headers=admin_headers,
        json={"genre_structure_override": True},
    )
    assert resp.status_code == 200
    assert resp.json()["genre_structure_override"] is True


@pytest.mark.asyncio
async def test_patch_artist_clear_template_with_explicit_null(
    client, admin_headers, sample_ai_artist,
):
    aid = str(sample_ai_artist)
    # set then clear
    await client.patch(
        f"/api/v1/admin/artists/{aid}/structure",
        headers=admin_headers,
        json={"structure_template": VALID_STRUCTURE},
    )
    resp = await client.patch(
        f"/api/v1/admin/artists/{aid}/structure",
        headers=admin_headers,
        json={"structure_template": None},
    )
    assert resp.status_code == 200
    assert resp.json()["structure_template"] is None


@pytest.mark.asyncio
async def test_patch_artist_404_for_missing(client, admin_headers):
    fake = str(uuid.uuid4())
    resp = await client.patch(
        f"/api/v1/admin/artists/{fake}/structure",
        headers=admin_headers,
        json={"genre_structure_override": True},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_patch_artist_400_for_invalid_uuid(client, admin_headers):
    resp = await client.patch(
        "/api/v1/admin/artists/not-a-uuid/structure",
        headers=admin_headers,
        json={"genre_structure_override": True},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_patch_artist_422_for_invalid_structure(
    client, admin_headers, sample_ai_artist,
):
    aid = str(sample_ai_artist)
    resp = await client.patch(
        f"/api/v1/admin/artists/{aid}/structure",
        headers=admin_headers,
        json={"structure_template": [{"name": "X", "bars": 0, "vocals": True}]},
    )
    assert resp.status_code == 422
