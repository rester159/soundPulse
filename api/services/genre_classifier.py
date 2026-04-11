from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Union

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from shared.genre_taxonomy import GENRE_TAXONOMY

if TYPE_CHECKING:
    from api.models.artist import Artist
    from api.models.track import Track

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Known Spotify playlist ID → SoundPulse genre mappings
# ---------------------------------------------------------------------------
PLAYLIST_GENRES: dict[str, list[str]] = {
    "37i9dQZF1DX4JAvHpjipBk": ["electronic.house.tech-house"],
    "37i9dQZF1DX1kCIzMYtzum": ["electronic.house.deep-house"],
    "37i9dQZF1DX6J5NfMJS675": ["electronic.techno"],
    "37i9dQZF1DWTvNyxOwkzGM": ["electronic.house"],
    "37i9dQZF1DX0XUsuxWHRQd": ["hip-hop.rap"],
    "37i9dQZF1DX2RxBh64BHjQ": ["hip-hop.trap"],
    "37i9dQZF1DWY4xHQp97fN6": ["pop"],
    "37i9dQZF1DX10zKzsJ2jva": ["pop"],
    "37i9dQZF1DWXRqgorJj26U": ["rock"],
    "37i9dQZF1DX9GRpeH4CL0S": ["rock.metal"],
    "37i9dQZF1DX4E3UdUs7fUx": ["rock.punk"],
    "37i9dQZF1DX2Nc3B70tvx0": ["r-and-b"],
    "37i9dQZF1DX4SBhb3fqCJd": ["r-and-b.soul"],
    "37i9dQZF1DX8FwnYE6PRvL": ["country"],
    "37i9dQZF1DWZBCPUIUs2iR": ["latin.reggaeton"],
    "37i9dQZF1DX1lVhptIYRda": ["african.afrobeats"],
    "37i9dQZF1DXbITWG1ZJMcf": ["jazz"],
    "37i9dQZF1DWWEJlAGA9gs0": ["classical"],
    "37i9dQZF1DXc8kgYqQLMfH": ["electronic.ambient.lofi"],
    "37i9dQZF1DWWY64wDtewQt": ["electronic.phonk"],
    "37i9dQZF1DX7EidXGCHpnb": ["latin.salsa"],
    "37i9dQZF1DX50QitC6Oqtn": ["pop.k-pop"],
    "37i9dQZF1DXdbXrPNafg9d": ["pop.j-pop"],
    "37i9dQZF1DXaXDsfv6nvZ5": ["caribbean.dancehall"],
    "37i9dQZF1DX3LyU0mhfqgP": ["caribbean.reggae"],
    "37i9dQZF1DWTp2IZ2KPQMV": ["african.amapiano"],
}

# ---------------------------------------------------------------------------
# Hashtag → SoundPulse genre mapping for social tag signal
# ---------------------------------------------------------------------------
HASHTAG_GENRE_MAP: dict[str, list[str]] = {
    "edm": ["electronic"],
    "techno": ["electronic.techno"],
    "house": ["electronic.house"],
    "deephouse": ["electronic.house.deep-house"],
    "techhouse": ["electronic.house.tech-house"],
    "hiphop": ["hip-hop"],
    "rap": ["hip-hop.rap"],
    "trap": ["hip-hop.trap"],
    "drill": ["hip-hop.drill"],
    "rnb": ["r-and-b"],
    "soul": ["r-and-b.soul"],
    "country": ["country"],
    "rock": ["rock"],
    "metal": ["rock.metal"],
    "punk": ["rock.punk"],
    "indie": ["rock.indie"],
    "pop": ["pop"],
    "kpop": ["pop.k-pop"],
    "jpop": ["pop.j-pop"],
    "latin": ["latin"],
    "reggaeton": ["latin.reggaeton"],
    "salsa": ["latin.salsa"],
    "cumbia": ["latin.cumbia"],
    "afrobeats": ["african.afrobeats"],
    "amapiano": ["african.amapiano"],
    "reggae": ["caribbean.reggae"],
    "dancehall": ["caribbean.dancehall"],
    "jazz": ["jazz"],
    "classical": ["classical"],
    "lofi": ["electronic.ambient.lofi"],
    "phonk": ["electronic.phonk"],
    "trance": ["electronic.trance"],
    "dubstep": ["electronic.dubstep"],
    "dnb": ["electronic.drum-and-bass"],
    "drumandbass": ["electronic.drum-and-bass"],
    "synthwave": ["electronic.synthwave"],
    "ambient": ["electronic.ambient"],
    "funk": ["funk"],
    "disco": ["electronic.disco"],
    "gospel": ["gospel"],
    "blues": ["blues"],
    "folk": ["folk"],
    "acoustic": ["folk.acoustic"],
    "ska": ["caribbean.ska"],
    "grunge": ["rock.grunge"],
    "emo": ["rock.emo"],
    "hardstyle": ["electronic.hardstyle"],
    "garage": ["electronic.garage"],
    "grime": ["electronic.grime"],
    "bachata": ["latin.bachata"],
    "bossanova": ["latin.bossa-nova"],
    "samba": ["latin.samba"],
    "flamenco": ["latin.flamenco"],
}


# ---------------------------------------------------------------------------
# Result data-classes
# ---------------------------------------------------------------------------
@dataclass
class GenreCandidate:
    genre_id: str
    confidence: float
    signals: dict
    depth: int


@dataclass
class ClassificationResult:
    primary_genres: list[str]
    all_candidates: list[GenreCandidate]
    classification_quality: str
    # P1-013: richer quality metric beyond the single high/medium/low label
    signal_sources: dict[str, int] = field(default_factory=dict)  # {"platform_labels": 3, "audio_features": 1, ...}
    taxonomy_matched_count: int = 0   # how many unique genre IDs had any signal
    top_candidate_score: float = 0.0  # best candidate's raw score
    platform_hit_count: int = 0       # how many distinct platforms contributed


# ---------------------------------------------------------------------------
# Classifier
# ---------------------------------------------------------------------------
class GenreClassifier:
    """
    Multi-signal genre classification engine.
    Uses up to 6 signals, weighted by reliability.
    """

    SIGNAL_WEIGHTS: dict[str, float] = {
        "platform_labels": 0.30,
        "audio_features": 0.20,
        "artist_inheritance": 0.15,
        "playlist_context": 0.15,
        "social_tags": 0.10,
        "neighbor_inference": 0.10,
    }

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.taxonomy: dict[str, dict] = {g["id"]: g for g in GENRE_TAXONOMY}

        # Pre-build reverse lookups: platform genre string → SoundPulse genre IDs
        self.spotify_reverse: dict[str, list[str]] = {}
        self.apple_reverse: dict[str, list[str]] = {}
        self.musicbrainz_reverse: dict[str, list[str]] = {}
        self.chartmetric_reverse: dict[str, list[str]] = {}
        self._last_platform_hits: dict[str, int] = {}

        for genre in GENRE_TAXONOMY:
            gid = genre["id"]
            for sg in genre.get("spotify_genres", []):
                self.spotify_reverse.setdefault(sg.lower(), []).append(gid)
            for ag in genre.get("apple_music_genres", []):
                self.apple_reverse.setdefault(ag.lower(), []).append(gid)
            for mt in genre.get("musicbrainz_tags", []):
                self.musicbrainz_reverse.setdefault(mt.lower(), []).append(gid)
            for cg in genre.get("chartmetric_genres", []):
                self.chartmetric_reverse.setdefault(cg.lower(), []).append(gid)

        # Collect all platform labels for fuzzy matching fallback
        self._all_label_to_genre: dict[str, str] = {}
        for genre in GENRE_TAXONOMY:
            gid = genre["id"]
            name = genre.get("name", "")
            if name:
                self._all_label_to_genre[name.lower()] = gid
            for mapping_key in (
                "spotify_genres",
                "apple_music_genres",
                "musicbrainz_tags",
                "chartmetric_genres",
            ):
                for label in genre.get(mapping_key, []):
                    self._all_label_to_genre[label.lower()] = gid

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def classify(self, entity: Union[Artist, Track]) -> ClassificationResult:
        """Main entry point.  Classify an entity into SoundPulse genres."""
        is_track = _is_track(entity)

        # Gather raw signal dicts: {genre_id: score}
        signal_results: dict[str, dict[str, float]] = {}

        signal_results["platform_labels"] = self._signal_platform_labels(entity)
        signal_results["audio_features"] = (
            self._signal_audio_features(entity, signal_results["platform_labels"])
            if is_track
            else {}
        )
        signal_results["artist_inheritance"] = (
            await self._signal_artist_inheritance(entity) if is_track else {}
        )
        signal_results["playlist_context"] = self._signal_playlist_context(entity)
        signal_results["social_tags"] = self._signal_social_tags(entity)
        signal_results["neighbor_inference"] = await self._signal_neighbor_inference(
            entity, is_track
        )

        # Merge into weighted candidate map
        merged: dict[str, dict] = {}  # genre_id → {score, signals}
        for signal_name, scores in signal_results.items():
            weight = self.SIGNAL_WEIGHTS[signal_name]
            for genre_id, raw_score in scores.items():
                if genre_id not in self.taxonomy:
                    continue
                weighted = raw_score * weight
                if genre_id not in merged:
                    merged[genre_id] = {"score": 0.0, "signals": {}}
                merged[genre_id]["score"] += weighted
                merged[genre_id]["signals"][signal_name] = raw_score

        # P1-013: compute richer quality metrics
        signal_sources = {name: len(scores) for name, scores in signal_results.items() if scores}

        if not merged:
            return ClassificationResult(
                primary_genres=[],
                all_candidates=[],
                classification_quality="low",
                signal_sources=signal_sources,
                taxonomy_matched_count=0,
                top_candidate_score=0.0,
                platform_hit_count=len(self._last_platform_hits),
            )

        candidates = [
            GenreCandidate(
                genre_id=gid,
                confidence=info["score"],
                signals=info["signals"],
                depth=gid.count("."),
            )
            for gid, info in merged.items()
        ]

        ranked = self._resolve_hierarchy(candidates)
        primary = self._select_primary_genres(ranked)
        quality = self._assess_quality(ranked, primary)

        return ClassificationResult(
            primary_genres=[c.genre_id for c in primary],
            all_candidates=ranked,
            classification_quality=quality,
            signal_sources=signal_sources,
            taxonomy_matched_count=len(merged),
            top_candidate_score=ranked[0].confidence if ranked else 0.0,
            platform_hit_count=len(self._last_platform_hits),
        )

    async def classify_and_save(
        self, entity: Union[Artist, Track]
    ) -> ClassificationResult:
        """Classify, persist genres on the entity, and write rich quality
        metrics into metadata_json under `classification_details`.
        """
        result = await self.classify(entity)
        if result.primary_genres:
            entity.genres = result.primary_genres

        # P1-013: write richer classification details so we can debug why
        # classification succeeded or failed without re-running.
        existing_meta = entity.metadata_json or {}
        entity.metadata_json = {
            **existing_meta,
            "classification_quality": result.classification_quality,
            "classification_details": {
                "primary_genres": result.primary_genres,
                "signal_sources": result.signal_sources,
                "taxonomy_matched_count": result.taxonomy_matched_count,
                "top_candidate_score": result.top_candidate_score,
                "platform_hit_count": result.platform_hit_count,
                "candidate_count": len(result.all_candidates),
            },
        }
        return result

    # ------------------------------------------------------------------
    # Signal 1: Platform Label Mapping (weight 0.30)
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_label_list(value: Any) -> list[str]:
        """
        Accept either a list of genre labels OR a comma-separated string
        (optionally with semicolons, slashes, pipes) and return a clean list.

        P1-012: Chartmetric ships genres as a comma-string like
        `"pop, dance pop, chill pop"` inside `signals_json.genres` — NOT
        as a structured array. The trending ingest path copied that into
        `metadata_json` unchanged, and the classifier's original iteration
        walked character-by-character through the string. This is the root
        cause of ~95% of tracks being unclassified.
        """
        if value is None:
            return []
        if isinstance(value, list):
            return [str(item).strip() for item in value if item and str(item).strip()]
        if isinstance(value, str):
            # Split on comma, semicolon, slash, pipe
            import re
            parts = re.split(r"[,;/|]+", value)
            return [p.strip() for p in parts if p.strip()]
        return []

    def _signal_platform_labels(self, entity: Union[Artist, Track]) -> dict[str, float]:
        meta = entity.metadata_json or {}
        scores: dict[str, float] = {}
        # Track how many distinct platforms contributed to each genre
        platform_hits: dict[str, int] = {}

        # P1-012: normalize every source list in case it came in as a
        # comma-string. Also check `genres` (the raw Chartmetric field that
        # the bulk endpoint copies straight through) — it maps to
        # chartmetric_reverse because that's where Chartmetric's labels live.
        raw_chartmetric_genres = (
            meta.get("chartmetric_genres") or meta.get("genres") or []
        )

        source_configs: list[tuple[list[str], dict[str, list[str]], float]] = [
            (self._normalize_label_list(meta.get("spotify_genres", [])),
             self.spotify_reverse, 1.0),
            (self._normalize_label_list(meta.get("apple_music_genres", [])),
             self.apple_reverse, 0.8),
            (self._normalize_label_list(meta.get("musicbrainz_tags", [])),
             self.musicbrainz_reverse, 0.7),
            (self._normalize_label_list(raw_chartmetric_genres),
             self.chartmetric_reverse, 0.8),
        ]

        unmatched_labels: list[str] = []

        for labels, reverse_map, base_score in source_configs:
            matched_this_source: set[str] = set()
            for raw_label in labels:
                label = raw_label.lower().strip()
                if not label:
                    continue
                matched_ids = reverse_map.get(label)
                if matched_ids:
                    for gid in matched_ids:
                        scores[gid] = max(scores.get(gid, 0.0), base_score)
                        matched_this_source.add(gid)
                else:
                    unmatched_labels.append(label)
            # Count this platform source for each genre it matched
            for gid in matched_this_source:
                platform_hits[gid] = platform_hits.get(gid, 0) + 1

        # Cross-platform agreement bonus: if 2+ platforms agree, boost score
        for gid, hit_count in platform_hits.items():
            if hit_count >= 2:
                bonus = min((hit_count - 1) * 0.15, 0.3)
                scores[gid] = min(scores.get(gid, 0.0) + bonus, 1.0)

        # Store platform hit counts so quality assessment can use them
        self._last_platform_hits = platform_hits

        # Fuzzy matching fallback for unmatched labels
        for label in unmatched_labels:
            fuzzy_id = self._fuzzy_match_genre(label)
            if fuzzy_id:
                scores[fuzzy_id] = max(scores.get(fuzzy_id, 0.0), 0.5)
            else:
                logger.debug("Unmatched platform label: %s", label)

        return scores

    # ------------------------------------------------------------------
    # Signal 2: Audio Feature Matching (weight 0.20) — tracks only
    # ------------------------------------------------------------------

    def _signal_audio_features(
        self,
        entity: Union[Artist, Track],
        platform_candidates: dict[str, float],
    ) -> dict[str, float]:
        af = getattr(entity, "audio_features", None)
        if not af or not isinstance(af, dict):
            return {}

        feature_keys = ["tempo", "energy", "valence", "danceability"]
        feature_values: dict[str, float] = {}
        for key in feature_keys:
            val = af.get(key)
            if val is not None:
                try:
                    feature_values[key] = float(val)
                except (TypeError, ValueError):
                    pass

        if not feature_values:
            return {}

        # Determine which genres to score
        genres_to_score: set[str] = set()
        if platform_candidates:
            genres_to_score.update(platform_candidates.keys())
        # Always include root and depth-1 genres
        for gid in self.taxonomy:
            if gid.count(".") <= 1:
                genres_to_score.add(gid)

        scores: dict[str, float] = {}
        for gid in genres_to_score:
            genre_def = self.taxonomy.get(gid)
            if not genre_def:
                continue
            audio_profile = genre_def.get("audio_profile")
            if not audio_profile or not isinstance(audio_profile, dict):
                continue

            dimension_scores: list[float] = []
            for key, value in feature_values.items():
                range_key = f"{key}_range"
                genre_range = audio_profile.get(range_key)
                if not genre_range or len(genre_range) != 2:
                    continue

                low, high = genre_range[0], genre_range[1]
                range_size = high - low if high > low else 1.0

                if low <= value <= high:
                    dimension_scores.append(1.0)
                else:
                    distance = min(abs(value - low), abs(value - high))
                    closeness = max(0.0, 1.0 - distance / range_size) * 0.5
                    dimension_scores.append(closeness)

            if dimension_scores:
                avg = sum(dimension_scores) / len(dimension_scores)
                if avg > 0.5:
                    scores[gid] = avg

        return scores

    # ------------------------------------------------------------------
    # Signal 3: Artist Genre Inheritance (weight 0.15) — tracks only
    # ------------------------------------------------------------------

    async def _signal_artist_inheritance(
        self, entity: Union[Artist, Track]
    ) -> dict[str, float]:
        artist = getattr(entity, "artist", None)

        if artist is None:
            artist_id = getattr(entity, "artist_id", None)
            if artist_id is None:
                return {}
            try:
                from api.models.artist import Artist as ArtistModel

                result = await self.db.execute(
                    select(ArtistModel).where(ArtistModel.id == artist_id)
                )
                artist = result.scalar_one_or_none()
            except Exception as exc:
                # AUD-006: was `logger.debug` which is invisible at default
                # log levels. Failed artist lookups directly cause empty
                # genre classification — surface them at warning.
                logger.warning(
                    "[genre-classifier] artist inheritance failed: track=%s artist_id=%s err=%s",
                    entity.id, artist_id, exc,
                )
                return {}

        if artist is None:
            return {}

        artist_genres: list[str] = getattr(artist, "genres", None) or []
        scores: dict[str, float] = {}
        for gid in artist_genres:
            if gid in self.taxonomy:
                scores[gid] = 0.85
        return scores

    # ------------------------------------------------------------------
    # Signal 4: Playlist Context (weight 0.15)
    # ------------------------------------------------------------------

    def _signal_playlist_context(self, entity: Union[Artist, Track]) -> dict[str, float]:
        meta = entity.metadata_json or {}

        # Pre-mapped playlist genres
        playlist_genres: list[str] = meta.get("playlist_genres", [])
        if playlist_genres:
            vote_counts: dict[str, int] = {}
            for gid in playlist_genres:
                vote_counts[gid] = vote_counts.get(gid, 0) + 1
            if vote_counts:
                max_votes = max(vote_counts.values())
                return {
                    gid: count / max_votes
                    for gid, count in vote_counts.items()
                    if gid in self.taxonomy
                }

        # Raw playlist IDs
        playlists: list[str] = meta.get("playlists", [])
        if playlists:
            vote_counts = {}
            for pid in playlists:
                genre_ids = PLAYLIST_GENRES.get(pid, [])
                for gid in genre_ids:
                    vote_counts[gid] = vote_counts.get(gid, 0) + 1
            if vote_counts:
                max_votes = max(vote_counts.values())
                return {
                    gid: count / max_votes
                    for gid, count in vote_counts.items()
                    if gid in self.taxonomy
                }

        return {}

    # ------------------------------------------------------------------
    # Signal 5: Social Tag Analysis (weight 0.10)
    # ------------------------------------------------------------------

    def _signal_social_tags(self, entity: Union[Artist, Track]) -> dict[str, float]:
        meta = entity.metadata_json or {}
        hashtags: list[str] = meta.get("tiktok_hashtags", [])
        if not hashtags:
            return {}

        scores: dict[str, float] = {}
        for raw_tag in hashtags:
            tag = raw_tag.lower().strip().lstrip("#")
            genre_ids = HASHTAG_GENRE_MAP.get(tag, [])
            for gid in genre_ids:
                if gid in self.taxonomy:
                    scores[gid] = max(scores.get(gid, 0.0), 0.6)
        return scores

    # ------------------------------------------------------------------
    # Signal 6: Neighbor Inference (weight 0.10)
    # ------------------------------------------------------------------

    async def _signal_neighbor_inference(
        self,
        entity: Union[Artist, Track],
        is_track: bool,
    ) -> dict[str, float]:
        # Determine root categories from the entity (or its artist).
        # For tracks, we need the artist's genres. Accessing entity.artist on
        # an async-loaded Track fails with MissingGreenlet if the relationship
        # wasn't eagerly loaded — catch that explicitly instead of silently
        # returning {}.
        source_genres: list[str] = []
        artist_id: Any = None
        if is_track:
            try:
                artist = getattr(entity, "artist", None)
            except Exception as exc:
                logger.warning(
                    "[genre-classifier] neighbor inference: could not access "
                    "entity.artist for track %s (likely not eager-loaded): %s",
                    getattr(entity, "id", None), exc,
                )
                artist = None
            if artist is not None:
                source_genres = list(getattr(artist, "genres", None) or [])
                artist_id = getattr(artist, "id", None)
            else:
                # Fall back: load the artist by FK
                try:
                    from api.models.artist import Artist as ArtistModel
                    fk = getattr(entity, "artist_id", None)
                    if fk:
                        result = await self.db.execute(
                            select(ArtistModel).where(ArtistModel.id == fk)
                        )
                        artist = result.scalar_one_or_none()
                        if artist:
                            source_genres = list(getattr(artist, "genres", None) or [])
                            artist_id = artist.id
                except Exception as exc:
                    logger.warning(
                        "[genre-classifier] neighbor inference fallback load "
                        "failed for track %s: %s",
                        getattr(entity, "id", None), exc,
                    )
        else:
            source_genres = list(getattr(entity, "genres", None) or [])
            artist_id = getattr(entity, "id", None)

        root_categories = list({g.split(".")[0] for g in source_genres if g})
        if not root_categories:
            return {}

        # CORRECTED: previously fell back to entity.id (the track's UUID)
        # when artist couldn't be resolved — that comparison against the
        # artists table would never match and made the filter meaningless.
        # Now we only run the query when we have a real artist_id.
        if artist_id is None:
            return {}

        try:
            result = await self.db.execute(
                text(
                    "SELECT genres FROM artists "
                    "WHERE genres && :roots "
                    "AND id != :eid "
                    "LIMIT 20"
                ),
                {"roots": root_categories, "eid": str(artist_id)},
            )
            rows = result.fetchall()
        except Exception as exc:
            # AUD-005 + AUD-006 family: was logger.debug (invisible). Promoted
            # to warning so neighbor-inference failures surface in logs.
            logger.warning(
                "[genre-classifier] neighbor inference query failed "
                "for artist_id=%s roots=%s: %s",
                artist_id, root_categories, exc,
            )
            return {}

        if not rows:
            return {}

        genre_counts: dict[str, int] = {}
        total = len(rows)
        for row in rows:
            neighbor_genres = row[0] if row[0] else []
            for gid in neighbor_genres:
                genre_counts[gid] = genre_counts.get(gid, 0) + 1

        threshold = total * 0.2
        scores: dict[str, float] = {}
        for gid, count in genre_counts.items():
            if count >= threshold and gid in self.taxonomy:
                scores[gid] = count / total

        return scores

    # ------------------------------------------------------------------
    # Hierarchy Resolution
    # ------------------------------------------------------------------

    def _resolve_hierarchy(
        self, candidates: list[GenreCandidate]
    ) -> list[GenreCandidate]:
        # Apply depth bonus: +5% per depth level, max +15%
        for c in candidates:
            bonus = min(c.depth * 0.05, 0.15)
            c.confidence += bonus
            c.confidence = min(c.confidence, 1.0)

        # Build a lookup for fast access
        by_id: dict[str, GenreCandidate] = {c.genre_id: c for c in candidates}

        # Remove redundant ancestors
        ids_to_remove: set[str] = set()
        for c in candidates:
            parts = c.genre_id.split(".")
            # Check all ancestor paths
            for i in range(1, len(parts)):
                ancestor_id = ".".join(parts[:i])
                ancestor = by_id.get(ancestor_id)
                if ancestor and ancestor.confidence <= c.confidence:
                    ids_to_remove.add(ancestor_id)

        filtered = [c for c in candidates if c.genre_id not in ids_to_remove]
        filtered.sort(key=lambda c: c.confidence, reverse=True)

        # Cap confidence
        for c in filtered:
            c.confidence = min(c.confidence, 1.0)

        return filtered

    def _select_primary_genres(
        self, ranked: list[GenreCandidate]
    ) -> list[GenreCandidate]:
        if not ranked:
            return []

        primary: list[GenreCandidate] = [ranked[0]]
        top_confidence = ranked[0].confidence
        roots_used: set[str] = {ranked[0].genre_id.split(".")[0]}
        parents_at_depth: dict[tuple[str, int], float] = {}

        # Track the first primary's parent info
        first_parts = ranked[0].genre_id.split(".")
        if len(first_parts) > 1:
            parent = ".".join(first_parts[:-1])
            parents_at_depth[(parent, ranked[0].depth)] = ranked[0].confidence

        for c in ranked[1:]:
            if len(primary) >= 3:
                break
            if c.confidence < 0.4:
                break
            if c.confidence < top_confidence * 0.5:
                break

            root = c.genre_id.split(".")[0]

            # Check sibling constraint
            parts = c.genre_id.split(".")
            if len(parts) > 1:
                parent = ".".join(parts[:-1])
                key = (parent, c.depth)
                if key in parents_at_depth and c.confidence < 0.7:
                    continue
                parents_at_depth[key] = c.confidence

            # Max 3 different root categories
            if root not in roots_used and len(roots_used) >= 3:
                continue

            primary.append(c)
            roots_used.add(root)

        return primary

    def _assess_quality(
        self,
        ranked: list[GenreCandidate],
        primary: list[GenreCandidate],
    ) -> str:
        if not ranked or not primary:
            return "low"

        top = ranked[0]
        top_confidence = top.confidence
        signal_count = len(top.signals)

        # Count distinct platform sources that agreed on the top genre
        platform_hits = getattr(self, "_last_platform_hits", {})
        platform_agreement = platform_hits.get(top.genre_id, 0)
        # Treat cross-platform agreement as additional effective signals
        effective_signals = signal_count + max(0, platform_agreement - 1)

        if top_confidence > 0.7 and effective_signals >= 3:
            return "high"
        if top_confidence >= 0.4 or effective_signals >= 2:
            return "medium"
        return "low"

    # ------------------------------------------------------------------
    # Fuzzy matching helper
    # ------------------------------------------------------------------

    def _fuzzy_match_genre(self, label: str, threshold: float = 0.75) -> str | None:
        try:
            from rapidfuzz import fuzz
        except ImportError:
            return None

        best_score = 0.0
        best_id: str | None = None

        for known_label, genre_id in self._all_label_to_genre.items():
            score = fuzz.ratio(label, known_label) / 100.0
            if score > best_score:
                best_score = score
                best_id = genre_id

        if best_score >= threshold and best_id is not None:
            return best_id
        return None


# ---------------------------------------------------------------------------
# Internal helper
# ---------------------------------------------------------------------------

def _is_track(entity: Union[Artist, Track]) -> bool:
    """Determine whether the entity is a Track (vs Artist) by checking for
    the ``artist_id`` attribute which only exists on the Track model."""
    return hasattr(entity, "artist_id")
