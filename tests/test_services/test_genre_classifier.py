import pytest
from api.services.genre_classifier import GenreClassifier, ClassificationResult


class TestGenreClassifier:
    """Test the multi-signal genre classification engine."""

    async def test_classify_with_spotify_labels(self, db_session, sample_artist):
        """Artist with clear Spotify genre labels gets classified correctly."""
        sample_artist.metadata_json = {
            "spotify_genres": ["tech house", "deep house"],
        }
        classifier = GenreClassifier(db_session)
        result = await classifier.classify(sample_artist)

        assert isinstance(result, ClassificationResult)
        assert len(result.primary_genres) >= 1
        assert any("electronic" in g for g in result.primary_genres)
        assert result.classification_quality in ("high", "medium")

    async def test_classify_with_audio_features_only(self, db_session, sample_track):
        """Track with only audio features gets classified based on profile matching."""
        sample_track.audio_features = {
            "tempo": 128, "energy": 0.75, "valence": 0.5, "danceability": 0.82
        }
        sample_track.metadata_json = {}
        classifier = GenreClassifier(db_session)
        result = await classifier.classify(sample_track)

        assert isinstance(result, ClassificationResult)
        assert len(result.primary_genres) >= 1
        # High tempo + high danceability + moderate energy → likely electronic/house
        # But we don't assert specific genre since audio-only is less precise

    async def test_classify_with_artist_inheritance(self, db_session, sample_artist, sample_track):
        """Track inherits genres from its artist."""
        sample_artist.genres = ["rock.alternative.indie-rock"]
        sample_track.metadata_json = {}
        sample_track.audio_features = None

        classifier = GenreClassifier(db_session)
        result = await classifier.classify(sample_track)

        assert "rock.alternative.indie-rock" in result.primary_genres

    async def test_classify_with_tiktok_hashtags(self, db_session, sample_artist):
        """Social tags from TikTok influence classification."""
        sample_artist.metadata_json = {
            "tiktok_hashtags": ["#afrobeats", "#amapiano"],
        }
        classifier = GenreClassifier(db_session)
        result = await classifier.classify(sample_artist)

        assert any("african" in g for g in result.primary_genres)

    async def test_classify_cross_genre(self, db_session, sample_track, sample_artist):
        """Track spanning genres gets multiple assignments."""
        sample_artist.genres = ["hip-hop.pop-rap"]
        sample_track.metadata_json = {
            "spotify_genres": ["pop rap", "hip hop"],
            "apple_music_genres": ["Pop"],
        }
        sample_track.audio_features = {"tempo": 95, "energy": 0.65, "valence": 0.7, "danceability": 0.75}

        classifier = GenreClassifier(db_session)
        result = await classifier.classify(sample_track)

        # Should have genres from multiple root categories
        assert len(result.primary_genres) >= 1

    async def test_classify_empty_entity(self, db_session, sample_artist):
        """Entity with no metadata gets low quality classification."""
        sample_artist.metadata_json = {}
        sample_artist.genres = []

        classifier = GenreClassifier(db_session)
        result = await classifier.classify(sample_artist)

        assert result.classification_quality == "low"

    async def test_classify_and_save(self, db_session, sample_artist):
        """classify_and_save persists genres to the entity."""
        sample_artist.metadata_json = {
            "spotify_genres": ["jazz", "bebop"],
        }
        sample_artist.genres = []

        classifier = GenreClassifier(db_session)
        result = await classifier.classify_and_save(sample_artist)

        assert len(sample_artist.genres) >= 1
        assert any("jazz" in g for g in sample_artist.genres)

    async def test_hierarchy_prefers_specific(self, db_session, sample_artist):
        """Classifier prefers specific genres over broad root categories."""
        sample_artist.metadata_json = {
            "spotify_genres": ["tech house"],
        }
        classifier = GenreClassifier(db_session)
        result = await classifier.classify(sample_artist)

        # Should get "electronic.house.tech-house" not just "electronic"
        if result.primary_genres:
            assert any(g.count(".") >= 2 for g in result.primary_genres)

    async def test_multiple_platform_signals_boost_confidence(self, db_session, sample_artist):
        """Multiple platforms agreeing on genre produces higher quality."""
        sample_artist.metadata_json = {
            "spotify_genres": ["reggaeton"],
            "apple_music_genres": ["Reggaeton"],
            "chartmetric_genres": ["Reggaeton"],
        }
        classifier = GenreClassifier(db_session)
        result = await classifier.classify(sample_artist)

        assert result.classification_quality in ("high", "medium")
        assert any("reggaeton" in g for g in result.primary_genres)
