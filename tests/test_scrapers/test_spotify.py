import pytest
from datetime import date
from unittest.mock import AsyncMock, patch, MagicMock
import httpx

from scrapers.base import RawDataPoint, IngestionError
from scrapers.spotify import SpotifyScraper


@pytest.fixture
def scraper():
    """Create a SpotifyScraper with test credentials."""
    s = SpotifyScraper(
        credentials={"client_id": "test_id", "client_secret": "test_secret"},
        api_base_url="http://localhost:8000",
        admin_key="test_admin_key",
    )
    return s


def _mock_response(status_code=200, json_data=None, headers=None):
    """Create a mock httpx.Response."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.headers = headers or {}
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "error", request=MagicMock(), response=resp
        )
    return resp


# Mock Spotify API responses
MOCK_TOKEN_RESPONSE = {
    "access_token": "mock_token_abc123",
    "token_type": "Bearer",
    "expires_in": 3600,
}

MOCK_PLAYLIST_RESPONSE = {
    "items": [
        {
            "track": {
                "id": "track_001",
                "name": "Test Song",
                "artists": [{"id": "artist_001", "name": "Test Artist"}],
                "external_ids": {"isrc": "USRC12345678"},
                "popularity": 85,
                "duration_ms": 210000,
            }
        },
        {
            "track": {
                "id": "track_002",
                "name": "Another Song",
                "artists": [{"id": "artist_002", "name": "Another Artist"}],
                "external_ids": {"isrc": "GBRC98765432"},
                "popularity": 72,
                "duration_ms": 185000,
            }
        },
    ],
    "next": None,
}

MOCK_AUDIO_FEATURES_RESPONSE = {
    "audio_features": [
        {
            "id": "track_001",
            "tempo": 128.0,
            "energy": 0.75,
            "valence": 0.6,
            "danceability": 0.82,
            "acousticness": 0.05,
            "instrumentalness": 0.01,
        },
        {
            "id": "track_002",
            "tempo": 95.0,
            "energy": 0.55,
            "valence": 0.45,
            "danceability": 0.7,
            "acousticness": 0.15,
            "instrumentalness": 0.0,
        },
    ]
}

MOCK_ARTISTS_RESPONSE = {
    "artists": [
        {
            "id": "artist_001",
            "name": "Test Artist",
            "genres": ["pop", "dance pop"],
            "popularity": 88,
            "followers": {"total": 5000000},
        },
        {
            "id": "artist_002",
            "name": "Another Artist",
            "genres": ["hip hop", "rap"],
            "popularity": 75,
            "followers": {"total": 2000000},
        },
    ]
}


class TestSpotifyAuthentication:
    async def test_authenticate_success(self, scraper):
        """Successful authentication stores access token."""
        scraper.client.request = AsyncMock(
            return_value=_mock_response(200, MOCK_TOKEN_RESPONSE)
        )
        await scraper.authenticate()
        assert scraper.access_token == "mock_token_abc123"

    async def test_authenticate_failure(self, scraper):
        """Failed authentication raises AuthenticationError."""
        from scrapers.base import AuthenticationError
        scraper.client.request = AsyncMock(
            return_value=_mock_response(401, {"error": "invalid_client"})
        )
        with pytest.raises(AuthenticationError):
            await scraper.authenticate()


class TestSpotifyCollectTrending:
    async def test_collect_returns_data_points(self, scraper):
        """collect_trending returns list of RawDataPoint."""
        scraper.access_token = "mock_token"

        # Mock all API calls
        async def mock_request(method, url, **kwargs):
            if "playlists" in url and "tracks" in url:
                return _mock_response(200, MOCK_PLAYLIST_RESPONSE)
            elif "audio-features" in url:
                return _mock_response(200, MOCK_AUDIO_FEATURES_RESPONSE)
            elif "artists" in url and "?" in url:
                return _mock_response(200, MOCK_ARTISTS_RESPONSE)
            return _mock_response(200, {})

        scraper.client.request = AsyncMock(side_effect=mock_request)
        # Use only 1 playlist to speed up test
        scraper.TRENDING_PLAYLISTS = {"test_playlist_id": "Test Playlist"}

        points = await scraper.collect_trending()

        assert len(points) > 0
        assert all(isinstance(p, RawDataPoint) for p in points)

        # Should have both track and artist data points
        track_points = [p for p in points if p.entity_type == "track"]
        artist_points = [p for p in points if p.entity_type == "artist"]
        assert len(track_points) >= 2
        assert len(artist_points) >= 2

    async def test_track_data_point_structure(self, scraper):
        """Track data points have correct entity_identifier and signals."""
        scraper.access_token = "mock_token"

        async def mock_request(method, url, **kwargs):
            if "playlists" in url and "tracks" in url:
                return _mock_response(200, MOCK_PLAYLIST_RESPONSE)
            elif "audio-features" in url:
                return _mock_response(200, MOCK_AUDIO_FEATURES_RESPONSE)
            elif "artists" in url and "?" in url:
                return _mock_response(200, MOCK_ARTISTS_RESPONSE)
            return _mock_response(200, {})

        scraper.client.request = AsyncMock(side_effect=mock_request)
        scraper.TRENDING_PLAYLISTS = {"test_playlist_id": "Test Playlist"}

        points = await scraper.collect_trending()
        track_point = next(p for p in points if p.entity_type == "track")

        assert track_point.platform == "spotify"
        assert "spotify_id" in track_point.entity_identifier
        assert "title" in track_point.entity_identifier
        assert "artist_name" in track_point.entity_identifier
        assert track_point.raw_score is not None
        assert track_point.raw_score > 0

    async def test_audio_features_key_present(self, scraper):
        """Audio features key exists in signals (empty until Extended Quota granted)."""
        scraper.access_token = "mock_token"

        async def mock_request(method, url, **kwargs):
            if "playlists" in url and "tracks" in url:
                return _mock_response(200, MOCK_PLAYLIST_RESPONSE)
            elif "audio-features" in url:
                return _mock_response(200, MOCK_AUDIO_FEATURES_RESPONSE)
            elif "artists" in url and "?" in url:
                return _mock_response(200, MOCK_ARTISTS_RESPONSE)
            return _mock_response(200, {})

        scraper.client.request = AsyncMock(side_effect=mock_request)
        scraper.TRENDING_PLAYLISTS = {"test_playlist_id": "Test Playlist"}

        points = await scraper.collect_trending()
        track_point = next(p for p in points if p.entity_identifier.get("spotify_id") == "track_001")

        # audio_features key is present (empty dict until Extended Quota is granted)
        assert "audio_features" in track_point.signals

    async def test_spotify_genres_in_signals(self, scraper):
        """Artist genres from Spotify are included in track signals for classifier."""
        scraper.access_token = "mock_token"

        async def mock_request(method, url, **kwargs):
            if "playlists" in url and "tracks" in url:
                return _mock_response(200, MOCK_PLAYLIST_RESPONSE)
            elif "audio-features" in url:
                return _mock_response(200, MOCK_AUDIO_FEATURES_RESPONSE)
            elif "artists" in url and "?" in url:
                return _mock_response(200, MOCK_ARTISTS_RESPONSE)
            return _mock_response(200, {})

        scraper.client.request = AsyncMock(side_effect=mock_request)
        scraper.TRENDING_PLAYLISTS = {"test_playlist_id": "Test Playlist"}

        points = await scraper.collect_trending()
        track_point = next(p for p in points if p.entity_identifier.get("spotify_id") == "track_001")

        assert "spotify_genres" in track_point.signals
        assert "pop" in track_point.signals["spotify_genres"]


class TestPostToApi:
    async def test_post_success(self, scraper):
        """Successful POST returns 'created'."""
        scraper.client.post = AsyncMock(return_value=_mock_response(201))
        point = RawDataPoint(
            platform="spotify", entity_type="track",
            entity_identifier={"spotify_id": "abc"}, snapshot_date=date.today()
        )
        result = await scraper._post_to_api(point)
        assert result == "created"

    async def test_post_duplicate(self, scraper):
        """409 response returns 'duplicate'."""
        scraper.client.post = AsyncMock(return_value=_mock_response(409))
        point = RawDataPoint(
            platform="spotify", entity_type="track",
            entity_identifier={"spotify_id": "abc"}, snapshot_date=date.today()
        )
        result = await scraper._post_to_api(point)
        assert result == "duplicate"

    async def test_post_rate_limited_then_success(self, scraper):
        """429 then 201 succeeds after retry."""
        scraper.client.post = AsyncMock(side_effect=[
            _mock_response(429, headers={"Retry-After": "1"}),
            _mock_response(201),
        ])
        point = RawDataPoint(
            platform="spotify", entity_type="track",
            entity_identifier={"spotify_id": "abc"}, snapshot_date=date.today()
        )
        result = await scraper._post_to_api(point)
        assert result == "created"
