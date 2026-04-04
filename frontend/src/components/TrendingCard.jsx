import SparkLine from './SparkLine'
import { formatScore } from '../utils/formatters'

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
  spotify: 'SP',
  apple_music: 'AM',
  tidal: 'TD',
  youtube: 'YT',
  soundcloud: 'SC',
  shazam: 'SZ',
  deezer: 'DZ',
}

export default function TrendingCard({ item, rank, onClick }) {
  if (!item) return null

  const entity = item.entity || item
  const scores = item.scores || {}
  const sparkline = item.sparkline_7d || []
  const compositeScore = scores.composite ?? entity.composite_score ?? 0
  const platforms = Object.keys(scores).filter((k) => k !== 'composite')

  return (
    <button
      onClick={() => onClick?.(item)}
      className="group w-full flex items-center gap-4 px-4 py-3 rounded-lg border border-zinc-800 bg-zinc-900 hover:border-violet-500/40 hover:shadow-[0_0_16px_rgba(139,92,246,0.08)] transition-all duration-150 ease-out text-left cursor-pointer"
    >
      {/* Rank */}
      {rank !== undefined && (
        <span className="font-mono text-sm font-semibold text-zinc-500 w-7 text-right shrink-0">
          {rank}
        </span>
      )}

      {/* Info */}
      <div className="flex-1 min-w-0">
        <div className="text-sm font-medium text-zinc-100 truncate">
          {entity.name || entity.title || 'Unknown'}
        </div>
        {entity.artist?.name && (
          <div className="text-xs text-zinc-500 truncate">{entity.artist.name}</div>
        )}
      </div>

      {/* Score bar */}
      <div className="flex items-center gap-2 shrink-0">
        <div className="w-20 h-1.5 bg-zinc-800 rounded-full overflow-hidden">
          <div
            className="h-full rounded-full bg-violet-500 transition-all duration-300 ease-out"
            style={{ width: `${Math.min(100, Math.max(0, compositeScore))}%` }}
          />
        </div>
        <span className="font-mono text-xs text-zinc-300 w-8 text-right">
          {formatScore(compositeScore)}
        </span>
      </div>

      {/* Platform badges */}
      {platforms.length > 0 && (
        <div className="flex gap-1 shrink-0">
          {platforms.slice(0, 4).map((platform) => (
            <span
              key={platform}
              className="text-[9px] font-mono font-semibold px-1.5 py-0.5 rounded"
              style={{
                backgroundColor: `${PLATFORM_COLORS[platform] || '#52525b'}20`,
                color: PLATFORM_COLORS[platform] || '#a1a1aa',
              }}
            >
              {PLATFORM_LABELS[platform] || platform.slice(0, 2).toUpperCase()}
            </span>
          ))}
          {platforms.length > 4 && (
            <span className="text-[9px] font-mono text-zinc-500">
              +{platforms.length - 4}
            </span>
          )}
        </div>
      )}

      {/* Sparkline */}
      <div className="shrink-0">
        <SparkLine data={sparkline} width={80} height={24} />
      </div>
    </button>
  )
}
