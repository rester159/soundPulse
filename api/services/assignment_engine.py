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


# ---------------------------------------------------------------------------
# Dimensions 5-10 — shipped as live scorers (previously stubs).
# Each returns [0, 1]. The heuristics are deliberately simple; the
# model will learn better weights when the ML hit predictor trains on
# resolved outcomes (§10 Layer 6).
# ---------------------------------------------------------------------------

# Minimum days between releases per PRD §22 cooldown rule. An artist
# who just dropped should not take a second blueprint back-to-back.
RELEASE_COOLDOWN_DAYS = 21


def score_release_cadence_fit(blueprint: dict, artist: dict) -> float:
    """
    Cooldown check: penalize reuse if the artist just released.
    1.0 if never released or > 60 days since last.
    0.9 between 30-60 days.
    0.6 between 21-30 days.
    0.2 within 21-day cooldown.
    """
    import datetime as _dt
    last = artist.get("last_released_at")
    if last is None:
        return 1.0
    try:
        if isinstance(last, str):
            last_dt = _dt.datetime.fromisoformat(last.replace("Z", "+00:00"))
        else:
            last_dt = last
        now = _dt.datetime.now(last_dt.tzinfo or _dt.timezone.utc)
        days = (now - last_dt).days
    except Exception:
        return 0.5

    if days >= 60:
        return 1.0
    if days >= 30:
        return 0.9
    if days >= RELEASE_COOLDOWN_DAYS:
        return 0.6
    return 0.2


def score_momentum_fit(blueprint: dict, artist: dict) -> float:
    """
    Momentum fit: reward high-momentum artists for high-opportunity
    blueprints (you want your rising star to catch waves), penalize
    pairing a cold artist with a hot opportunity you should give to
    someone who can actually ride it.

    Uses artist['momentum_score'] if the orchestrator projected one
    (from artist_performance_state), otherwise falls back to song_count
    as a rough recency proxy. Blueprint['opportunity_score'] is passed
    from §11 quantification.
    """
    artist_momentum = float(artist.get("momentum_score") or 0)
    if artist_momentum <= 0:
        # Fallback: song_count-as-proxy. New artist (0 songs) is assumed
        # to need a boost; artist with 5+ songs gets momentum credit.
        sc = int(artist.get("song_count") or 0)
        if sc == 0:
            artist_momentum = 0.5
        elif sc <= 2:
            artist_momentum = 0.55
        elif sc <= 5:
            artist_momentum = 0.7
        else:
            artist_momentum = 0.85

    bp_opp = float(blueprint.get("opportunity_score") or 0.5)
    # Close-matching momentum to opportunity rewards pairing; mismatch
    # penalizes. Abs difference in [0,1] → 1 - diff = score.
    diff = abs(artist_momentum - bp_opp)
    return max(0.0, min(1.0, 1.0 - diff))


def _visual_tokens(visual: dict | None) -> set[str]:
    """Flatten a visual_dna dict into a searchable token bag."""
    if not visual:
        return set()
    parts: list[str] = []
    for key in (
        "face_description", "body_presentation", "hair_signature",
        "fashion_style_summary", "art_direction",
    ):
        val = visual.get(key)
        if isinstance(val, str):
            parts.extend(val.lower().split())
    return {p.strip(",.") for p in parts if len(p) > 3}


def score_visual_brand_fit(blueprint: dict, artist: dict) -> float:
    """
    Compare blueprint's visual descriptors against artist visual_dna.
    Blueprints that don't specify visuals get a neutral 0.6 (slight
    reuse preference so we're not blocked on visual data).
    """
    bp_visual = blueprint.get("visual_requirements")
    ar_visual = artist.get("visual_dna")
    if not bp_visual:
        return 0.6  # slight reuse preference — no blueprint visual spec
    if not ar_visual:
        return 0.4
    bp_tokens = _visual_tokens(bp_visual)
    ar_tokens = _visual_tokens(ar_visual)
    if not bp_tokens or not ar_tokens:
        return 0.5
    overlap = _jaccard(bp_tokens, ar_tokens)
    # Stretched Jaccard, same logic as voice_fit — small token bags are
    # pessimistic under raw Jaccard.
    return min(1.0, overlap * 2.5)


def score_cannibalization_risk(blueprint: dict, artist: dict) -> float:
    """
    Risk of the new song cannibalizing the artist's recent releases.
    Returns HIGH value (less risk) for artists who haven't released
    recently OR whose recent songs cover different sonic zones.

    Heuristic: if song_count == 0, no risk (1.0). Otherwise penalty
    scales with how many songs exist (~5+ songs = saturated catalog =
    moderate risk). ML layer 6 will learn this properly from
    resolved stream outcomes.
    """
    sc = int(artist.get("song_count") or 0)
    if sc == 0:
        return 1.0
    if sc <= 2:
        return 0.9
    if sc <= 5:
        return 0.75
    if sc <= 10:
        return 0.55
    return 0.4  # heavy catalog, real cannibalization risk


def score_brand_stretch_risk(blueprint: dict, artist: dict) -> float:
    """
    How far does this blueprint stretch the artist's brand?
    1.0 = exact genre match (no stretch)
    0.7 = adjacent genre within the artist's known palette
    0.3 = totally different primary genre (brand drift)

    Reuses _genre_tokens + adjacent_genres lookups.
    """
    bp_primary = str(blueprint.get("primary_genre", "")).strip().lower()
    ar_primary = str(artist.get("primary_genre", "")).strip().lower()
    if not bp_primary or not ar_primary:
        return 0.5

    if bp_primary == ar_primary:
        return 1.0

    bp_tokens = _genre_tokens(bp_primary)
    ar_tokens = _genre_tokens(ar_primary)
    shared = bp_tokens & ar_tokens
    if shared:
        # Top-level token match (e.g. pop.k-pop vs pop.chill-pop)
        return 0.7

    ar_adj = _as_set(artist.get("adjacent_genres"))
    if bp_primary in ar_adj:
        return 0.6

    return 0.3  # real brand drift


def score_strategic_diversification(blueprint: dict, artist: dict) -> float:
    """
    Reward giving songs to UNDERUSED artists in the roster so we don't
    pile every release on the top 2-3 performers and starve the rest.

    Heuristic: an artist with song_count < roster_median_song_count gets
    a diversification boost; above-median artists get a penalty. If the
    blueprint supplies roster_median_song_count, we use it; otherwise
    neutral 0.5.
    """
    median = blueprint.get("roster_median_song_count")
    if median is None:
        return 0.5
    sc = int(artist.get("song_count") or 0)
    try:
        median_f = float(median)
    except Exception:
        return 0.5
    if sc < median_f:
        return 0.85  # underused → boost
    if sc == median_f:
        return 0.65
    return 0.4  # already over-represented in the roster


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
