"""
Unit tests for the artist assignment engine (§22 of PRD v3).

Every new song blueprint asks: reuse an existing AI artist or create a
new one? The engine scores every existing artist against the blueprint
across 10 dimensions. This test file covers the 4 dimensions shipped in
the first slice — genre_match, voice_fit, lyrical_fit, audience_fit —
plus the top-level decision logic.

The service is pure Python (no DB, no LLM), tested in isolation with
dict-shaped blueprints and artists.
"""
from __future__ import annotations

import pytest

from api.services.assignment_engine import (
    AssignmentDecision,
    AssignmentEngine,
    score_audience_fit,
    score_genre_match,
    score_lyrical_fit,
    score_voice_fit,
)


# --- Fixtures ---------------------------------------------------------------

@pytest.fixture
def pop_blueprint() -> dict:
    return {
        "id": "bp-001",
        "primary_genre": "pop.chill-pop",
        "adjacent_genres": ["pop", "indie-pop"],
        "target_themes": ["midnight drives", "neon", "longing"],
        "vocabulary_tone": "conversational",
        "target_audience_tags": ["gen_z", "urban", "female_lean"],
        "voice_requirements": {
            "timbre": "soft warm female tenor",
            "delivery": ["half-sung", "whispered"],
            "autotune": "light",
        },
    }


@pytest.fixture
def matching_chill_pop_artist() -> dict:
    return {
        "artist_id": "ar-001",
        "stage_name": "Nova Rain",
        "primary_genre": "pop.chill-pop",
        "adjacent_genres": ["pop", "bedroom-pop"],
        "voice_dna": {
            "timbre_core": "warm breathy female tenor",
            "delivery_style": ["half-sung", "whispered doubles"],
            "autotune_profile": "light pitch correction",
        },
        "lyrical_dna": {
            "recurring_themes": ["longing", "midnight drives", "neon"],
            "vocab_level": "conversational",
        },
        "audience_tags": ["gen_z", "urban", "female_lean"],
        "song_count": 4,
    }


@pytest.fixture
def mismatched_country_artist() -> dict:
    return {
        "artist_id": "ar-002",
        "stage_name": "Wyatt Hollow",
        "primary_genre": "country.outlaw",
        "adjacent_genres": ["americana", "folk"],
        "voice_dna": {
            "timbre_core": "gravelly baritone",
            "delivery_style": ["full-voice belt"],
            "autotune_profile": "none",
        },
        "lyrical_dna": {
            "recurring_themes": ["heartache", "whiskey", "highway"],
            "vocab_level": "conversational",
        },
        "audience_tags": ["millennial", "rural", "male_lean"],
        "song_count": 12,
    }


# --- Per-dimension scoring --------------------------------------------------

class TestGenreMatch:
    def test_exact_primary_genre_scores_max(self, pop_blueprint, matching_chill_pop_artist):
        assert score_genre_match(pop_blueprint, matching_chill_pop_artist) == pytest.approx(1.0)

    def test_wildly_different_genre_scores_near_zero(self, pop_blueprint, mismatched_country_artist):
        assert score_genre_match(pop_blueprint, mismatched_country_artist) < 0.25

    def test_adjacent_overlap_scores_medium(self, pop_blueprint):
        adjacent_artist = {
            "primary_genre": "indie-pop",
            "adjacent_genres": ["pop", "dream-pop"],
        }
        score = score_genre_match(pop_blueprint, adjacent_artist)
        assert 0.4 < score < 0.9


class TestVoiceFit:
    def test_matching_timbre_and_delivery_scores_high(self, pop_blueprint, matching_chill_pop_artist):
        assert score_voice_fit(pop_blueprint, matching_chill_pop_artist) >= 0.7

    def test_opposite_voice_scores_low(self, pop_blueprint, mismatched_country_artist):
        assert score_voice_fit(pop_blueprint, mismatched_country_artist) < 0.3

    def test_blueprint_without_voice_requirements_returns_neutral(self, matching_chill_pop_artist):
        neutral_bp = {"id": "bp-x", "primary_genre": "pop"}
        score = score_voice_fit(neutral_bp, matching_chill_pop_artist)
        assert 0.4 <= score <= 0.6


class TestLyricalFit:
    def test_full_theme_overlap_scores_max(self, pop_blueprint, matching_chill_pop_artist):
        assert score_lyrical_fit(pop_blueprint, matching_chill_pop_artist) >= 0.8

    def test_no_theme_overlap_scores_low(self, pop_blueprint, mismatched_country_artist):
        assert score_lyrical_fit(pop_blueprint, mismatched_country_artist) < 0.3


class TestAudienceFit:
    def test_matching_audience_tags_score_high(self, pop_blueprint, matching_chill_pop_artist):
        assert score_audience_fit(pop_blueprint, matching_chill_pop_artist) >= 0.9

    def test_opposite_audience_scores_low(self, pop_blueprint, mismatched_country_artist):
        assert score_audience_fit(pop_blueprint, mismatched_country_artist) < 0.3


# --- Decision engine end-to-end --------------------------------------------

class TestAssignmentEngine:
    def test_recommends_reuse_when_strong_match_exists(
        self, pop_blueprint, matching_chill_pop_artist, mismatched_country_artist
    ):
        engine = AssignmentEngine(reuse_threshold=0.68)
        decision = engine.decide(
            blueprint=pop_blueprint,
            roster=[matching_chill_pop_artist, mismatched_country_artist],
        )
        assert isinstance(decision, AssignmentDecision)
        assert decision.proposal == "reuse"
        assert decision.proposed_artist_id == "ar-001"
        # The matching artist should clearly beat the mismatched one
        assert decision.scores["ar-001"] > decision.scores["ar-002"]
        # And should clear the reuse threshold
        assert decision.scores["ar-001"] >= 0.68

    def test_recommends_create_new_when_no_match_is_strong_enough(
        self, pop_blueprint, mismatched_country_artist
    ):
        engine = AssignmentEngine(reuse_threshold=0.68)
        decision = engine.decide(
            blueprint=pop_blueprint,
            roster=[mismatched_country_artist],
        )
        assert decision.proposal == "create_new"
        assert decision.proposed_artist_id is None
        # The best score should still be recorded for auditability
        assert "ar-002" in decision.scores
        assert decision.scores["ar-002"] < 0.68

    def test_empty_roster_always_creates_new(self, pop_blueprint):
        engine = AssignmentEngine()
        decision = engine.decide(blueprint=pop_blueprint, roster=[])
        assert decision.proposal == "create_new"
        assert decision.scores == {}

    def test_decision_includes_per_dimension_breakdown(
        self, pop_blueprint, matching_chill_pop_artist
    ):
        engine = AssignmentEngine()
        decision = engine.decide(
            blueprint=pop_blueprint,
            roster=[matching_chill_pop_artist],
        )
        breakdown = decision.breakdown["ar-001"]
        # All 4 live dimensions must be present
        for key in ("genre_match", "voice_fit", "lyrical_fit", "audience_fit"):
            assert key in breakdown
            assert 0.0 <= breakdown[key] <= 1.0

    def test_custom_threshold_overrides_default(
        self, pop_blueprint, matching_chill_pop_artist
    ):
        # With a very strict threshold, even the strong match should fail
        engine = AssignmentEngine(reuse_threshold=0.999)
        decision = engine.decide(
            blueprint=pop_blueprint,
            roster=[matching_chill_pop_artist],
        )
        assert decision.proposal == "create_new"
