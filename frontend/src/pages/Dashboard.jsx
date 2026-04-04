import { useState } from 'react'
import { useTrending, usePredictions, useGenres } from '../hooks/useSoundPulse'
import FreshnessIndicator from '../components/FreshnessIndicator'
import TrendingTable from '../components/TrendingTable'
import PredictionCard from '../components/PredictionCard'
import GenreHeatmap from '../components/GenreHeatmap'

const ENTITY_TYPES = [
  { value: 'track', label: 'Tracks' },
  { value: 'artist', label: 'Artists' },
]

export default function Dashboard() {
  const [entityType, setEntityType] = useState('track')

  const {
    data: trendingResult,
    isLoading: trendingLoading,
    dataUpdatedAt: trendingUpdatedAt,
  } = useTrending({ entity_type: entityType, limit: 20, time_range: '30d' })

  const { data: predictionsResult, isLoading: predictionsLoading } =
    usePredictions({ limit: 5 })

  const { data: genresResult, isLoading: genresLoading } = useGenres({
    root: true,
  })

  // API shape: makeRequest wraps response → { data: <api-body>, status, ... }
  // API body shape: { data: [...], meta: {...} }  or { data: { genres: [...], ... } }
  const trendingItems = trendingResult?.data?.data || []
  const predictions = predictionsResult?.data?.data || []
  // Genres endpoint returns { data: { genres: [...tree], total_genres: N } }
  const genres = genresResult?.data?.data?.genres || []
  const updatedAt = trendingUpdatedAt ? new Date(trendingUpdatedAt).toISOString() : null

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <h1 className="text-2xl font-semibold text-zinc-100 tracking-tight">
          Dashboard
        </h1>
        <FreshnessIndicator updatedAt={updatedAt} />
      </div>

      {/* Main content: two columns */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        {/* Left: Trending Now (takes 2/3 width on xl) */}
        <div className="xl:col-span-2 rounded-lg border border-zinc-800 bg-zinc-900 overflow-hidden">
          {/* Panel header with toggle */}
          <div className="flex items-center justify-between px-5 py-4 border-b border-zinc-800">
            <h2 className="text-base font-semibold text-zinc-100">
              Trending Now
            </h2>
            <div className="flex items-center bg-zinc-800 rounded-lg p-0.5">
              {ENTITY_TYPES.map((type) => (
                <button
                  key={type.value}
                  onClick={() => setEntityType(type.value)}
                  className={`px-3 py-1.5 rounded-md text-xs font-medium transition-all duration-150 ${
                    entityType === type.value
                      ? 'bg-violet-600 text-white shadow-sm'
                      : 'text-zinc-400 hover:text-zinc-200'
                  }`}
                >
                  {type.label}
                </button>
              ))}
            </div>
          </div>

          {/* Table */}
          <div className="p-4">
            <TrendingTable
              items={trendingItems}
              isLoading={trendingLoading}
              onRowClick={(item) => {
                console.log('Trending item clicked:', item)
              }}
            />
          </div>
        </div>

        {/* Right: Breakout Predictions */}
        <div className="rounded-lg border border-zinc-800 bg-zinc-900 overflow-hidden">
          <div className="px-5 py-4 border-b border-zinc-800">
            <h2 className="text-base font-semibold text-zinc-100">
              Breakout Predictions
            </h2>
          </div>
          <div className="p-4 space-y-3">
            {predictionsLoading
              ? Array.from({ length: 5 }).map((_, i) => (
                  <div
                    key={i}
                    className="rounded-lg border border-zinc-800 bg-zinc-900 p-4 space-y-3"
                  >
                    <div className="flex items-start justify-between">
                      <div className="space-y-1.5">
                        <div className="h-4 w-28 bg-zinc-800 rounded skeleton" />
                        <div className="h-3 w-20 bg-zinc-800 rounded skeleton" />
                      </div>
                      <div className="h-5 w-14 bg-zinc-800 rounded skeleton" />
                    </div>
                    <div className="h-2 w-full bg-zinc-800 rounded-full skeleton" />
                  </div>
                ))
              : predictions.length > 0
                ? predictions.map((prediction, i) => (
                    <PredictionCard
                      key={prediction.entity?.id || prediction.id || i}
                      prediction={prediction}
                      onClick={(p) => {
                        console.log('Prediction clicked:', p)
                      }}
                    />
                  ))
                : (
                    <div className="text-center text-sm text-zinc-500 py-8">
                      No predictions available
                    </div>
                  )}
          </div>
        </div>
      </div>

      {/* Bottom: Genre Heatmap */}
      <div className="rounded-lg border border-zinc-800 bg-zinc-900 overflow-hidden">
        <div className="px-5 py-4 border-b border-zinc-800">
          <h2 className="text-base font-semibold text-zinc-100">
            Genre Momentum
          </h2>
        </div>
        <div className="p-5">
          <GenreHeatmap
            genres={genres}
            isLoading={genresLoading}
            onGenreClick={(genre) => {
              console.log('Genre clicked:', genre)
            }}
          />
        </div>
      </div>

    </div>
  )
}
