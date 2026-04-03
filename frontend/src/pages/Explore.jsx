import { useState } from 'react'
import { useTrending, useGenres } from '../hooks/useSoundPulse'
import SearchBar from '../components/SearchBar'
import TrendingTable from '../components/TrendingTable'
import GenreTree from '../components/GenreTree'
import SparkLine from '../components/SparkLine'
import PredictionCard from '../components/PredictionCard'
import { formatScore } from '../utils/formatters'

const ENTITY_TYPES = [
  { value: 'track', label: 'Tracks' },
  { value: 'artist', label: 'Artists' },
  { value: 'all', label: 'All' },
]

const TIME_RANGES = [
  { value: '24h', label: '24h' },
  { value: '7d', label: '7d' },
  { value: '30d', label: '30d' },
  { value: '90d', label: '90d' },
]

const PLATFORM_COLORS = {
  spotify: '#1DB954',
  apple_music: '#FC3C44',
  tidal: '#000000',
  youtube: '#FF0000',
  soundcloud: '#FF5500',
  shazam: '#08f',
  deezer: '#A238FF',
}

const PLATFORM_LABELS = {
  spotify: 'Spotify',
  apple_music: 'Apple Music',
  tidal: 'Tidal',
  youtube: 'YouTube',
  soundcloud: 'SoundCloud',
  shazam: 'Shazam',
  deezer: 'Deezer',
}

export default function Explore() {
  const [entityType, setEntityType] = useState('track')
  const [timeRange, setTimeRange] = useState('7d')
  const [selectedGenre, setSelectedGenre] = useState(null)
  const [expandedItem, setExpandedItem] = useState(null)

  const trendingParams = {
    entity_type: entityType === 'all' ? undefined : entityType,
    time_range: timeRange,
    genre: selectedGenre?.id || selectedGenre?.name || undefined,
    limit: 30,
  }

  // Only enable trending when entity_type is set (hook requires it)
  const enableTrending = entityType !== 'all'
  const {
    data: trendingResult,
    isLoading: trendingLoading,
  } = useTrending(enableTrending ? trendingParams : { entity_type: entityType, time_range: timeRange, genre: trendingParams.genre, limit: 30 })

  const { data: genresResult, isLoading: genresLoading } = useGenres({})

  const trendingItems = trendingResult?.data?.data || []
  const genreTree = genresResult?.data?.data || []

  function handleSearchSelect(item) {
    setExpandedItem(item)
  }

  function handleGenreSelect(genre) {
    if (selectedGenre?.id === genre.id || selectedGenre?.name === genre.name) {
      setSelectedGenre(null)
    } else {
      setSelectedGenre(genre)
    }
  }

  function handleRowClick(item) {
    const itemId = item.entity?.id || item.id || item.entity?.name
    const expandedId =
      expandedItem?.entity?.id || expandedItem?.id || expandedItem?.entity?.name

    if (expandedId && expandedId === itemId) {
      setExpandedItem(null)
    } else {
      setExpandedItem(item)
    }
  }

  return (
    <div className="space-y-6">
      {/* Header with search */}
      <div>
        <h1 className="text-2xl font-semibold text-zinc-100 tracking-tight mb-4">
          Explore
        </h1>
        <SearchBar onSelect={handleSearchSelect} />
      </div>

      {/* Two-column layout */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Left sidebar: Filters */}
        <div className="lg:col-span-1 space-y-5">
          {/* Entity Type */}
          <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-4">
            <h3 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-3">
              Entity Type
            </h3>
            <div className="space-y-1">
              {ENTITY_TYPES.map((type) => (
                <label
                  key={type.value}
                  className={`flex items-center gap-2.5 px-2.5 py-2 rounded-md cursor-pointer transition-colors duration-150 ${
                    entityType === type.value
                      ? 'bg-violet-500/10 text-violet-400'
                      : 'text-zinc-300 hover:bg-zinc-800/60'
                  }`}
                >
                  <input
                    type="radio"
                    name="entityType"
                    value={type.value}
                    checked={entityType === type.value}
                    onChange={() => setEntityType(type.value)}
                    className="sr-only"
                  />
                  <span
                    className={`w-3.5 h-3.5 rounded-full border-2 flex items-center justify-center transition-colors duration-150 ${
                      entityType === type.value
                        ? 'border-violet-500'
                        : 'border-zinc-600'
                    }`}
                  >
                    {entityType === type.value && (
                      <span className="w-1.5 h-1.5 rounded-full bg-violet-500" />
                    )}
                  </span>
                  <span className="text-sm">{type.label}</span>
                </label>
              ))}
            </div>
          </div>

          {/* Time Range */}
          <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-4">
            <h3 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-3">
              Time Range
            </h3>
            <div className="flex flex-wrap gap-1.5">
              {TIME_RANGES.map((range) => (
                <button
                  key={range.value}
                  onClick={() => setTimeRange(range.value)}
                  className={`px-3 py-1.5 rounded-md text-xs font-medium transition-all duration-150 ${
                    timeRange === range.value
                      ? 'bg-violet-600 text-white shadow-sm'
                      : 'bg-zinc-800 text-zinc-400 hover:text-zinc-200 hover:bg-zinc-700'
                  }`}
                >
                  {range.label}
                </button>
              ))}
            </div>
          </div>

          {/* Genre Tree */}
          <div className="rounded-lg border border-zinc-800 bg-zinc-900 overflow-hidden">
            <div className="px-4 py-3 border-b border-zinc-800">
              <div className="flex items-center justify-between">
                <h3 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">
                  Genres
                </h3>
                {selectedGenre && (
                  <button
                    onClick={() => setSelectedGenre(null)}
                    className="text-[10px] text-violet-400 hover:text-violet-300 transition-colors"
                  >
                    Clear
                  </button>
                )}
              </div>
            </div>
            <div className="max-h-72 overflow-y-auto">
              <GenreTree
                genres={genreTree}
                selectedId={selectedGenre?.id || selectedGenre?.name}
                onSelect={handleGenreSelect}
                isLoading={genresLoading}
              />
            </div>
          </div>
        </div>

        {/* Right: Results */}
        <div className="lg:col-span-3 space-y-4">
          {/* Active filters summary */}
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-xs text-zinc-500">Showing:</span>
            <span className="text-xs font-medium px-2 py-0.5 rounded bg-zinc-800 text-zinc-300">
              {ENTITY_TYPES.find((t) => t.value === entityType)?.label}
            </span>
            <span className="text-xs font-medium px-2 py-0.5 rounded bg-zinc-800 text-zinc-300">
              {TIME_RANGES.find((t) => t.value === timeRange)?.label}
            </span>
            {selectedGenre && (
              <span className="text-xs font-medium px-2 py-0.5 rounded bg-violet-500/15 text-violet-400">
                {selectedGenre.name || selectedGenre.label}
              </span>
            )}
          </div>

          {/* Results table */}
          <TrendingTable
            items={trendingItems}
            isLoading={trendingLoading}
            onRowClick={handleRowClick}
          />

          {/* Expanded detail panel */}
          {expandedItem && (
            <ExpandedDetail item={expandedItem} onClose={() => setExpandedItem(null)} />
          )}
        </div>
      </div>
    </div>
  )
}

function ExpandedDetail({ item, onClose }) {
  const entity = item.entity || item
  const scores = item.scores || {}
  const sparkline = item.sparkline_7d || []
  const platforms = Object.keys(scores).filter(
    (k) => k !== 'composite' && k !== 'velocity'
  )
  const prediction = item.prediction || null

  return (
    <div className="rounded-lg border border-violet-500/30 bg-zinc-900 p-5 space-y-4 animate-fade-in">
      <style>{`
        @keyframes fadeIn {
          from { opacity: 0; transform: translateY(-4px); }
          to { opacity: 1; transform: translateY(0); }
        }
        .animate-fade-in {
          animation: fadeIn 150ms ease-out forwards;
        }
      `}</style>

      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h3 className="text-lg font-semibold text-zinc-100">
            {entity.name || entity.title || 'Unknown'}
          </h3>
          {entity.artist && (
            <p className="text-sm text-zinc-400 mt-0.5">{entity.artist}</p>
          )}
        </div>
        <button
          onClick={onClose}
          className="text-zinc-500 hover:text-zinc-300 transition-colors text-xs px-2 py-1 rounded hover:bg-zinc-800"
        >
          Close
        </button>
      </div>

      {/* Per-platform scores */}
      {platforms.length > 0 && (
        <div>
          <h4 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-3">
            Platform Scores
          </h4>
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
            {platforms.map((platform) => {
              const score = scores[platform]
              const platformScore =
                typeof score === 'object' ? score.score ?? score.value ?? 0 : score ?? 0

              return (
                <div
                  key={platform}
                  className="rounded-lg border border-zinc-800 bg-zinc-800/40 p-3"
                >
                  <div className="flex items-center gap-2 mb-2">
                    <span
                      className="w-2 h-2 rounded-full"
                      style={{
                        backgroundColor: PLATFORM_COLORS[platform] || '#71717a',
                      }}
                    />
                    <span className="text-xs font-medium text-zinc-300">
                      {PLATFORM_LABELS[platform] || platform}
                    </span>
                  </div>
                  <div className="font-mono text-lg font-semibold text-zinc-100">
                    {formatScore(platformScore)}
                  </div>
                  <div className="w-full h-1 bg-zinc-700 rounded-full mt-2 overflow-hidden">
                    <div
                      className="h-full rounded-full transition-all duration-300"
                      style={{
                        width: `${Math.min(100, Math.max(0, platformScore))}%`,
                        backgroundColor: PLATFORM_COLORS[platform] || '#71717a',
                      }}
                    />
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Sparkline preview */}
      {sparkline.length > 1 && (
        <div>
          <h4 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-2">
            7-Day Trend
          </h4>
          <SparkLine data={sparkline} width={300} height={48} />
        </div>
      )}

      {/* Prediction if available */}
      {prediction && (
        <div>
          <h4 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-2">
            Prediction
          </h4>
          <div className="max-w-sm">
            <PredictionCard prediction={prediction} />
          </div>
        </div>
      )}
    </div>
  )
}
