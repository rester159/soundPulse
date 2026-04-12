"""
Artist assignment engine (§22 of PRD v3).

Given a song blueprint and the current AI artist roster, score each
artist as a potential target for this song and either recommend reusing
the best-scoring artist above a configurable threshold, or recommend
creating a new artist.

The engine is pure Python (no DB, no LLM). Callers pass plain dicts.
Persistence, CEO gate delivery, and the create-new artist pipeline all
live in separate modules and use this engine's `AssignmentDecision`
output as their input.

10 scoring dimensions are specified in PRD §22. This first slice ships
4 of them live (genre_match, voice_fit, lyrical_fit, audience_fit) and
stubs the other 6 with neutral 0.5 values — explicitly labeled as stubs
so nothing silently looks complete.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Per-dimension scorers — each returns a float in [0, 1]
# ---------------------------------------------------------------------------

def _as_set(value: Any) -> set[str]:
    if not value:
        return set()
    if isinstance(value, (list, tuple, set)):
        return {str(v).strip().lower() for v in value if v}
    return {str(value).strip().lower()}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 0.0
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


def _genre_tokens(genre: str) -> set[str]:
    """Split a genre id into its word tokens (separators: '.' and '-')."""
    if not genre:
        return set()
    out: set[str] = set()
    for part in genre.replace(".", " ").replace("-", " ").split():
        t = part.strip().lower()
        if t:
            out.add(t)
    return out


def score_genre_match(blueprint: dict, artist: dict) -> float:
    """
    Compare primary + adjacent genres.

    Tiers:
      1.0   exact primary match (e.g. pop.chill-pop == pop.chill-pop)
      0.5 + adjacency-bonus — shared genre tokens (e.g. pop.chill-pop vs indie-pop both have "pop")
      0.0 + adjacency-bonus — no shared tokens

    Adjacency bonus is a stretched Jaccard over the combined adjacency
    sets, capped so a different primary genre can never hit 1.0.
    """
    bp_primary = str(blueprint.get("primary_genre", "")).strip().lower()
    ar_primary = str(artist.get("primary_genre", "")).strip().lower()

    if bp_primary and bp_primary == ar_primary:
        return 1.0

    bp_tokens = _genre_tokens(bp_primary)
    ar_tokens = _genre_tokens(ar_primary)
    shared_tokens = bp_tokens & ar_tokens

    base = 0.5 if shared_tokens else 0.0

    bp_adj = _as_set(blueprint.get("adjacent_genres"))
    if bp_primary:
        bp_adj.add(bp_primary)
    ar_adj = _as_set(artist.get("adjacent_genres"))
    if ar_primary:
        ar_adj.add(ar_primary)
    adjacency = _jaccard(bp_adj, ar_adj)

    # Cap below 1.0 so non-exact matches can never ceiling.
    return min(0.95, base + 0.35 * adjacency)


def _voice_tokens(voice: dict | None) -> set[str]:
    """Flatten a voice_dna-like dict into a searchable token bag."""
    if not voice:
        return set()
    parts: list[str] = []
    for key in ("timbre_core", "timbre", "brightness", "delivery", "accent_pronunciation"):
        val = voice.get(key)
        if isinstance(val, str):
            parts.extend(val.lower().split())
    for key in ("delivery_style", "delivery"):
        val = voice.get(key)
        if isinstance(val, list):
            for v in val:
                parts.extend(str(v).lower().split())
    return {p.strip(",.") for p in parts if len(p) > 2}


def score_voice_fit(blueprint: dict, artist: dict) -> float:
    """
    Compare blueprint voice requirements against artist voice_dna.
    Blueprints without any voice requirement return a neutral 0.5 — we
    don't penalize an artist for a dimension the blueprint doesn't care
    about.
    """
    bp_voice = blueprint.get("voice_requirements")
    ar_voice = artist.get("voice_dna")
    if not bp_voice:
        return 0.5
    if not ar_voice:
        return 0.3  # blueprint wants voice match but artist has no voice DNA

    bp_tokens = _voice_tokens(bp_voice)
    ar_tokens = _voice_tokens(ar_voice)
    if not bp_tokens or not ar_tokens:
        return 0.5

    overlap = _jaccard(bp_tokens, ar_tokens)
    # Jaccard on small token bags is pessimistic; stretch it so a decent
    # overlap lands in the 0.7-0.9 band.
    return min(1.0, overlap * 2.5)


def score_lyrical_fit(blueprint: dict, artist: dict) -> float:
    """Compare blueprint target themes + tone against artist lyrical_dna."""
    bp_themes = _as_set(blueprint.get("target_themes"))
    bp_tone = str(blueprint.get("vocabulary_tone", "")).strip().lower()

    lyrical_dna = artist.get("lyrical_dna") or {}
    ar_themes = _as_set(lyrical_dna.get("recurring_themes"))
    ar_tone = str(lyrical_dna.get("vocab_level", "")).strip().lower()

    if not bp_themes and not bp_tone:
        return 0.5

    theme_score = _jaccard(bp_themes, ar_themes) if bp_themes else 0.5
    tone_score = 1.0 if (bp_tone and bp_tone == ar_tone) else (0.5 if not bp_tone else 0.2)

    # Theme overlap dominates; tone is a tiebreaker.
    return min(1.0, 0.75 * min(1.0, theme_score * 1.3) + 0.25 * tone_score)


def score_audience_fit(blueprint: dict, artist: dict) -> float:
    """Compare blueprint target audience tags against the artist's audience."""
    bp_aud = _as_set(blueprint.get("target_audience_tags"))
    ar_aud = _as_set(artist.get("audience_tags"))
    if not bp_aud:
        return 0.5
    if not ar_aud:
        return 0.4
    return _jaccard(bp_aud, ar_aud)


# Stubs for the remaining 6 dimensions. Explicitly labeled — they return
# 0.5 (neutral) and a comment so the reader knows they aren't implemented.
def score_release_cadence_fit(blueprint: dict, artist: dict) -> float:
    """STUB: needs song_count + last_released_at with a cooldown check."""
    return 0.5


def score_momentum_fit(blueprint: dict, artist: dict) -> float:
    """STUB: needs artist_performance_state aggregated from revenue_events."""
    return 0.5


def score_visual_brand_fit(blueprint: dict, artist: dict) -> float:
    """STUB: needs visual_dna + blueprint visual descriptors."""
    return 0.5


def score_cannibalization_risk(blueprint: dict, artist: dict) -> float:
    """STUB: needs DSP algorithmic-placement model."""
    return 0.5


def score_brand_stretch_risk(blueprint: dict, artist: dict) -> float:
    """STUB: needs brand-drift distance metric."""
    return 0.5


def score_strategic_diversification(blueprint: dict, artist: dict) -> float:
    """STUB: needs portfolio-level roster analysis."""
    return 0.5


# ---------------------------------------------------------------------------
# Decision engine
# ---------------------------------------------------------------------------

@dataclass
class AssignmentDecision:
    proposal: str                                   # "reuse" | "create_new"
    proposed_artist_id: str | None
    scores: dict[str, float]                        # artist_id → composite reuse_score
    breakdown: dict[str, dict[str, float]]          # artist_id → per-dimension scores
    threshold: float
    reason: str = ""                                # human-readable rationale


# Weights derived from PRD §22, normalized over the 4 live dimensions +
# 6 stubs. The live dims carry ~64% of the weight; stubs carry ~36% at
# neutral 0.5 each so their impact is identical across artists and the
# relative ranking is entirely driven by the live dimensions.
_DIMENSIONS = [
    ("genre_match",               0.22, score_genre_match),
    ("voice_fit",                 0.18, score_voice_fit),
    ("lyrical_fit",               0.12, score_lyrical_fit),
    ("audience_fit",              0.12, score_audience_fit),
    ("release_cadence_fit",       0.08, score_release_cadence_fit),
    ("momentum_fit",              0.08, score_momentum_fit),
    ("visual_brand_fit",          0.05, score_visual_brand_fit),
    ("cannibalization_risk",      0.05, score_cannibalization_risk),
    ("brand_stretch_risk",        0.05, score_brand_stretch_risk),
    ("strategic_diversification", 0.05, score_strategic_diversification),
]

# Sanity check that weights sum to 1 (catches future edits that forget).
assert abs(sum(w for _, w, _ in _DIMENSIONS) - 1.0) < 1e-6, "dimension weights must sum to 1"


@dataclass
class AssignmentEngine:
    reuse_threshold: float = 0.68

    def decide(self, *, blueprint: dict, roster: list[dict]) -> AssignmentDecision:
        if not roster:
            return AssignmentDecision(
                proposal="create_new",
                proposed_artist_id=None,
                scores={},
                breakdown={},
                threshold=self.reuse_threshold,
                reason="roster is empty",
            )

        scores: dict[str, float] = {}
        breakdown: dict[str, dict[str, float]] = {}

        for artist in roster:
            artist_id = str(artist.get("artist_id") or artist.get("id") or "?")
            per_dim: dict[str, float] = {}
            composite = 0.0
            for name, weight, scorer in _DIMENSIONS:
                value = float(scorer(blueprint, artist))
                per_dim[name] = value
                composite += weight * value
            scores[artist_id] = round(composite, 4)
            breakdown[artist_id] = per_dim

        best_id = max(scores, key=lambda k: scores[k])
        best_score = scores[best_id]

        if best_score >= self.reuse_threshold:
            return AssignmentDecision(
                proposal="reuse",
                proposed_artist_id=best_id,
                scores=scores,
                breakdown=breakdown,
                threshold=self.reuse_threshold,
                reason=f"{best_id} scored {best_score:.3f} ≥ threshold {self.reuse_threshold}",
            )

        return AssignmentDecision(
            proposal="create_new",
            proposed_artist_id=None,
            scores=scores,
            breakdown=breakdown,
            threshold=self.reuse_threshold,
            reason=f"best score {best_score:.3f} below threshold {self.reuse_threshold}",
        )
