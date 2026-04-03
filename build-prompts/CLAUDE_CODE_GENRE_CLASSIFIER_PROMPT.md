# SoundPulse Genre Classification Engine — Claude Code Build Prompt

> **How every track and artist gets mapped to SoundPulse's 850+ proprietary genre taxonomy.**
> This is the bridge between upstream platform labels and SoundPulse's hierarchy.

---

## THE PROBLEM

SoundPulse has a proprietary taxonomy of 850+ genres in a dot-notation hierarchy.
Upstream platforms each have their OWN genre systems:

- **Spotify**: ~1,500 genre strings (free-form, e.g., "bedroom pop", "german techno", "escape room")
- **Apple Music**: ~300 curated genres (broad, e.g., "Electronic", "Alternative")
- **MusicBrainz**: Open folksonomy tags (community-submitted, messy, e.g., "tech house", "deep house", "housey house")
- **Chartmetric**: ~200 genres (their own taxonomy)
- **TikTok**: No genres at all — just sounds and hashtags
- **Shazam**: Minimal genre info
- **Radio**: Format-based ("CHR/Top 40", "Urban", "Country") — not genre-specific

No single source is reliable alone. A track might be labeled "pop" on Apple Music, "dance pop, post-teen pop, pop" on Spotify, have MusicBrainz tags "synth-pop, electropop, dance-pop", and be trending on TikTok with #edm and #dancepop hashtags.

SoundPulse needs to take ALL of these signals and output: `["pop.dance-pop", "pop.synth-pop.electropop"]`

---

## THE SOLUTION: MULTI-SIGNAL GENRE CLASSIFICATION

### Architecture

```
Incoming entity (track or artist)
       │
       ▼
┌──────────────────────────────────┐
│  SIGNAL 1: Platform Label Mapping │  ← Direct lookup from stored mappings
│  SIGNAL 2: Audio Feature Matching │  ← Compare audio features to genre profiles
│  SIGNAL 3: Artist Genre Inheritance│  ← Track inherits artist's genres
│  SIGNAL 4: Playlist Context       │  ← What playlists is this track on?
│  SIGNAL 5: Social Tag Analysis    │  ← TikTok hashtags, MusicBrainz tags
│  SIGNAL 6: Neighbor Inference     │  ← What genres do similar artists have?
└──────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────┐
│  GENRE SCORER                     │  ← Score each candidate genre 0-1
│  (weighted combination of signals)│
└──────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────┐
│  HIERARCHY RESOLVER               │  ← Pick the right depth level
│  (prefer specific over broad)     │  ← Enforce parent consistency
└──────────────────────────────────┘
       │
       ▼
Final genre assignment: ["pop.dance-pop", "pop.synth-pop.electropop"]
```

---

## BUILD: `api/services/genre_classifier.py`

```python
"""
Multi-Signal Genre Classification Engine

Takes an entity (track or artist) and all available metadata,
returns a ranked list of SoundPulse genre IDs with confidence scores.
"""

from dataclasses import dataclass
from shared.genre_taxonomy import GENRE_TAXONOMY

@dataclass
class GenreCandidate:
    genre_id: str           # e.g., "electronic.house.tech-house"
    confidence: float       # 0.0 to 1.0
    signals: dict           # which signals contributed and how much
    depth: int              # genre depth in hierarchy

@dataclass
class ClassificationResult:
    primary_genres: list[str]       # top 1-3 genre IDs assigned to entity
    all_candidates: list[GenreCandidate]  # full ranked list
    classification_quality: str     # "high", "medium", "low" based on signal agreement


class GenreClassifier:
    """
    Classifies entities into SoundPulse's proprietary genre taxonomy.
    Uses up to 6 signals, weighted by reliability.
    """

    # Signal weights — how much to trust each signal source
    SIGNAL_WEIGHTS = {
        "platform_labels": 0.30,      # Spotify/Apple/MusicBrainz genre strings
        "audio_features": 0.20,       # Tempo, energy, valence matching
        "artist_inheritance": 0.15,   # Track gets artist's genres
        "playlist_context": 0.15,     # Genre inferred from playlist membership
        "social_tags": 0.10,          # TikTok hashtags, user tags
        "neighbor_inference": 0.10,   # Similar artists' genres
    }

    def __init__(self, genre_taxonomy: list[dict], db_session):
        self.taxonomy = {g["id"]: g for g in genre_taxonomy}
        self.db = db_session

        # Pre-build reverse lookup: platform genre string → SoundPulse genre IDs
        # e.g., "tech house" (Spotify) → ["electronic.house.tech-house"]
        self.spotify_reverse = {}
        self.apple_reverse = {}
        self.musicbrainz_reverse = {}
        self.chartmetric_reverse = {}

        for genre in genre_taxonomy:
            for sg in genre.get("spotify_genres", []):
                self.spotify_reverse.setdefault(sg.lower(), []).append(genre["id"])
            for ag in genre.get("apple_music_genres", []):
                self.apple_reverse.setdefault(ag.lower(), []).append(genre["id"])
            for mt in genre.get("musicbrainz_tags", []):
                self.musicbrainz_reverse.setdefault(mt.lower(), []).append(genre["id"])
            for cg in genre.get("chartmetric_genres", []):
                self.chartmetric_reverse.setdefault(cg.lower(), []).append(genre["id"])


    async def classify(self, entity) -> ClassificationResult:
        """
        Main entry point. Takes a Track or Artist entity with all available metadata.
        Returns classified genres.
        """
        candidates: dict[str, float] = {}  # genre_id → cumulative score
        signal_details: dict[str, dict] = {}  # genre_id → {signal: contribution}

        # ── SIGNAL 1: Platform Label Mapping ──
        # Direct lookup: take genre strings from each platform and map them
        platform_genres = await self._signal_platform_labels(entity)
        for genre_id, score in platform_genres.items():
            candidates[genre_id] = candidates.get(genre_id, 0) + score * self.SIGNAL_WEIGHTS["platform_labels"]
            signal_details.setdefault(genre_id, {})["platform_labels"] = score

        # ── SIGNAL 2: Audio Feature Matching ──
        # Compare entity's audio features to each genre's expected profile
        if entity.audio_features:
            audio_genres = self._signal_audio_features(entity.audio_features)
            for genre_id, score in audio_genres.items():
                candidates[genre_id] = candidates.get(genre_id, 0) + score * self.SIGNAL_WEIGHTS["audio_features"]
                signal_details.setdefault(genre_id, {})["audio_features"] = score

        # ── SIGNAL 3: Artist Genre Inheritance ──
        # For tracks: inherit the artist's genres (with slight discount)
        if hasattr(entity, 'artist_id') and entity.artist_id:
            artist_genres = await self._signal_artist_inheritance(entity.artist_id)
            for genre_id, score in artist_genres.items():
                candidates[genre_id] = candidates.get(genre_id, 0) + score * self.SIGNAL_WEIGHTS["artist_inheritance"]
                signal_details.setdefault(genre_id, {})["artist_inheritance"] = score

        # ── SIGNAL 4: Playlist Context ──
        # What playlists is this track on? Playlists have implicit genres.
        if hasattr(entity, 'spotify_id') and entity.spotify_id:
            playlist_genres = await self._signal_playlist_context(entity.spotify_id)
            for genre_id, score in playlist_genres.items():
                candidates[genre_id] = candidates.get(genre_id, 0) + score * self.SIGNAL_WEIGHTS["playlist_context"]
                signal_details.setdefault(genre_id, {})["playlist_context"] = score

        # ── SIGNAL 5: Social Tag Analysis ──
        # TikTok hashtags, MusicBrainz user tags, etc.
        social_genres = await self._signal_social_tags(entity)
        for genre_id, score in social_genres.items():
            candidates[genre_id] = candidates.get(genre_id, 0) + score * self.SIGNAL_WEIGHTS["social_tags"]
            signal_details.setdefault(genre_id, {})["social_tags"] = score

        # ── SIGNAL 6: Neighbor Inference ──
        # What genres do similar/related artists have?
        neighbor_genres = await self._signal_neighbor_inference(entity)
        for genre_id, score in neighbor_genres.items():
            candidates[genre_id] = candidates.get(genre_id, 0) + score * self.SIGNAL_WEIGHTS["neighbor_inference"]
            signal_details.setdefault(genre_id, {})["neighbor_inference"] = score

        # ── RESOLVE: Pick final genres ──
        ranked = self._resolve_hierarchy(candidates, signal_details)
        primary = self._select_primary_genres(ranked)
        quality = self._assess_quality(ranked, primary)

        return ClassificationResult(
            primary_genres=[g.genre_id for g in primary],
            all_candidates=ranked,
            classification_quality=quality,
        )


    # ══════════════════════════════════════════════
    # SIGNAL IMPLEMENTATIONS
    # ══════════════════════════════════════════════

    async def _signal_platform_labels(self, entity) -> dict[str, float]:
        """
        SIGNAL 1: Map platform genre strings to SoundPulse genres.
        This is the most reliable signal when available.

        Example:
            Spotify says: ["tech house", "deep house"]
            Lookup: "tech house" → "electronic.house.tech-house" (score 1.0)
                    "deep house" → "electronic.house.deep-house" (score 1.0)
        """
        scores = {}

        # Spotify genres (most granular, best source)
        spotify_genres = entity.metadata_json.get("spotify_genres", [])
        for sg in spotify_genres:
            matched = self.spotify_reverse.get(sg.lower(), [])
            for genre_id in matched:
                scores[genre_id] = max(scores.get(genre_id, 0), 1.0)

        # Apple Music genres (broader, less useful)
        apple_genres = entity.metadata_json.get("apple_music_genres", [])
        for ag in apple_genres:
            matched = self.apple_reverse.get(ag.lower(), [])
            for genre_id in matched:
                scores[genre_id] = max(scores.get(genre_id, 0), 0.8)  # slightly lower confidence

        # MusicBrainz tags
        mb_tags = entity.metadata_json.get("musicbrainz_tags", [])
        for mt in mb_tags:
            matched = self.musicbrainz_reverse.get(mt.lower(), [])
            for genre_id in matched:
                scores[genre_id] = max(scores.get(genre_id, 0), 0.7)

        # Chartmetric genres
        cm_genres = entity.metadata_json.get("chartmetric_genres", [])
        for cg in cm_genres:
            matched = self.chartmetric_reverse.get(cg.lower(), [])
            for genre_id in matched:
                scores[genre_id] = max(scores.get(genre_id, 0), 0.8)

        # FUZZY MATCHING for unmatched labels
        # If a platform genre string doesn't have an exact mapping,
        # try fuzzy matching against all genre names in the taxonomy
        all_platform_labels = set(
            [s.lower() for s in spotify_genres + apple_genres + mb_tags + cm_genres]
        )
        mapped_labels = set()
        for genre_id in scores:
            g = self.taxonomy[genre_id]
            mapped_labels.update(s.lower() for s in g.get("spotify_genres", []))
            mapped_labels.update(s.lower() for s in g.get("apple_music_genres", []))

        unmatched = all_platform_labels - mapped_labels
        for label in unmatched:
            best_match = self._fuzzy_match_genre(label)
            if best_match:
                scores[best_match] = max(scores.get(best_match, 0), 0.5)  # lower confidence for fuzzy

        return scores


    def _signal_audio_features(self, audio_features: dict) -> dict[str, float]:
        """
        SIGNAL 2: Compare track's audio features to each genre's expected profile.

        Example:
            Track has: tempo=126, energy=0.72, danceability=0.83, valence=0.45
            Genre "electronic.house.tech-house" expects:
                tempo: [120, 130], energy: [0.6, 0.85], valence: [0.3, 0.7], danceability: [0.7, 0.9]
            → All features in range → high score

            Genre "rock.metal.death-metal" expects:
                tempo: [100, 200], energy: [0.8, 1.0], valence: [0.1, 0.4], danceability: [0.3, 0.5]
            → danceability way out of range → low score
        """
        track_tempo = audio_features.get("tempo")
        track_energy = audio_features.get("energy")
        track_valence = audio_features.get("valence")
        track_danceability = audio_features.get("danceability")

        scores = {}

        for genre_id, genre in self.taxonomy.items():
            profile = genre.get("audio_profile")
            if not profile:
                continue

            feature_matches = 0
            feature_count = 0

            # For each audio dimension, check if track falls within genre's range
            for feature_name, track_value in [
                ("tempo_range", track_tempo),
                ("energy_range", track_energy),
                ("valence_range", track_valence),
                ("danceability_range", track_danceability),
            ]:
                range_vals = profile.get(feature_name)
                if range_vals and track_value is not None:
                    feature_count += 1
                    low, high = range_vals
                    if low <= track_value <= high:
                        feature_matches += 1
                    else:
                        # Partial credit for being close
                        distance = min(abs(track_value - low), abs(track_value - high))
                        range_size = high - low
                        if range_size > 0:
                            closeness = max(0, 1 - (distance / range_size))
                            feature_matches += closeness * 0.5  # half credit for close

            if feature_count > 0:
                match_score = feature_matches / feature_count
                if match_score > 0.5:  # only include reasonable matches
                    scores[genre_id] = match_score

        return scores


    async def _signal_artist_inheritance(self, artist_id: str) -> dict[str, float]:
        """
        SIGNAL 3: Track inherits genres from its artist.

        If an artist is classified as ["hip-hop.trap.melodic-trap", "r-and-b.contemporary-rnb"],
        their new track likely falls into one of those genres too.

        Discount slightly because artists can release tracks outside their usual genre.
        """
        artist = await self.db.get(Artist, artist_id)
        if not artist or not artist.genres:
            return {}

        return {genre_id: 0.85 for genre_id in artist.genres}


    async def _signal_playlist_context(self, spotify_id: str) -> dict[str, float]:
        """
        SIGNAL 4: Infer genre from playlist membership.

        Spotify playlists have implicit genres:
            "RapCaviar" → hip-hop
            "mint" → electronic
            "Hot Country" → country
            "Are & Be" → r-and-b

        If a track appears on "RapCaviar" AND "Feelin' Myself",
        strong signal for hip-hop.

        Build a playlist → genre mapping table and look up which playlists
        the track appears on.
        """
        # Playlist-to-genre mapping (maintained as a lookup table)
        # This is populated during Spotify scraping — each monitored playlist
        # is tagged with its primary genre(s)
        PLAYLIST_GENRES = {
            "37i9dQZF1DX0XUsuxWHRQd": ["hip-hop"],                    # RapCaviar
            "37i9dQZF1DX4dyzvuaRJ0n": ["electronic"],                 # mint
            "37i9dQZF1DX1lVhptIYRda": ["country"],                    # Hot Country
            "37i9dQZF1DX4SBhb3fqCJd": ["r-and-b"],                    # Are & Be
            "37i9dQZF1DX10zKzsJ2jva": ["latin"],                      # Viva Latino
            "37i9dQZF1DWXRqgorJj26U": ["rock"],                       # Rock This
            "37i9dQZF1DXcBWIGoYBM5M": [],                             # Today's Top Hits (mixed)
            "37i9dQZEVXbLiRSasKsNU9": [],                             # Viral 50 (mixed)
            # ... extended during scraping as new playlists are discovered
        }

        # Look up which playlists this track is on
        playlists = await self._get_entity_playlists(spotify_id)

        genre_votes = {}
        for playlist_id in playlists:
            genres = PLAYLIST_GENRES.get(playlist_id, [])
            for g in genres:
                # Vote for this root genre and any current children
                genre_votes[g] = genre_votes.get(g, 0) + 1

        if not genre_votes:
            return {}

        max_votes = max(genre_votes.values())
        return {genre_id: count / max_votes for genre_id, count in genre_votes.items()}


    async def _signal_social_tags(self, entity) -> dict[str, float]:
        """
        SIGNAL 5: Analyze TikTok hashtags and other social metadata.

        TikTok has no genre system, but hashtags carry genre signal:
            #edm → electronic
            #trap → hip-hop.trap
            #countrymusic → country
            #afrobeats → african.afrobeats
            #indievibes → rock.alternative.indie-rock OR pop.indie-pop

        Build a hashtag → genre mapping and score based on frequency.
        """
        HASHTAG_GENRE_MAP = {
            "edm": ["electronic.edm"],
            "techno": ["electronic.techno"],
            "house": ["electronic.house"],
            "deephouse": ["electronic.house.deep-house"],
            "techhouse": ["electronic.house.tech-house"],
            "hiphop": ["hip-hop"],
            "rap": ["hip-hop"],
            "trap": ["hip-hop.trap"],
            "drill": ["hip-hop.trap.drill"],
            "rnb": ["r-and-b"],
            "soul": ["r-and-b.soul"],
            "country": ["country"],
            "countrymusic": ["country"],
            "rock": ["rock"],
            "metal": ["rock.metal"],
            "punk": ["rock.punk"],
            "indie": ["rock.alternative.indie-rock", "pop.indie-pop"],
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
            "dancehall": ["caribbean.reggae.dancehall"],
            "jazz": ["jazz"],
            "classical": ["classical"],
            "lofi": ["electronic.downtempo.lo-fi-beats", "hip-hop.lo-fi-hip-hop"],
            "phonk": ["hip-hop.phonk"],
            # ... extend this as TikTok trends evolve
        }

        tiktok_hashtags = entity.metadata_json.get("tiktok_hashtags", [])
        scores = {}

        for tag in tiktok_hashtags:
            clean_tag = tag.lower().replace("#", "").replace(" ", "")
            matched_genres = HASHTAG_GENRE_MAP.get(clean_tag, [])
            for genre_id in matched_genres:
                scores[genre_id] = max(scores.get(genre_id, 0), 0.6)

        return scores


    async def _signal_neighbor_inference(self, entity) -> dict[str, float]:
        """
        SIGNAL 6: Look at what genres similar/related entities have.

        "Similar" defined by:
        - Spotify "related artists" API
        - Artists that frequently appear on the same playlists
        - Artists with similar audio feature profiles

        If 4 out of 5 related artists are classified as "electronic.house",
        this entity is probably also "electronic.house".
        """
        if hasattr(entity, 'spotify_id') and entity.spotify_id:
            related_artists = await self._get_related_artists(entity.spotify_id)
        else:
            related_artists = await self._get_playlist_neighbors(entity.id)

        if not related_artists:
            return {}

        genre_counts = {}
        for artist in related_artists:
            for genre_id in (artist.genres or []):
                genre_counts[genre_id] = genre_counts.get(genre_id, 0) + 1

        total = len(related_artists)
        return {genre_id: count / total for genre_id, count in genre_counts.items() if count / total > 0.2}


    # ══════════════════════════════════════════════
    # HIERARCHY RESOLUTION
    # ══════════════════════════════════════════════

    def _resolve_hierarchy(self, candidates: dict[str, float],
                           signal_details: dict[str, dict]) -> list[GenreCandidate]:
        """
        Take raw candidate scores and resolve hierarchy conflicts.

        Rules:
        1. PREFER SPECIFIC OVER BROAD: If both "electronic" (depth 0) and
           "electronic.house.tech-house" (depth 2) are candidates, prefer the specific one.
           The broad one only wins if the specific one has low confidence.

        2. PARENT CONSISTENCY: If "electronic.house.tech-house" is assigned,
           "electronic.house" and "electronic" are implicitly true too.
           Don't assign a child genre AND a conflicting sibling's parent.

        3. DEPTH BONUS: Genres at depth 2-3 get a small bonus because specific
           classifications are more useful than broad ones.

        4. CROSS-BRANCH LIMIT: An entity can belong to at most 3 root categories.
           (A track can be "pop + electronic" but probably not "pop + electronic + metal + country + jazz")
        """
        # Apply depth bonus
        adjusted = {}
        for genre_id, score in candidates.items():
            depth = self.taxonomy[genre_id]["depth"]
            depth_bonus = min(depth * 0.05, 0.15)  # +5% per depth level, max +15%
            adjusted[genre_id] = score + depth_bonus

        # Remove redundant ancestors if a descendant is present with higher score
        to_remove = set()
        for genre_id in adjusted:
            # Walk up the tree — if this genre's parent/grandparent is also a candidate
            # with a lower score, mark the ancestor for removal
            parent_id = self.taxonomy[genre_id].get("parent_id")
            while parent_id:
                if parent_id in adjusted and adjusted[parent_id] <= adjusted[genre_id]:
                    to_remove.add(parent_id)
                parent_id = self.taxonomy.get(parent_id, {}).get("parent_id")

        for r in to_remove:
            del adjusted[r]

        # Sort by score descending
        ranked = []
        for genre_id, score in sorted(adjusted.items(), key=lambda x: -x[1]):
            ranked.append(GenreCandidate(
                genre_id=genre_id,
                confidence=min(score, 1.0),
                signals=signal_details.get(genre_id, {}),
                depth=self.taxonomy[genre_id]["depth"],
            ))

        return ranked


    def _select_primary_genres(self, ranked: list[GenreCandidate]) -> list[GenreCandidate]:
        """
        Pick the top 1-3 genres to assign.

        Rules:
        - Always assign at least 1
        - Assign up to 3 if they all have confidence > 0.4
        - Max 3 different root categories
        - The 2nd and 3rd genre must have confidence >= 50% of the 1st
        """
        if not ranked:
            return []

        primary = [ranked[0]]
        top_score = ranked[0].confidence

        roots_used = {self.taxonomy[ranked[0].genre_id]["root_category"]}

        for candidate in ranked[1:]:
            if len(primary) >= 3:
                break
            if candidate.confidence < 0.4:
                break
            if candidate.confidence < top_score * 0.5:
                break

            root = self.taxonomy[candidate.genre_id]["root_category"]
            if len(roots_used) >= 3 and root not in roots_used:
                continue
            roots_used.add(root)

            # Don't add sibling at same depth under same parent
            # (e.g., don't assign both tech-house AND deep-house unless signals are strong)
            is_sibling_conflict = any(
                self.taxonomy[p.genre_id].get("parent_id") == self.taxonomy[candidate.genre_id].get("parent_id")
                and self.taxonomy[p.genre_id]["depth"] == candidate.depth
                for p in primary
            )
            if is_sibling_conflict and candidate.confidence < 0.7:
                continue

            primary.append(candidate)

        return primary


    def _assess_quality(self, ranked: list[GenreCandidate],
                        primary: list[GenreCandidate]) -> str:
        """
        How confident are we in this classification?

        HIGH: Top genre has confidence > 0.7 AND multiple signals agree
        MEDIUM: Top genre has confidence 0.4-0.7 OR signals disagree
        LOW: Top genre has confidence < 0.4 OR very few signals available
        """
        if not primary:
            return "low"

        top = primary[0]
        signal_count = len(top.signals)

        if top.confidence > 0.7 and signal_count >= 3:
            return "high"
        elif top.confidence > 0.4 and signal_count >= 2:
            return "medium"
        else:
            return "low"


    # ══════════════════════════════════════════════
    # HELPERS
    # ══════════════════════════════════════════════

    def _fuzzy_match_genre(self, label: str, threshold: float = 0.75) -> str | None:
        """
        Fuzzy match an unrecognized platform label to a SoundPulse genre name.
        Uses Levenshtein ratio. Returns best match genre_id or None.
        """
        from rapidfuzz import fuzz

        best_score = 0
        best_id = None

        for genre_id, genre in self.taxonomy.items():
            # Compare against genre name and all platform mappings
            candidates = [genre["name"].lower()] + \
                         [s.lower() for s in genre.get("spotify_genres", [])] + \
                         [s.lower() for s in genre.get("musicbrainz_tags", [])]

            for candidate in candidates:
                score = fuzz.ratio(label, candidate) / 100
                if score > best_score and score >= threshold:
                    best_score = score
                    best_id = genre_id

        return best_id


    async def _get_related_artists(self, spotify_id: str) -> list:
        """Fetch related artists from Spotify or from cached data."""
        # Implementation: call Spotify API GET /artists/{id}/related-artists
        # or look up cached relationships in DB
        pass

    async def _get_playlist_neighbors(self, entity_id: str) -> list:
        """Find artists that co-occur on the same playlists."""
        pass

    async def _get_entity_playlists(self, spotify_id: str) -> list[str]:
        """Look up which monitored playlists contain this track."""
        pass


# ══════════════════════════════════════════════
# INTEGRATION: When to classify
# ══════════════════════════════════════════════

"""
Genre classification runs at these points:

1. ON ENTITY CREATION
   When a new track/artist is first created via POST /trending,
   run classification with whatever signals are available.
   Initial classification may be "low" quality — that's OK.

2. ON METADATA ENRICHMENT
   When MusicBrainz enricher fills in additional metadata,
   re-run classification. Quality typically jumps to "medium".

3. ON SIGNIFICANT DATA UPDATE
   When an entity gets data from a NEW platform (e.g., first time
   appearing on TikTok), re-run classification. New signals may
   refine or change the genre assignment.

4. PERIODIC RE-CLASSIFICATION (weekly)
   Re-run classification for entities with "low" quality scores.
   As more data accumulates, quality should improve.

5. NEVER re-classify entities with "high" quality unless
   a human explicitly triggers it or new platform data arrives.
"""
```

---

## HANDLING EDGE CASES

### Track with NO genre signals at all
- Happens with brand new tracks that only have a name + artist
- Fallback: inherit artist's genres at 0.5 confidence
- If artist also has no genres: classify as root genre based on audio features alone
- If no audio features either: leave unclassified, queue for enrichment
- Mark classification_quality as "low"

### Track with CONFLICTING signals
- Spotify says "pop", audio features match "electronic", TikTok hashtags say "hip-hop"
- The scoring system handles this naturally — the genre with the most signal agreement wins
- If confidence spread is flat (many genres at ~0.4), mark quality as "medium" and assign top 2-3
- This often indicates the track genuinely spans genres (e.g., pop-electronic crossover)

### Genre that doesn't exist in taxonomy
- Spotify has ~1,500 genres, many are hyper-specific ("escape room", "german jazz-rap")
- If fuzzy matching fails (no match above 0.75 threshold): log the unmatched label
- Periodically review unmatched labels — they may indicate genres to add to the taxonomy
- This feeds into the genre governance process (proposing new genres)

### Artist vs Track classification
- Artists are classified first (more metadata usually available)
- Tracks inherit artist genres as one signal
- Tracks can diverge from artist genre (e.g., a hip-hop artist releases a pop ballad)
- Audio features are the tiebreaker for track-vs-artist genre divergence

---

## TESTING

```python
class TestGenreClassifier:
    def test_obvious_classification(self):
        """Track with clear Spotify genre labels → high confidence."""
        entity = make_track(spotify_genres=["tech house", "deep house"],
                           audio_features={"tempo": 125, "energy": 0.72})
        result = classifier.classify(entity)
        assert "electronic.house.tech-house" in result.primary_genres
        assert result.classification_quality == "high"

    def test_audio_only_classification(self):
        """Track with no labels but clear audio signature."""
        entity = make_track(audio_features={"tempo": 170, "energy": 0.9, "danceability": 0.6})
        result = classifier.classify(entity)
        # High tempo + high energy + moderate danceability → drum and bass or metal
        assert any("drum-and-bass" in g or "metal" in g for g in result.primary_genres)

    def test_cross_genre_track(self):
        """Track that genuinely spans genres gets multiple assignments."""
        entity = make_track(
            spotify_genres=["pop rap", "hip hop"],
            apple_music_genres=["Pop"],
            audio_features={"tempo": 95, "energy": 0.65, "valence": 0.7}
        )
        result = classifier.classify(entity)
        # Should have both pop and hip-hop related genres
        roots = {g.split(".")[0] for g in result.primary_genres}
        assert len(roots) >= 2

    def test_no_signals(self):
        """Track with zero metadata → low quality, falls back to artist."""
        entity = make_track(artist_genres=["rock.alternative.indie-rock"])
        result = classifier.classify(entity)
        assert "rock.alternative.indie-rock" in result.primary_genres
        assert result.classification_quality == "low"

    def test_conflicting_signals(self):
        """Conflicting platform labels → medium quality, multi-genre."""
        entity = make_track(
            spotify_genres=["pop"],
            musicbrainz_tags=["electronic"],
            tiktok_hashtags=["#edm", "#dance"]
        )
        result = classifier.classify(entity)
        assert result.classification_quality in ("medium", "low")
```

---

## DEPENDENCY

Add to `pyproject.toml`:
```
rapidfuzz>=3.0  # for fuzzy genre matching
```
