"""Tests for the health and root endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_root_returns_200(client: AsyncClient):
    response = await client.get("/")
    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "SoundPulse API"
    assert "version" in body


@pytest.mark.asyncio
async def test_health_returns_200(client: AsyncClient):
    response = await client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
