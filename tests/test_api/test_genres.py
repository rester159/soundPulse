"""Tests for the /api/v1/genres endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_get_genres_with_auth(client: AsyncClient, admin_headers: dict):
    response = await client.get("/api/v1/genres", headers=admin_headers)
    assert response.status_code == 200
    body = response.json()
    assert "data" in body


@pytest.mark.asyncio
async def test_get_genres_without_auth(client: AsyncClient):
    response = await client.get("/api/v1/genres")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_genre_not_found(client: AsyncClient, admin_headers: dict):
    response = await client.get("/api/v1/genres/nonexistent-genre-id", headers=admin_headers)
    assert response.status_code == 404
