"""Advanced feature engineering pipeline for the SoundPulse prediction engine.

Computes ~70 features organized into categories:
  - Momentum: velocity, acceleration, jerk over multiple windows
  - Cross-platform: platform counts, agreement scores, ratios
  - Audio: tempo, energy, valence, danceability from metadata
  - Genre: genre momentum, saturation, diversity
  - Temporal: day-of-week, days since release, seasonality
  - Social: TikTok signals, playlist counts
  - Historical: peak rank, volatility, comebacks
  - Competitive: genre saturation in trending pool

All features are computed from DB data and returned as a flat dict
suitable for model consumption.
"""

import logging
import math
import uuid
from datetime import date, timedelta
from statistics import mean, stdev

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.artist import Artist
from api.models.genre import Genre
from api.models.track import Track
from api.models.trending_snapshot import TrendingSnapshot
from shared.constants import PLATFORM_WEIGHTS, VALID_PLATFORMS

logger = logging.getLogger(__name__)

# Minimum snapshot days to compute any features.
MIN_HISTORY_DAYS = 3

# Platforms used for per-platform feature expansion.
PLATFORMS = list(PLATFORM_WEIGHTS.keys())

# Ordered list of all feature names produced by this module.
# Updated dynamically at module load via _build_feature_names().
FEATURE_NAMES: list[str] = []


def _build_feature_names() -> list[str]:
    """Build the canonical ordered list of feature names."""
    names: list[str] = []

    # Group 1: Per-platform momentum (7 platforms x 5 = 35)
    for p in PLATFORMS:
        names.append(f"{p}_score_7d_avg")
        names.append(f"{p}_velocity_7d")
        names.append(f"{p}_acceleration")
        names.append(f"{p}_score_vs_30d_avg")
        names.append(f"{p}_rank_change_7d")

    # Group 2: Cross-platform (10)
    names.extend([
        "platform_count",
        "platform_score_variance",
        "shazam_to_spotify_ratio",
        "tiktok_to_spotify_ratio",
        "apple_to_spotify_ratio",
        "cross_platform_velocity_alignment",
        "max_platform_score",
        "min_platform_score",
        "platform_score_range",
        "weighted_platform_entropy",
    ])

    # Group 3: TikTok-specific (5)
    names.extend([
        "tiktok_creator_tier_migration_rate",
        "tiktok_geo_spread",
        "tiktok_video_count_velocity",
        "tiktok_macro_creator_adoption",
        "tiktok_avg_engagement_rate",
    ])

    # Group 4: Temporal (8)
    names.extend([
        "day_of_week",
        "days_since_release",
        "is_weekend",
        "is_holiday_period",
        "season_q1",
        "season_q2",
        "season_q3",
        "season_q4",
    ])

    # Group 5: Genre (7)
    names.extend([
        "genre_overall_momentum",
        "genre_new_entry_rate",
        "genre_trending_count",
        "artist_genre_rarity",
        "genre_depth",
        "genre_cross_branch_momentum",
        "genre_saturation",
    ])

    # Group 6: Entity history (10)
    names.extend([
        "entity_age_days",
        "peak_composite_score_ever",
        "days_since_peak",
        "score_30d_trend",
        "previous_breakout_count",
        "avg_time_between_peaks",
        "current_streak_days",
        "rank_volatility",
        "fastest_rise_rate_ever",
        "recovery_rate",
    ])

    # Group 7: Audio features (4)
    names.extend([
        "audio_tempo",
        "audio_energy",
        "audio_valence",
        "audio_danceability",
    ])

    return names


FEATURE_NAMES = _build_feature_names()


def _safe_div(a: float, b: float, default: float = 0.0) -> float:
    """Safe division returning *default* when divisor is zero."""
    if b == 0:
        return default
    return a / b


def _linear_slope(values: list[float]) -> float:
    """Simple linear regression slope over an evenly-spaced series."""
    n = len(values)
    if n < 2:
        return 0.0
    x_mean = (n - 1) / 2.0
    y_mean = mean(values)
    numerator = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(values))
    denominator = sum((i - x_mean) ** 2 for i in range(n))
    if denominator == 0:
        return 0.0
    return numerator / denominator


def _entropy(probs: list[float]) -> float:
    """Shannon entropy (nats) of a probability distribution."""
    return -sum(p * math.log(p + 1e-12) for p in probs if p > 0)


def _is_holiday_period(d: date) -> bool:
    """Rough check for major US/global music-release holiday windows."""
    md = (d.month, d.day)
    # Thanksgiving–New Year corridor, Valentine's, summer kickoff
    if d.month == 12 or (d.month == 11 and d.day >= 20):
        return True
    if d.month == 1 and d.day <= 5:
        return True
    if md == (2, 14):
        return True
    if d.month == 7 and d.day <= 7:  # July 4 weekend
        return True
    return False


# ── Main feature computation ─────────────────────────────────────────

async def compute_features(
    db: AsyncSession,
    entity_id: uuid.UUID,
    entity_type: str,
    as_of: date | None = None,
) -> dict[str, float] | None:
    """Compute the full ~70-feature vector for a single entity.

    Returns a dict keyed by feature name, or None when there is
    not enough history.
    """
    if as_of is None:
        as_of = date.today()

    # ── 1. Pull snapshots ────────────────────────────────────────
    result = await db.execute(
        select(TrendingSnapshot)
        .where(
            TrendingSnapshot.entity_id == entity_id,
            TrendingSnapshot.entity_type == entity_type,
            TrendingSnapshot.snapshot_date <= as_of,
        )
        .order_by(TrendingSnapshot.snapshot_date.asc())
    )
    snapshots = result.scalars().all()

    if not snapshots:
        return None

    # Group by date and by platform
    daily: dict[date, list[TrendingSnapshot]] = {}
    by_platform: dict[str, list[TrendingSnapshot]] = {p: [] for p in PLATFORMS}

    for snap in snapshots:
        daily.setdefault(snap.snapshot_date, []).append(snap)
        if snap.platform in by_platform:
            by_platform[snap.platform].append(snap)

    sorted_dates = sorted(daily.keys())
    if len(sorted_dates) < MIN_HISTORY_DAYS:
        return None

    # ── 2. Daily aggregates ──────────────────────────────────────
    daily_best_ranks: list[int] = []
    daily_composites: list[float] = []

    for d in sorted_dates:
        day_snaps = daily[d]
        ranks = [s.platform_rank for s in day_snaps if s.platform_rank is not None]
        composites = [s.composite_score for s in day_snaps if s.composite_score is not None]
        daily_best_ranks.append(min(ranks) if ranks else 999)
        daily_composites.append(max(composites) if composites else 0.0)

    features: dict[str, float] = {}

    # ── 3. Per-platform momentum features (Group 1) ──────────────
    latest_platform_scores: dict[str, float] = {}

    for platform in PLATFORMS:
        p_snaps = by_platform[platform]
        if not p_snaps:
            features[f"{platform}_score_7d_avg"] = 0.0
            features[f"{platform}_velocity_7d"] = 0.0
            features[f"{platform}_acceleration"] = 0.0
            features[f"{platform}_score_vs_30d_avg"] = 0.0
            features[f"{platform}_rank_change_7d"] = 0.0
            continue

        # Sort by date
        p_snaps_sorted = sorted(p_snaps, key=lambda s: s.snapshot_date)

        # Scores by date
        p_scores = [s.normalized_score for s in p_snaps_sorted]
        p_ranks = [s.platform_rank for s in p_snaps_sorted if s.platform_rank is not None]

        # 7d avg
        recent_7 = p_scores[-7:]
        score_7d_avg = mean(recent_7) if recent_7 else 0.0
        features[f"{platform}_score_7d_avg"] = round(score_7d_avg, 4)

        # Store latest for cross-platform
        latest_platform_scores[platform] = p_scores[-1] if p_scores else 0.0

        # Velocity: linear slope of last 7 scores
        velocity_7d = _linear_slope(recent_7)
        features[f"{platform}_velocity_7d"] = round(velocity_7d, 4)

        # Acceleration: slope of velocities (use 3-day windows)
        if len(p_scores) >= 10:
            vel_early = _linear_slope(p_scores[-10:-5])
            vel_late = _linear_slope(p_scores[-5:])
            accel = vel_late - vel_early
        elif len(p_scores) >= 4:
            mid = len(p_scores) // 2
            vel_early = _linear_slope(p_scores[:mid])
            vel_late = _linear_slope(p_scores[mid:])
            accel = vel_late - vel_early
        else:
            accel = 0.0
        features[f"{platform}_acceleration"] = round(accel, 4)

        # Score vs 30d avg
        recent_30 = p_scores[-30:]
        avg_30 = mean(recent_30) if recent_30 else 1.0
        features[f"{platform}_score_vs_30d_avg"] = round(
            _safe_div(score_7d_avg, avg_30, 1.0), 4
        )

        # Rank change 7d
        if len(p_ranks) >= 2:
            recent_ranks_7 = p_ranks[-7:]
            rank_change = recent_ranks_7[0] - recent_ranks_7[-1]  # positive = improving
        else:
            rank_change = 0
        features[f"{platform}_rank_change_7d"] = float(rank_change)

    # ── 4. Cross-platform features (Group 2) ─────────────────────
    latest_day_snaps = daily[sorted_dates[-1]]
    active_platforms = {s.platform for s in latest_day_snaps}
    platform_count = len(active_platforms)
    features["platform_count"] = float(platform_count)

    active_scores = [latest_platform_scores.get(p, 0.0) for p in active_platforms if latest_platform_scores.get(p, 0.0) > 0]
    if len(active_scores) >= 2:
        features["platform_score_variance"] = round(stdev(active_scores) ** 2, 4)
    else:
        features["platform_score_variance"] = 0.0

    spotify_score = latest_platform_scores.get("spotify", 0.0)
    shazam_score = latest_platform_scores.get("shazam", 0.0)
    tiktok_score = latest_platform_scores.get("tiktok", 0.0)
    apple_score = latest_platform_scores.get("apple_music", 0.0)

    features["shazam_to_spotify_ratio"] = round(_safe_div(shazam_score, spotify_score), 4)
    features["tiktok_to_spotify_ratio"] = round(_safe_div(tiktok_score, spotify_score), 4)
    features["apple_to_spotify_ratio"] = round(_safe_div(apple_score, spotify_score), 4)

    # Cross-platform velocity alignment: do all platforms trend the same direction?
    platform_velocities = []
    for p in PLATFORMS:
        v = features.get(f"{p}_velocity_7d", 0.0)
        if v != 0.0:
            platform_velocities.append(v)

    if len(platform_velocities) >= 2:
        signs = [1 if v > 0 else -1 for v in platform_velocities]
        alignment = abs(sum(signs)) / len(signs)  # 1.0 = all same direction
    else:
        alignment = 0.0
    features["cross_platform_velocity_alignment"] = round(alignment, 4)

    all_scores = list(latest_platform_scores.values())
    features["max_platform_score"] = round(max(all_scores) if all_scores else 0.0, 4)
    features["min_platform_score"] = round(min(all_scores) if all_scores else 0.0, 4)
    features["platform_score_range"] = round(
        (max(all_scores) - min(all_scores)) if all_scores else 0.0, 4
    )

    # Weighted platform entropy
    total_weighted = sum(
        latest_platform_scores.get(p, 0.0) * PLATFORM_WEIGHTS.get(p, 0.0)
        for p in PLATFORMS
    )
    if total_weighted > 0:
        probs = [
            (latest_platform_scores.get(p, 0.0) * PLATFORM_WEIGHTS.get(p, 0.0)) / total_weighted
            for p in PLATFORMS
        ]
        features["weighted_platform_entropy"] = round(_entropy(probs), 4)
    else:
        features["weighted_platform_entropy"] = 0.0

    # ── 5. TikTok-specific features (Group 3) ────────────────────
    # These are extracted from signals_json on TikTok snapshots
    tiktok_snaps = by_platform.get("tiktok", [])
    tiktok_snaps_sorted = sorted(tiktok_snaps, key=lambda s: s.snapshot_date)

    if tiktok_snaps_sorted:
        latest_tt = tiktok_snaps_sorted[-1]
        signals = latest_tt.signals_json or {}

        # Creator tier migration rate
        tier_dist = signals.get("creator_tier_distribution", {})
        macro_pct = tier_dist.get("macro", 0.0) + tier_dist.get("mega", 0.0)
        features["tiktok_macro_creator_adoption"] = round(macro_pct, 4)

        # Compare to earlier snapshot for migration rate
        if len(tiktok_snaps_sorted) >= 7:
            earlier_tt = tiktok_snaps_sorted[-7]
            earlier_signals = earlier_tt.signals_json or {}
            earlier_tier = earlier_signals.get("creator_tier_distribution", {})
            earlier_macro = earlier_tier.get("macro", 0.0) + earlier_tier.get("mega", 0.0)
            features["tiktok_creator_tier_migration_rate"] = round(macro_pct - earlier_macro, 4)
        else:
            features["tiktok_creator_tier_migration_rate"] = 0.0

        features["tiktok_geo_spread"] = float(signals.get("geo_spread", 0))

        # Video count velocity
        tt_video_counts = []
        for s in tiktok_snaps_sorted[-7:]:
            sj = s.signals_json or {}
            vc = sj.get("video_count_24h", 0)
            tt_video_counts.append(float(vc))
        features["tiktok_video_count_velocity"] = round(_linear_slope(tt_video_counts), 4)

        # Avg engagement rate
        eng_rates = []
        for s in tiktok_snaps_sorted[-7:]:
            sj = s.signals_json or {}
            er = sj.get("engagement_rate", 0.0)
            eng_rates.append(float(er))
        features["tiktok_avg_engagement_rate"] = round(mean(eng_rates) if eng_rates else 0.0, 4)
    else:
        features["tiktok_creator_tier_migration_rate"] = 0.0
        features["tiktok_geo_spread"] = 0.0
        features["tiktok_video_count_velocity"] = 0.0
        features["tiktok_macro_creator_adoption"] = 0.0
        features["tiktok_avg_engagement_rate"] = 0.0

    # ── 6. Temporal features (Group 4) ───────────────────────────
    features["day_of_week"] = float(as_of.weekday())  # 0=Monday
    features["is_weekend"] = 1.0 if as_of.weekday() >= 5 else 0.0
    features["is_holiday_period"] = 1.0 if _is_holiday_period(as_of) else 0.0

    # Season one-hot
    quarter = (as_of.month - 1) // 3 + 1
    features["season_q1"] = 1.0 if quarter == 1 else 0.0
    features["season_q2"] = 1.0 if quarter == 2 else 0.0
    features["season_q3"] = 1.0 if quarter == 3 else 0.0
    features["season_q4"] = 1.0 if quarter == 4 else 0.0

    # Days since release: look up entity metadata
    release_date = await _get_release_date(db, entity_id, entity_type)
    if release_date:
        features["days_since_release"] = float((as_of - release_date).days)
    else:
        features["days_since_release"] = -1.0  # sentinel for unknown

    # ── 7. Genre features (Group 5) ──────────────────────────────
    entity_genres = await _get_entity_genres(db, entity_id, entity_type)
    genre_feats = await _compute_genre_features(db, entity_genres, as_of)
    features.update(genre_feats)

    # ── 8. Entity history features (Group 6) ─────────────────────
    features["entity_age_days"] = float((sorted_dates[-1] - sorted_dates[0]).days)

    peak_composite = max(daily_composites) if daily_composites else 0.0
    features["peak_composite_score_ever"] = round(peak_composite, 4)

    # Days since peak
    if daily_composites:
        peak_idx = daily_composites.index(peak_composite)
        peak_date = sorted_dates[peak_idx]
        features["days_since_peak"] = float((as_of - peak_date).days)
    else:
        features["days_since_peak"] = 0.0

    # 30d trend: linear slope of last 30 composites
    recent_30_composites = daily_composites[-30:]
    features["score_30d_trend"] = round(_linear_slope(recent_30_composites), 4)

    # Previous breakout count (composite >= 80)
    breakout_threshold = 80.0
    breakout_count = sum(1 for c in daily_composites if c >= breakout_threshold)
    features["previous_breakout_count"] = float(breakout_count)

    # Avg time between peaks (local maxima above threshold)
    peak_dates = [
        sorted_dates[i]
        for i, c in enumerate(daily_composites)
        if c >= breakout_threshold
    ]
    if len(peak_dates) >= 2:
        gaps = [(peak_dates[i + 1] - peak_dates[i]).days for i in range(len(peak_dates) - 1)]
        features["avg_time_between_peaks"] = round(mean(gaps), 4)
    else:
        features["avg_time_between_peaks"] = 0.0

    # Current streak: consecutive days of positive velocity
    streak = 0
    for i in range(len(daily_composites) - 1, 0, -1):
        if daily_composites[i] > daily_composites[i - 1]:
            streak += 1
        else:
            break
    features["current_streak_days"] = float(streak)

    # Rank volatility
    recent_ranks = daily_best_ranks[-14:]
    if len(recent_ranks) >= 2:
        features["rank_volatility"] = round(stdev(recent_ranks), 4)
    else:
        features["rank_volatility"] = 0.0

    # Fastest rise rate ever (max single-day composite gain)
    if len(daily_composites) >= 2:
        daily_gains = [
            daily_composites[i] - daily_composites[i - 1]
            for i in range(1, len(daily_composites))
        ]
        features["fastest_rise_rate_ever"] = round(max(daily_gains), 4)
    else:
        features["fastest_rise_rate_ever"] = 0.0

    # Recovery rate: avg bounce-back after dips below moving average
    if len(daily_composites) >= 7:
        recovery_speeds: list[float] = []
        window = 7
        for i in range(window, len(daily_composites)):
            ma = mean(daily_composites[i - window : i])
            if daily_composites[i] < ma * 0.9:  # dip detected
                # Look for recovery in next 5 days
                for j in range(i + 1, min(i + 6, len(daily_composites))):
                    if daily_composites[j] >= ma:
                        recovery_speeds.append(1.0 / (j - i))
                        break
        features["recovery_rate"] = round(mean(recovery_speeds) if recovery_speeds else 0.0, 4)
    else:
        features["recovery_rate"] = 0.0

    # ── 9. Audio features (Group 7) ──────────────────────────────
    audio = await _get_audio_features(db, entity_id, entity_type)
    features["audio_tempo"] = audio.get("tempo", 0.0)
    features["audio_energy"] = audio.get("energy", 0.0)
    features["audio_valence"] = audio.get("valence", 0.0)
    features["audio_danceability"] = audio.get("danceability", 0.0)

    # Ensure all expected features are present with defaults
    for name in FEATURE_NAMES:
        if name not in features:
            features[name] = 0.0

    return features


# ── Helper: entity metadata lookups ─────────────────────────────────

async def _get_release_date(
    db: AsyncSession, entity_id: uuid.UUID, entity_type: str
) -> date | None:
    """Look up the release date for a track, or None for artists / missing data."""
    if entity_type != "track":
        return None
    result = await db.execute(select(Track.release_date).where(Track.id == entity_id))
    return result.scalar_one_or_none()


async def _get_entity_genres(
    db: AsyncSession, entity_id: uuid.UUID, entity_type: str
) -> list[str]:
    """Return the genre list for the entity."""
    if entity_type == "artist":
        result = await db.execute(select(Artist.genres).where(Artist.id == entity_id))
    elif entity_type == "track":
        result = await db.execute(select(Track.genres).where(Track.id == entity_id))
    else:
        return []
    genres = result.scalar_one_or_none()
    return genres or []


async def _get_audio_features(
    db: AsyncSession, entity_id: uuid.UUID, entity_type: str
) -> dict:
    """Extract audio features from track.audio_features or artist.metadata_json."""
    if entity_type == "track":
        result = await db.execute(
            select(Track.audio_features).where(Track.id == entity_id)
        )
        af = result.scalar_one_or_none()
        if af and isinstance(af, dict):
            return {
                "tempo": float(af.get("tempo", 0.0)),
                "energy": float(af.get("energy", 0.0)),
                "valence": float(af.get("valence", 0.0)),
                "danceability": float(af.get("danceability", 0.0)),
            }
    elif entity_type == "artist":
        result = await db.execute(
            select(Artist.metadata_json).where(Artist.id == entity_id)
        )
        md = result.scalar_one_or_none()
        if md and isinstance(md, dict):
            af = md.get("audio_features", md.get("audio_profile", {}))
            if af:
                return {
                    "tempo": float(af.get("tempo", 0.0)),
                    "energy": float(af.get("energy", 0.0)),
                    "valence": float(af.get("valence", 0.0)),
                    "danceability": float(af.get("danceability", 0.0)),
                }
    return {"tempo": 0.0, "energy": 0.0, "valence": 0.0, "danceability": 0.0}


async def _compute_genre_features(
    db: AsyncSession, entity_genres: list[str], as_of: date
) -> dict[str, float]:
    """Compute genre-level features based on entity's assigned genres."""
    defaults = {
        "genre_overall_momentum": 0.0,
        "genre_new_entry_rate": 0.0,
        "genre_trending_count": 0.0,
        "artist_genre_rarity": 0.0,
        "genre_depth": 0.0,
        "genre_cross_branch_momentum": 0.0,
        "genre_saturation": 0.0,
    }
    if not entity_genres:
        return defaults

    primary_genre = entity_genres[0]

    # Genre depth: count dots in genre ID
    defaults["genre_depth"] = float(primary_genre.count("."))

    # Genre rarity: 1 / number of entities sharing this genre in recent trending
    # Count how many distinct entities in trending_snapshots share any of our genres
    # in the last 7 days
    week_ago = as_of - timedelta(days=7)

    # Get all entities trending in last 7 days
    result = await db.execute(
        select(
            TrendingSnapshot.entity_id,
            TrendingSnapshot.entity_type,
        )
        .where(TrendingSnapshot.snapshot_date >= week_ago, TrendingSnapshot.snapshot_date <= as_of)
        .distinct()
    )
    trending_entities = result.all()
    total_trending = len(trending_entities)

    if total_trending == 0:
        return defaults

    defaults["genre_trending_count"] = float(total_trending)

    # Genre saturation: fraction of trending entities that share our genre
    # We need to check genres of trending entities. For efficiency, we'll
    # estimate based on root category.
    root_genre = primary_genre.split(".")[0] if "." in primary_genre else primary_genre

    # Count entities in same genre root among trending
    genre_match_count = 0
    entity_ids_by_type: dict[str, list[uuid.UUID]] = {"artist": [], "track": []}
    for row in trending_entities:
        entity_ids_by_type.setdefault(row.entity_type, []).append(row.entity_id)

    # Check artist genres
    if entity_ids_by_type.get("artist"):
        artist_result = await db.execute(
            select(Artist.genres).where(Artist.id.in_(entity_ids_by_type["artist"]))
        )
        for (genres_list,) in artist_result:
            if genres_list and any(g.startswith(root_genre) for g in genres_list):
                genre_match_count += 1

    # Check track genres
    if entity_ids_by_type.get("track"):
        track_result = await db.execute(
            select(Track.genres).where(Track.id.in_(entity_ids_by_type["track"]))
        )
        for (genres_list,) in track_result:
            if genres_list and any(g.startswith(root_genre) for g in genres_list):
                genre_match_count += 1

    defaults["genre_saturation"] = round(_safe_div(genre_match_count, total_trending), 4)
    defaults["artist_genre_rarity"] = round(1.0 - defaults["genre_saturation"], 4)

    # Genre overall momentum: average velocity of entities in same genre
    # Approximate using composite scores of genre-matched entities
    if genre_match_count > 0:
        # Use aggregate composite score trend for genre momentum
        genre_momentum_result = await db.execute(
            select(
                func.avg(TrendingSnapshot.velocity),
            )
            .where(
                TrendingSnapshot.snapshot_date >= week_ago,
                TrendingSnapshot.snapshot_date <= as_of,
            )
        )
        avg_vel = genre_momentum_result.scalar_one_or_none()
        defaults["genre_overall_momentum"] = round(float(avg_vel or 0.0), 4)

    # Genre new entry rate: fraction of trending entities first seen in last 7 days
    new_entry_result = await db.execute(
        select(func.count(func.distinct(TrendingSnapshot.entity_id))).where(
            TrendingSnapshot.snapshot_date >= week_ago,
            TrendingSnapshot.snapshot_date <= as_of,
        )
    )
    total_7d = new_entry_result.scalar_one_or_none() or 0

    before_result = await db.execute(
        select(func.count(func.distinct(TrendingSnapshot.entity_id))).where(
            TrendingSnapshot.snapshot_date < week_ago,
        )
    )
    total_before = before_result.scalar_one_or_none() or 0

    if total_7d > 0 and total_before > 0:
        # New entries = entities in 7d that were NOT in the before period
        # Approximation: ratio of new 7d / total before
        new_rate = max(0.0, (total_7d - total_before) / total_7d) if total_7d > total_before else 0.0
        defaults["genre_new_entry_rate"] = round(new_rate, 4)

    # Genre cross-branch momentum: look up adjacent genres and their momentum
    genre_result = await db.execute(
        select(Genre.adjacent_genres).where(Genre.id == primary_genre)
    )
    adjacent = genre_result.scalar_one_or_none()
    if adjacent:
        # Avg velocity across adjacent genres' entities
        adj_vel_result = await db.execute(
            select(func.avg(TrendingSnapshot.velocity))
            .where(
                TrendingSnapshot.snapshot_date >= week_ago,
                TrendingSnapshot.snapshot_date <= as_of,
                TrendingSnapshot.velocity.isnot(None),
            )
        )
        adj_vel = adj_vel_result.scalar_one_or_none()
        defaults["genre_cross_branch_momentum"] = round(float(adj_vel or 0.0), 4)

    return defaults


# ── Utility functions for training / serving ─────────────────────────

def features_to_vector(features: dict[str, float]) -> list[float]:
    """Convert a feature dict to an ordered numeric vector matching FEATURE_NAMES."""
    return [float(features.get(f, 0.0)) for f in FEATURE_NAMES]


async def get_entities_with_history(
    db: AsyncSession,
    min_days: int = 30,
) -> list[dict]:
    """Return entity_id / entity_type pairs with at least *min_days* of snapshot history."""
    stmt = (
        select(
            TrendingSnapshot.entity_id,
            TrendingSnapshot.entity_type,
            func.count(func.distinct(TrendingSnapshot.snapshot_date)).label("day_count"),
        )
        .group_by(TrendingSnapshot.entity_id, TrendingSnapshot.entity_type)
        .having(func.count(func.distinct(TrendingSnapshot.snapshot_date)) >= min_days)
    )
    result = await db.execute(stmt)
    rows = result.all()
    return [
        {"entity_id": row.entity_id, "entity_type": row.entity_type, "day_count": row.day_count}
        for row in rows
    ]


async def did_reach_top_n(
    db: AsyncSession,
    entity_id: uuid.UUID,
    entity_type: str,
    after_date: date,
    within_days: int = 14,
    top_n: int = 20,
) -> bool:
    """Check if entity reached top *top_n* within *within_days* after *after_date*."""
    end_date = after_date + timedelta(days=within_days)
    result = await db.execute(
        select(TrendingSnapshot.platform_rank)
        .where(
            TrendingSnapshot.entity_id == entity_id,
            TrendingSnapshot.entity_type == entity_type,
            TrendingSnapshot.snapshot_date > after_date,
            TrendingSnapshot.snapshot_date <= end_date,
            TrendingSnapshot.platform_rank.isnot(None),
            TrendingSnapshot.platform_rank <= top_n,
        )
        .limit(1)
    )
    return result.scalar_one_or_none() is not None


def get_history_days(sorted_dates: list[date]) -> int:
    """Return the number of days of history available."""
    if len(sorted_dates) < 2:
        return len(sorted_dates)
    return (sorted_dates[-1] - sorted_dates[0]).days
