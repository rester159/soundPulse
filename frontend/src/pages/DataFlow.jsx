import { useRef, useEffect, useState, useCallback } from 'react'
import { Link } from 'react-router-dom'
import {
  GitBranch, RefreshCw, CheckCircle, XCircle, Clock,
  Database, Cpu, Globe, Monitor, Zap, ChevronDown, ChevronRight,
} from 'lucide-react'
import { useDataFlow } from '../hooks/useSoundPulse'

// ── Static field / detail definitions ────────────────────────────────────────

const NODE_DETAILS = {
  // ── Sources ──────────────────────────────────────────────────────────────
  chartmetric: {
    fields: [
      { name: 'title',              desc: 'Track name' },
      { name: 'artist_name',        desc: 'Artist name(s)' },
      { name: 'isrc',               desc: 'International Standard Recording Code' },
      { name: 'spotify_id',         desc: 'Spotify track ID (for audio enrichment)' },
      { name: 'chartmetric_id',     desc: 'Chartmetric internal track ID' },
      { name: 'rank',               desc: 'Chart position' },
      { name: 'spotify_popularity', desc: 'Spotify popularity score (0–100)' },
      { name: 'velocity',           desc: 'Rank change speed' },
      { name: 'current_plays',      desc: 'Stream count for the period' },
      { name: 'chart_type',         desc: 'regional / viral / plays / shazam / apple_music / tiktok' },
      { name: 'genres',             desc: 'Genre tags from Chartmetric' },
    ],
    note: 'Primary data backbone. Runs every 4h. Covers Spotify (regional, viral, plays), Shazam, Apple Music, and TikTok charts via a single authenticated API.',
  },
  spotify: {
    fields: [
      { name: 'title',              desc: 'Track name' },
      { name: 'artist_name',        desc: 'Artist(s)' },
      { name: 'spotify_id',         desc: 'Spotify track URI fragment' },
      { name: 'isrc',               desc: 'ISRC for cross-platform matching' },
      { name: 'rank',               desc: 'Position on the chart (1–200)' },
      { name: 'spotify_popularity', desc: 'Spotify popularity (0–100)' },
      { name: 'streams',            desc: 'Stream count (where available)' },
      { name: 'album_name',         desc: 'Album title' },
      { name: 'markets',            desc: 'Available market count' },
    ],
    note: 'Direct Spotify Web API. Falls back to Chartmetric if Spotify returns 0 records. Runs every 6h.',
  },
  spotify_audio: {
    fields: [
      { name: 'tempo',              desc: 'BPM (beats per minute)' },
      { name: 'energy',             desc: '0–1 intensity / loudness measure' },
      { name: 'danceability',       desc: '0–1 how suitable for dancing' },
      { name: 'valence',            desc: '0–1 musical positiveness / happiness' },
      { name: 'acousticness',       desc: '0–1 confidence of acoustic sound' },
      { name: 'instrumentalness',   desc: '0–1 predicts if no vocals' },
      { name: 'liveness',           desc: '0–1 presence of live audience' },
      { name: 'speechiness',        desc: '0–1 presence of spoken words' },
      { name: 'loudness',           desc: 'Average loudness in dBFS' },
      { name: 'key',                desc: 'Musical key (0=C, 1=C#, … 11=B)' },
      { name: 'mode',               desc: '1=major, 0=minor' },
      { name: 'duration_ms',        desc: 'Track length in milliseconds' },
      { name: 'time_signature',     desc: 'Beats per bar (typically 4)' },
      { name: 'audio_analysis',     desc: 'Sections, segments, beat/bar counts (top 50 tracks only)' },
    ],
    note: 'Enriches tracks that already have a spotify_id but no audio features. Runs daily at 5am UTC. Critical for blueprints and ML features — currently only ~6% of tracks have this data.',
  },
  shazam: {
    fields: [
      { name: 'title',         desc: 'Track name' },
      { name: 'artist_name',   desc: 'Artist name' },
      { name: 'shazam_id',     desc: 'Shazam track ID' },
      { name: 'rank',          desc: 'Position in Shazam trending chart' },
      { name: 'shazam_count',  desc: 'Shazam discovery count' },
      { name: 'genre_hint',    desc: 'Genre category used in query' },
    ],
    note: 'Uses the shazam-core RapidAPI. Queries 18 search terms across genres to surface trending tracks. Runs every 4h. Also available via Chartmetric /api/charts/shazam.',
  },
  apple_music: {
    fields: [
      { name: 'title',            desc: 'Track name' },
      { name: 'artist_name',      desc: 'Artist name(s)' },
      { name: 'apple_music_id',   desc: 'Apple Music track ID' },
      { name: 'isrc',             desc: 'ISRC for cross-platform matching' },
      { name: 'rank',             desc: 'Position on the storefront chart' },
      { name: 'storefront',       desc: 'Market / country code (e.g. us)' },
      { name: 'album_name',       desc: 'Album title' },
      { name: 'genre_names',      desc: 'Apple Music genre list' },
    ],
    note: 'Fetches Apple Music top songs chart via JWT (ES256) auth. US storefront only. Via Chartmetric: /api/charts/applemusic/tracks (fixed Apr 2026). Runs every 6h.',
  },
  musicbrainz: {
    fields: [
      { name: 'isrc',         desc: 'ISRC — primary cross-platform key' },
      { name: 'mbid',         desc: 'MusicBrainz Recording ID' },
      { name: 'release_date', desc: 'Official release date' },
      { name: 'genre_tags',   desc: 'Community-tagged genre list' },
      { name: 'artist_mbid',  desc: 'MusicBrainz Artist ID' },
      { name: 'country',      desc: 'Country of origin' },
      { name: 'duration_ms',  desc: 'Track duration from MusicBrainz' },
    ],
    note: 'Free enrichment source. No auth required. Looks up tracks by ISRC and fills in missing metadata (release_date, mbid, genre_tags). Runs daily at 2am UTC.',
  },
  radio: {
    fields: [
      { name: 'title',       desc: 'Track name (parsed from station metadata)' },
      { name: 'artist_name', desc: 'Artist name' },
      { name: 'station',     desc: 'Radio station name' },
      { name: 'play_count',  desc: 'Airplay frequency in the scrape window' },
      { name: 'format',      desc: 'Station format (CHR, AC, Hip-Hop, etc.)' },
    ],
    note: 'Scrapes public radio "now playing" feeds. Useful leading indicator — radio play often precedes streaming peaks. Runs daily at 6am UTC.',
  },

  // ── Database tables ───────────────────────────────────────────────────────
  trending_snapshots: {
    fields: [
      { name: 'id',               desc: 'UUID primary key' },
      { name: 'entity_type',      desc: '"track" or "artist"' },
      { name: 'entity_id',        desc: 'FK → tracks.id or artists.id' },
      { name: 'snapshot_date',    desc: 'Date of this data point (anchors ALL time-window queries)' },
      { name: 'platform',         desc: 'chartmetric / spotify / shazam / apple_music / radio / etc.' },
      { name: 'platform_rank',    desc: 'Position on source chart (nullable)' },
      { name: 'platform_score',   desc: 'Raw score from source (popularity, streams, rank-inverted)' },
      { name: 'normalized_score', desc: '0–100 score scaled uniformly across all platforms' },
      { name: 'velocity',         desc: 'Rate of rank change from the previous snapshot' },
      { name: 'composite_score',  desc: 'Weighted cross-platform score (computed at query time)' },
      { name: '── signals_json ──', desc: 'ALL raw source payload lives here as JSON' },
      { name: '  .chart_type',      desc: 'regional / viral / plays / shazam / apple_music / tiktok (Chartmetric)' },
      { name: '  .source_platform', desc: 'Which sub-source within Chartmetric (spotify, shazam, tiktok…)' },
      { name: '  .cm_track_id',     desc: 'Chartmetric internal track ID' },
      { name: '  .spotify_popularity', desc: 'Spotify popularity 0–100 (from Chartmetric)' },
      { name: '  .current_plays',   desc: 'Stream count for the period (from Chartmetric)' },
      { name: '  .velocity',        desc: 'Rank velocity as reported by Chartmetric' },
      { name: '  .source_rank',     desc: 'Chart position at source' },
      { name: '  .storefront',      desc: 'Apple Music market code (e.g. "us")' },
      { name: '  .shazam_count',    desc: 'Shazam discovery count' },
      { name: '  .genre_hint',      desc: 'Genre category used in Shazam query' },
      { name: '  .genres',          desc: 'Genre tags from Chartmetric (sparse — only ~102/2146 tracks)' },
      { name: '  .audio_features{}',desc: 'Spotify Audio: tempo, energy, danceability, valence, key, mode, etc.' },
      { name: '  .audio_analysis{}',desc: 'Spotify Audio: sections, segments, beat/bar counts (top 50 only)' },
      { name: '  .data_quality',    desc: '"live" / "aggregated" / "scraped" — which fallback tier delivered this' },
      { name: '  .data_source',     desc: 'Exact scraper class that produced this row' },
    ],
    note: '★ THIS is the central signal store. Every scrape appends new rows — one per track per platform per date. Velocity, plays, rank, genres, audio features — everything from every source is in signals_json here. trending_snapshots JOIN tracks gives you the full picture.',
  },
  tracks: {
    fields: [
      { name: '── IDENTITY ONLY ──', desc: 'tracks holds WHO a track is, not how it performs' },
      { name: 'id',              desc: 'UUID primary key — referenced by trending_snapshots.entity_id' },
      { name: 'title',           desc: 'Canonical track name (de-duplicated)' },
      { name: 'artist_id',       desc: 'FK → artists.id' },
      { name: 'isrc',            desc: 'Cross-platform match key (unique)' },
      { name: 'spotify_id',      desc: 'Spotify track ID (unique)' },
      { name: 'apple_music_id',  desc: 'Apple Music track ID (unique)' },
      { name: 'shazam_id',       desc: 'Shazam track ID (unique)' },
      { name: 'chartmetric_id',  desc: 'Chartmetric track ID (unique)' },
      { name: 'release_date',    desc: 'Official release date (from MusicBrainz enrichment)' },
      { name: 'genres[]',        desc: '⚠ Sparse array — prefer signals_json→genres in trending_snapshots' },
      { name: 'audio_features{}',desc: 'Permanent audio DNA from Spotify Audio scraper (tempo, energy, etc.) — only ~6% populated' },
      { name: 'metadata_json{}', desc: 'Extra fields from MusicBrainz (mbid, country, genre_tags)' },
    ],
    note: '⚠ tracks is an entity REGISTRY, not a signal store. It answers "what is this track?" — not "how is it performing?". All performance data (velocity, plays, rank, chart_type) lives in trending_snapshots.signals_json. audio_features here is the permanent Song DNA (static), while trending_snapshots holds the dynamic daily signals.',
  },
  predictions: {
    fields: [
      { name: 'id',               desc: 'UUID primary key' },
      { name: 'entity_id',        desc: 'Track or artist UUID' },
      { name: 'entity_type',      desc: '"track", "artist", or "genre"' },
      { name: 'horizon',          desc: 'Prediction window: "7d", "30d", "90d"' },
      { name: 'predicted_score',  desc: 'Breakout probability (0–1) from GBM model' },
      { name: 'confidence',       desc: 'Model confidence (0–1)' },
      { name: 'model_version',    desc: 'Semver of the model that made this prediction' },
      { name: 'features_json{}',  desc: 'Feature vector used at prediction time (for explainability)' },
      { name: 'predicted_at',     desc: 'Timestamp of prediction' },
      { name: 'resolved_at',      desc: 'When the prediction window closed (nullable)' },
      { name: 'actual_score',     desc: 'Real outcome score after resolution (nullable)' },
      { name: 'error',            desc: 'predicted_score – actual_score (nullable)' },
    ],
    note: 'Empty until model trains (needs ≥14 days of consecutive data, ETA mid-April 2026). Once populated, feeds the Model Validation page and Assistant context.',
  },
  backtest_results: {
    fields: [
      { name: 'id',               desc: 'String UUID primary key' },
      { name: 'run_id',           desc: 'Groups all rows from one backtest run' },
      { name: 'evaluation_date',  desc: 'The date being evaluated' },
      { name: 'entity_type',      desc: 'Track / artist filter (nullable = all)' },
      { name: 'genre_filter',     desc: 'Genre filter used in this run (nullable)' },
      { name: 'horizon',          desc: 'Prediction window evaluated ("7d" default)' },
      { name: 'mae',              desc: 'Mean Absolute Error for this period' },
      { name: 'rmse',             desc: 'Root Mean Squared Error' },
      { name: 'precision_score',  desc: 'Precision: of predicted breakouts, how many were real' },
      { name: 'recall_score',     desc: 'Recall: of actual breakouts, how many were caught' },
      { name: 'f1_score',         desc: 'Harmonic mean of precision and recall' },
      { name: 'auc_roc',          desc: 'Area Under ROC Curve' },
      { name: 'predicted_avg',    desc: 'Average predicted probability for charting' },
      { name: 'actual_rate',      desc: 'Actual breakout rate for charting' },
      { name: 'details_json{}',   desc: 'Per-entity predictions vs actuals (for drill-down)' },
    ],
    note: 'Populated by the daily backtest task (4:30am UTC) after model training. Used by the Model Validation page. Empty until first model trains.',
  },

  // ── Computed ──────────────────────────────────────────────────────────────
  composite_scores: {
    explanation: [
      { label: 'What it is',  text: 'A single 0–100 number representing a track\'s cross-platform momentum, used to rank trending lists.' },
      { label: 'Formula',     text: 'Weighted average of normalized_score across platforms: Chartmetric 35% + Spotify 30% + Shazam 20% + Apple Music 10% + Others 5%' },
      { label: 'When',        text: 'Computed on the fly at query time from the most recent snapshot per platform, within a MAX(snapshot_date) anchored window.' },
      { label: 'Where used',  text: 'Dashboard trending lists, Explore search results, TrendingCard score bar, SearchBar result ranking, Assistant context.' },
      { label: 'Weights',     text: 'Configurable via /admin/scoring page. Changing weights takes effect immediately on the next query — no re-scrape needed.' },
    ],
  },
  genre_opps: {
    explanation: [
      { label: 'What it is',  text: 'A score ranking music genres by how much opportunity they represent for a new release right now.' },
      { label: 'Formula',     text: 'opportunity = 0.4 × momentum + 0.4 × quality + 0.2 × (1 − saturation)' },
      { label: 'Momentum',    text: 'Average composite_score velocity across tracks in this genre over the last 60 days (anchored to MAX snapshot date).' },
      { label: 'Quality',     text: 'Average composite_score of top performers in the genre (proxy for audience engagement).' },
      { label: 'Saturation',  text: 'Fraction of top-200 tracks that already belong to this genre. High saturation = more competition.' },
      { label: 'Data gap',    text: 'Genre labels live in signals_json->>"genres" (raw Chartmetric strings), not in tracks.genres[]. Only ~102 of 2,146 tracks have genre labels there — causing many genres to show low scores.' },
      { label: 'Where used',  text: 'Song Lab left panel — genre list sorted by opportunity score.' },
    ],
  },
  blueprints: {
    explanation: [
      { label: 'What it is',  text: 'A "winning profile" for a genre: the aggregated Song DNA of the top-performing tracks in that genre over the last 60 days.' },
      { label: 'How built',   text: 'Query top tracks for the genre → average their audio features (tempo, energy, valence, danceability, key, mode) → identify common themes → translate into a model-specific text prompt.' },
      { label: 'LLM?',        text: 'No. All deterministic Python string templates — no LLM involved. Runs in <100ms per request.' },
      { label: 'Models',      text: 'Suno (natural language style text + [Verse]/[Chorus] lyrics skeleton), Udio (similar), SOUNDRAW (JSON params for tempo/energy/mood).' },
      { label: 'Limitation',  text: 'Without audio_features (only ~6% of tracks have them), the blueprint falls back to generic energy/mood language instead of specific BPM and key values.' },
      { label: 'Where used',  text: 'Song Lab right panel — Blueprint card + Generated Prompt text area.' },
    ],
  },
  ml_model: {
    explanation: [
      { label: 'What it is',   text: 'A GradientBoostingClassifier trained to predict whether a track will "break out" (composite_score > 70) within a future time horizon.' },
      { label: 'Algorithm',    text: 'sklearn GradientBoostingClassifier (100 estimators, max_depth=4, learning_rate=0.05). Also evaluates LogisticRegression and RandomForest; best F1 wins.' },
      { label: 'Features',     text: 'velocity, normalized_score, platform_rank, release_age_days, tempo, energy, danceability, valence, acousticness, genre_encoded, snapshot_count_7d, score_trend_7d' },
      { label: 'Label',        text: 'breakout=1 if composite_score > 70 at snapshot_date + horizon, else 0' },
      { label: 'Training',     text: 'Daily at 3am UTC via Celery Beat. Needs MIN_SAMPLES=30 and ≥2 snapshot dates. ETA for first run: mid-April 2026 (~14 days consecutive data).' },
      { label: 'Output',       text: 'predicted_score (breakout probability 0–1) + confidence per track → written to predictions table.' },
      { label: 'Path fix',     text: 'Train script path bug (relative vs absolute) fixed Apr 2026 — will run correctly on next 3am UTC cycle once data threshold is met.' },
    ],
  },
}

// ── Diagram topology ─────────────────────────────────────────────────────────

const COLUMNS = [
  { id: 'sources',  label: 'Data Sources', Icon: Globe,    color: '#60a5fa' },
  { id: 'workers',  label: 'Pipeline',     Icon: Cpu,      color: '#fb923c' },
  { id: 'storage',  label: 'Database',     Icon: Database, color: '#a78bfa' },
  { id: 'computed', label: 'Computed',     Icon: Zap,      color: '#34d399' },
  { id: 'frontend', label: 'UI Pages',     Icon: Monitor,  color: '#f472b6' },
]

const NODES = [
  { id: 'chartmetric',    col: 'sources', label: 'Chartmetric',    scraperKey: 'chartmetric',   expandable: true },
  { id: 'spotify',        col: 'sources', label: 'Spotify',        scraperKey: 'spotify',       expandable: true },
  { id: 'spotify_audio',  col: 'sources', label: 'Spotify Audio',  scraperKey: 'spotify_audio', expandable: true },
  { id: 'shazam',         col: 'sources', label: 'Shazam',         scraperKey: 'shazam',        expandable: true },
  { id: 'apple_music',    col: 'sources', label: 'Apple Music',    scraperKey: 'apple_music',   expandable: true },
  { id: 'musicbrainz',    col: 'sources', label: 'MusicBrainz',    scraperKey: 'musicbrainz',   expandable: true },
  { id: 'radio',          col: 'sources', label: 'Radio',          scraperKey: 'radio',         expandable: true },

  { id: 'celery_beat',   col: 'workers', label: 'Celery Beat',   subtitle: 'Cron scheduler' },
  { id: 'celery_worker', col: 'workers', label: 'Celery Worker', subtitle: 'Task executor' },

  { id: 'trending_snapshots', col: 'storage', label: 'trending_snapshots ★', tableKey: 'trending_snapshots', expandable: true },
  { id: 'tracks',             col: 'storage', label: 'tracks (registry)',    tableKey: 'tracks',             expandable: true },
  { id: 'predictions',        col: 'storage', label: 'predictions',         tableKey: 'predictions',        expandable: true },
  { id: 'backtest_results',   col: 'storage', label: 'backtest_results',    tableKey: 'backtest_results',   expandable: true },

  { id: 'composite_scores', col: 'computed', label: 'Composite Scores',    expandable: true },
  { id: 'genre_opps',       col: 'computed', label: 'Genre Opportunities', expandable: true },
  { id: 'blueprints',       col: 'computed', label: 'Blueprints',          expandable: true },
  { id: 'ml_model',         col: 'computed', label: 'ML Model',            expandable: true },

  { id: 'dashboard', col: 'frontend', label: 'Dashboard',        path: '/' },
  { id: 'explore',   col: 'frontend', label: 'Explore',          path: '/explore' },
  { id: 'song_lab',  col: 'frontend', label: 'Song Lab',         path: '/song-lab' },
  { id: 'model_val', col: 'frontend', label: 'Model Validation', path: '/model-validation' },
  { id: 'assistant', col: 'frontend', label: 'Assistant',        path: null },
]

const EDGES = [
  { from: 'chartmetric',   to: 'celery_worker' },
  { from: 'spotify',       to: 'celery_worker' },
  { from: 'spotify_audio', to: 'celery_worker' },
  { from: 'shazam',        to: 'celery_worker' },
  { from: 'apple_music',   to: 'celery_worker' },
  { from: 'musicbrainz',   to: 'celery_worker' },
  { from: 'radio',         to: 'celery_worker' },
  { from: 'celery_beat',   to: 'celery_worker' },
  { from: 'celery_worker', to: 'trending_snapshots' },
  { from: 'celery_worker', to: 'tracks' },
  { from: 'celery_worker', to: 'predictions' },
  { from: 'celery_worker', to: 'backtest_results' },
  { from: 'trending_snapshots', to: 'composite_scores' },
  { from: 'trending_snapshots', to: 'genre_opps' },
  { from: 'trending_snapshots', to: 'blueprints' },
  { from: 'trending_snapshots', to: 'ml_model' },
  { from: 'tracks',             to: 'blueprints' },
  { from: 'tracks',             to: 'ml_model' },
  { from: 'predictions',        to: 'ml_model' },
  { from: 'composite_scores', to: 'dashboard' },
  { from: 'composite_scores', to: 'explore' },
  { from: 'composite_scores', to: 'assistant' },
  { from: 'genre_opps',       to: 'song_lab' },
  { from: 'genre_opps',       to: 'assistant' },
  { from: 'blueprints',       to: 'song_lab' },
  { from: 'ml_model',         to: 'model_val' },
  { from: 'ml_model',         to: 'assistant' },
]

// ── Helpers ───────────────────────────────────────────────────────────────────

function relativeTime(isoStr) {
  if (!isoStr) return null
  const diff = Math.floor((Date.now() - new Date(isoStr)) / 1000)
  if (diff < 60)   return `${diff}s ago`
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
  return `${Math.floor(diff / 86400)}d ago`
}

function fmtNum(n) {
  if (n == null) return '—'
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M'
  if (n >= 1_000)     return (n / 1_000).toFixed(1) + 'k'
  return String(n)
}

function statusColor(status) {
  if (status === 'success') return '#34d399'
  if (status === 'error')   return '#f87171'
  if (status === 'running') return '#60a5fa'
  return '#52525b'
}

// ── Expandable detail panels ──────────────────────────────────────────────────

function FieldList({ fields }) {
  return (
    <div className="mt-2 space-y-1 border-t border-zinc-800 pt-2">
      {fields.map(f => (
        <div key={f.name} className="flex gap-2">
          <span className="font-mono text-[10px] text-violet-400 shrink-0 min-w-[120px]">{f.name}</span>
          <span className="text-[10px] text-zinc-500 leading-tight">{f.desc}</span>
        </div>
      ))}
    </div>
  )
}

function ExplanationList({ items }) {
  return (
    <div className="mt-2 space-y-1.5 border-t border-zinc-800 pt-2">
      {items.map(item => (
        <div key={item.label}>
          <span className="text-[10px] font-semibold text-zinc-400">{item.label}: </span>
          <span className="text-[10px] text-zinc-500">{item.text}</span>
        </div>
      ))}
    </div>
  )
}

// ── Main node card ────────────────────────────────────────────────────────────

function DiagramNode({ node, nodeRef, live, isExpanded, onToggle }) {
  const colDef  = COLUMNS.find(c => c.id === node.col)
  const accent  = colDef?.color || '#71717a'
  const details = NODE_DETAILS[node.id]

  // Scraper status badge
  const scraperData = node.scraperKey && live?.scrapers
    ? live.scrapers.find(s => s.id === node.scraperKey)
    : null

  const tableData = node.tableKey && live?.tables
    ? live.tables[node.tableKey]
    : null

  // Record count for the label parenthetical
  let recordCount = null
  if (scraperData?.last_record_count != null) recordCount = scraperData.last_record_count
  if (tableData?.total_rows != null) recordCount = tableData.total_rows

  const handleClick = node.expandable && details ? onToggle : undefined

  return (
    <div
      ref={nodeRef}
      onClick={handleClick}
      className={`rounded-lg border bg-zinc-900 px-3 py-2 mb-2 ${node.expandable && details ? 'cursor-pointer select-none' : ''}`}
      style={{ borderColor: isExpanded ? accent : `${accent}30` }}
    >
      {/* Header row */}
      <div className="flex items-center justify-between gap-1">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1 flex-wrap">
            <span className="text-xs font-medium text-zinc-200 leading-tight">{node.label}</span>
            {recordCount != null && (
              <span className="text-[10px] text-zinc-500">({fmtNum(recordCount)})</span>
            )}
          </div>

          {/* Sub-status line */}
          {scraperData && (
            <div className="flex items-center gap-1.5 mt-0.5">
              <div className="w-1.5 h-1.5 rounded-full shrink-0" style={{ backgroundColor: statusColor(scraperData.last_status) }} />
              <span className="text-[10px]" style={{ color: statusColor(scraperData.last_status) }}>
                {scraperData.last_status || 'never run'}
              </span>
              {scraperData.last_run_at && (
                <span className="text-[10px] text-zinc-600">{relativeTime(scraperData.last_run_at)}</span>
              )}
            </div>
          )}

          {tableData && !scraperData && (
            <div className="flex items-center gap-1.5 mt-0.5">
              <div className="w-1.5 h-1.5 rounded-full shrink-0"
                style={{ backgroundColor: (tableData.total_rows || 0) > 0 ? '#34d399' : '#52525b' }} />
              <span className={`text-[10px] ${(tableData.total_rows || 0) > 0 ? 'text-zinc-300' : 'text-zinc-600'}`}>
                {fmtNum(tableData.total_rows)} rows
              </span>
              {tableData.latest_date && (
                <span className="text-[10px] text-zinc-600">· {tableData.latest_date}</span>
              )}
              {tableData.distinct_dates != null && (
                <span className="text-[10px] text-zinc-600">· {tableData.distinct_dates} dates</span>
              )}
            </div>
          )}

          {node.col === 'workers' && (
            <div className="text-[10px] text-zinc-500 mt-0.5">{node.subtitle}</div>
          )}

          {node.col === 'computed' && !isExpanded && (
            <div className="text-[10px] text-zinc-600 mt-0.5">click to expand</div>
          )}

          {node.col === 'frontend' && node.path && (
            <Link
              to={node.path}
              onClick={e => e.stopPropagation()}
              className="text-[10px] text-violet-400 hover:text-violet-300 mt-0.5 block"
            >
              open →
            </Link>
          )}

          {/* Tracks audio feature coverage sub-note */}
          {node.tableKey === 'tracks' && live?.tables?.tracks && (
            <div className="text-[10px] text-zinc-600 mt-0.5">
              {fmtNum(live.tables.tracks.with_audio_features)} / {fmtNum(live.tables.tracks.total_rows)} with audio
            </div>
          )}
        </div>

        {/* Chevron */}
        {node.expandable && details && (
          <div className="shrink-0 ml-1">
            {isExpanded
              ? <ChevronDown size={11} style={{ color: accent }} />
              : <ChevronRight size={11} className="text-zinc-600" />
            }
          </div>
        )}
      </div>

      {/* Expanded content */}
      {isExpanded && details && (
        <div>
          {details.note && (
            <p className="text-[10px] text-zinc-500 mt-1.5 italic leading-snug">{details.note}</p>
          )}
          {details.fields && <FieldList fields={details.fields} />}
          {details.explanation && <ExplanationList items={details.explanation} />}
        </div>
      )}
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function DataFlow() {
  const { data: rawData, isLoading, refetch, dataUpdatedAt } = useDataFlow()
  const live = rawData?.data?.data

  const containerRef = useRef(null)
  const nodeRefs     = useRef({})
  const [svgLines, setSvgLines]     = useState([])
  const [svgSize, setSvgSize]       = useState({ w: 0, h: 0 })
  const [expanded, setExpanded]     = useState(new Set())

  const toggleNode = useCallback((id) => {
    setExpanded(prev => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }, [])

  const recalcLines = useCallback(() => {
    if (!containerRef.current) return
    const cr = containerRef.current.getBoundingClientRect()
    setSvgSize({ w: cr.width, h: cr.height })

    const lines = EDGES.map(edge => {
      const fromEl = nodeRefs.current[edge.from]
      const toEl   = nodeRefs.current[edge.to]
      if (!fromEl || !toEl) return null
      const fr = fromEl.getBoundingClientRect()
      const tr = toEl.getBoundingClientRect()
      const x1 = fr.right  - cr.left
      const y1 = fr.top    + fr.height / 2 - cr.top
      const x2 = tr.left   - cr.left
      const y2 = tr.top    + tr.height / 2 - cr.top
      const cx = (x1 + x2) / 2
      const d  = `M${x1},${y1} C${cx},${y1} ${cx},${y2} ${x2},${y2}`
      const fromNode = NODES.find(n => n.id === edge.from)
      const fromCol  = COLUMNS.find(c => c.id === fromNode?.col)
      const color    = fromCol ? fromCol.color + '28' : '#ffffff12'
      return { d, color, key: `${edge.from}-${edge.to}` }
    }).filter(Boolean)

    setSvgLines(lines)
  }, [])

  // Recalc after expansions and after data loads
  useEffect(() => {
    const t = setTimeout(recalcLines, 30)
    return () => clearTimeout(t)
  }, [recalcLines, live, expanded])

  useEffect(() => {
    const ro = new ResizeObserver(recalcLines)
    if (containerRef.current) ro.observe(containerRef.current)
    return () => ro.disconnect()
  }, [recalcLines])

  const nodesByCol = {}
  COLUMNS.forEach(c => { nodesByCol[c.id] = NODES.filter(n => n.col === c.id) })

  const lastUpdated = dataUpdatedAt ? relativeTime(new Date(dataUpdatedAt).toISOString()) : null

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <GitBranch size={28} className="text-violet-400" />
          <div>
            <h1 className="text-2xl font-bold text-zinc-100">Data Pipeline</h1>
            <p className="text-sm text-zinc-500">Live architecture — click any node to expand fields &amp; details</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {lastUpdated && <span className="text-xs text-zinc-500">Updated {lastUpdated}</span>}
          <button
            onClick={() => refetch()}
            className="flex items-center gap-2 px-3 py-1.5 bg-zinc-800 hover:bg-zinc-700 rounded-lg text-sm text-zinc-300 transition-colors"
          >
            <RefreshCw size={13} className={isLoading ? 'animate-spin' : ''} />
            Refresh
          </button>
        </div>
      </div>

      {/* Coverage strip */}
      {live?.coverage && (
        <div className="flex gap-3 flex-wrap">
          {[
            { label: 'Audio Features', value: `${live.coverage.audio_features_pct}%`,    ok: live.coverage.audio_features_pct > 50 },
            { label: 'Predictions',    value: `${live.coverage.prediction_coverage_pct}%`, ok: live.coverage.prediction_coverage_pct > 0 },
            { label: 'Model Trained',  value: live.coverage.model_trained ? 'Yes' : 'No', ok: live.coverage.model_trained },
            { label: 'Snapshot Dates', value: String(live.tables?.trending_snapshots?.distinct_dates ?? '—'), ok: (live.tables?.trending_snapshots?.distinct_dates || 0) >= 14 },
          ].map(({ label, value, ok }) => (
            <div key={label} className="flex items-center gap-2 bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-1.5">
              {ok
                ? <CheckCircle size={12} className="text-emerald-400 shrink-0" />
                : <XCircle    size={12} className="text-rose-400 shrink-0" />
              }
              <span className="text-xs text-zinc-400">{label}:</span>
              <span className={`text-xs font-semibold ${ok ? 'text-emerald-400' : 'text-rose-400'}`}>{value}</span>
            </div>
          ))}
        </div>
      )}

      {/* Diagram */}
      <div
        ref={containerRef}
        className="relative rounded-xl border border-zinc-800 bg-zinc-950 p-6 overflow-x-auto"
      >
        {/* SVG edge overlay */}
        <svg
          className="absolute inset-0 pointer-events-none"
          width={svgSize.w}
          height={svgSize.h}
          style={{ overflow: 'visible' }}
        >
          {svgLines.map(line => (
            <path
              key={line.key}
              d={line.d}
              stroke={line.color}
              strokeWidth={1.5}
              fill="none"
              strokeLinecap="round"
            />
          ))}
        </svg>

        {/* Column grid */}
        <div
          className="relative z-10 grid gap-6"
          style={{ gridTemplateColumns: `repeat(${COLUMNS.length}, minmax(170px, 1fr))` }}
        >
          {COLUMNS.map(col => (
            <div key={col.id}>
              {/* Column header */}
              <div className="flex items-center gap-1.5 mb-3 px-1">
                <col.Icon size={13} style={{ color: col.color }} />
                <span className="text-xs font-semibold uppercase tracking-wider" style={{ color: col.color }}>
                  {col.label}
                </span>
              </div>

              {nodesByCol[col.id].map(node => (
                <DiagramNode
                  key={node.id}
                  node={node}
                  nodeRef={el => { nodeRefs.current[node.id] = el }}
                  live={live}
                  isExpanded={expanded.has(node.id)}
                  onToggle={() => toggleNode(node.id)}
                />
              ))}
            </div>
          ))}
        </div>
      </div>

      {/* Architecture callout */}
      <div className="rounded-lg border border-amber-500/20 bg-amber-500/5 p-4">
        <div className="flex gap-3">
          <div className="text-amber-400 text-lg leading-none mt-0.5">⚠</div>
          <div>
            <div className="text-sm font-semibold text-amber-300 mb-1">Two-table pattern — why signals aren't all in <code className="font-mono text-xs">tracks</code></div>
            <div className="text-xs text-zinc-400 space-y-1">
              <p>
                <span className="text-zinc-300 font-medium">trending_snapshots</span> is the signal store.
                Every scrape appends a new row per track per platform per day. All performance data — velocity, current_plays, rank, chart_type, genres, audio features — lands in <code className="font-mono text-[10px] bg-zinc-800 px-1 rounded">signals_json</code> here.
                This is a <span className="text-zinc-300">time-series</span> design: you can query "how did this track move on Chartmetric over the last 30 days?" by reading multiple rows.
              </p>
              <p>
                <span className="text-zinc-300 font-medium">tracks</span> is the entity registry.
                It only stores identity — canonical name, platform IDs (spotify_id, apple_music_id…), and <span className="italic">permanent</span> Song DNA (audio_features from Spotify Audio scraper, which is static once set).
                It does <span className="underline">not</span> store daily performance signals.
              </p>
              <p>
                The full picture = <code className="font-mono text-[10px] bg-zinc-800 px-1 rounded">trending_snapshots JOIN tracks ON entity_id = tracks.id</code> — you get identity + all historical signals in one query.
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Platform breakdown */}
      {live?.tables?.trending_snapshots?.platforms && Object.keys(live.tables.trending_snapshots.platforms).length > 0 && (
        <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-4">
          <h3 className="text-sm font-semibold text-zinc-300 mb-3 flex items-center gap-2">
            <Database size={14} className="text-violet-400" />
            Snapshots by Platform
          </h3>
          <div className="flex flex-wrap gap-2">
            {Object.entries(live.tables.trending_snapshots.platforms)
              .sort(([, a], [, b]) => b - a)
              .map(([platform, count]) => (
                <div key={platform} className="flex items-center gap-2 bg-zinc-800/50 rounded-lg px-3 py-1.5">
                  <span className="text-xs font-medium text-zinc-300">{platform}</span>
                  <span className="text-xs text-zinc-500">{fmtNum(count)}</span>
                </div>
              ))}
          </div>
        </div>
      )}

      {/* Scraper detail table */}
      {live?.scrapers && live.scrapers.length > 0 && (
        <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-4">
          <h3 className="text-sm font-semibold text-zinc-300 mb-3 flex items-center gap-2">
            <Clock size={14} className="text-orange-400" />
            Scraper Status Details
          </h3>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-zinc-500 border-b border-zinc-800">
                  <th className="text-left py-1.5 px-2">Scraper</th>
                  <th className="text-center py-1.5 px-2">On</th>
                  <th className="text-left py-1.5 px-2">Status</th>
                  <th className="text-left py-1.5 px-2">Last Run</th>
                  <th className="text-right py-1.5 px-2">Records</th>
                  <th className="text-left py-1.5 px-2">Last Error</th>
                </tr>
              </thead>
              <tbody>
                {live.scrapers.map(s => (
                  <tr key={s.id} className="border-b border-zinc-800/40 hover:bg-zinc-800/20">
                    <td className="py-1.5 px-2 font-mono text-zinc-300">{s.id}</td>
                    <td className="py-1.5 px-2 text-center">
                      <span className={`inline-block w-1.5 h-1.5 rounded-full ${s.enabled ? 'bg-emerald-400' : 'bg-zinc-600'}`} />
                    </td>
                    <td className="py-1.5 px-2" style={{ color: statusColor(s.last_status) }}>
                      {s.last_status || 'never'}
                    </td>
                    <td className="py-1.5 px-2 text-zinc-500">{relativeTime(s.last_run_at) || '—'}</td>
                    <td className="py-1.5 px-2 text-right text-zinc-400">
                      {s.last_record_count != null ? fmtNum(s.last_record_count) : '—'}
                    </td>
                    <td className="py-1.5 px-2 text-zinc-600 max-w-xs truncate">{s.last_error || ''}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {isLoading && !live && (
        <div className="text-center py-12 text-zinc-500 text-sm">Loading pipeline data…</div>
      )}
    </div>
  )
}
