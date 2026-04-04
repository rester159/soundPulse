import { useState } from 'react'
import { ChevronUp, ChevronDown } from 'lucide-react'
import SparkLine from './SparkLine'
import { formatScore, formatNumber } from '../utils/formatters'

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

const COLUMNS = [
  { key: 'rank', label: '#', sortable: false, className: 'w-12 text-center' },
  { key: 'name', label: 'Name', sortable: true, className: 'text-left' },
  {
    key: 'composite',
    label: 'Score',
    sortable: true,
    className: 'w-28 text-right',
  },
  {
    key: 'velocity',
    label: 'Velocity',
    sortable: true,
    className: 'w-24 text-right',
  },
  {
    key: 'platforms',
    label: 'Platforms',
    sortable: false,
    className: 'w-32',
  },
  { key: 'sparkline', label: '7d Trend', sortable: false, className: 'w-28' },
]

function getNestedValue(item, key) {
  const entity = item.entity || item
  const scores = item.scores || {}
  switch (key) {
    case 'name':
      return (entity.name || entity.title || '').toLowerCase()
    case 'composite':
      return scores.composite_score ?? scores.composite ?? entity.composite_score ?? 0
    case 'velocity':
      return scores.velocity ?? entity.velocity ?? 0
    default:
      return 0
  }
}

function SkeletonRow() {
  return (
    <tr className="border-b border-zinc-800/50">
      <td className="px-3 py-3">
        <div className="h-4 w-6 bg-zinc-800 rounded skeleton mx-auto" />
      </td>
      <td className="px-3 py-3">
        <div className="space-y-1.5">
          <div className="h-4 w-36 bg-zinc-800 rounded skeleton" />
          <div className="h-3 w-24 bg-zinc-800 rounded skeleton" />
        </div>
      </td>
      <td className="px-3 py-3">
        <div className="h-4 w-12 bg-zinc-800 rounded skeleton ml-auto" />
      </td>
      <td className="px-3 py-3">
        <div className="h-4 w-14 bg-zinc-800 rounded skeleton ml-auto" />
      </td>
      <td className="px-3 py-3">
        <div className="flex gap-1">
          <div className="h-5 w-7 bg-zinc-800 rounded skeleton" />
          <div className="h-5 w-7 bg-zinc-800 rounded skeleton" />
        </div>
      </td>
      <td className="px-3 py-3">
        <div className="h-6 w-20 bg-zinc-800 rounded skeleton" />
      </td>
    </tr>
  )
}

export default function TrendingTable({
  items = [],
  isLoading = false,
  onRowClick,
}) {
  const [sortKey, setSortKey] = useState('composite')
  const [sortDir, setSortDir] = useState('desc')

  function handleSort(key) {
    if (!COLUMNS.find((c) => c.key === key)?.sortable) return
    if (sortKey === key) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortKey(key)
      setSortDir('desc')
    }
  }

  const sorted = [...items].sort((a, b) => {
    const aVal = getNestedValue(a, sortKey)
    const bVal = getNestedValue(b, sortKey)
    const cmp = typeof aVal === 'string' ? aVal.localeCompare(bVal) : aVal - bVal
    return sortDir === 'asc' ? cmp : -cmp
  })

  return (
    <div className="overflow-x-auto rounded-lg border border-zinc-800">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-zinc-800 bg-zinc-900/60">
            {COLUMNS.map((col) => (
              <th
                key={col.key}
                className={`px-3 py-2.5 text-xs font-medium text-zinc-400 uppercase tracking-wider ${col.className} ${col.sortable ? 'cursor-pointer select-none hover:text-zinc-200 transition-colors duration-150' : ''}`}
                onClick={() => col.sortable && handleSort(col.key)}
              >
                <span className="inline-flex items-center gap-1">
                  {col.label}
                  {col.sortable && sortKey === col.key && (
                    sortDir === 'asc' ? (
                      <ChevronUp className="w-3 h-3" />
                    ) : (
                      <ChevronDown className="w-3 h-3" />
                    )
                  )}
                </span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {isLoading
            ? Array.from({ length: 8 }).map((_, i) => <SkeletonRow key={i} />)
            : sorted.map((item, index) => {
                const entity = item.entity || item
                const scores = item.scores || {}
                const compositeScore = scores.composite_score ?? scores.composite ?? entity.composite_score ?? 0
                const velocity = scores.velocity ?? entity.velocity ?? 0
                // platforms: use the platforms map if available, otherwise fill from platform_count
                const platformMap = scores.platforms || {}
                const platformKeys = Object.keys(platformMap).length > 0
                  ? Object.keys(platformMap)
                  : scores.platform_count > 0
                    ? Array(Math.min(scores.platform_count, 4)).fill('chartmetric')
                    : []
                const sparkline = item.sparkline_7d || []

                return (
                  <tr
                    key={entity.id || entity.name || index}
                    onClick={() => onRowClick?.(item)}
                    className="border-b border-zinc-800/50 hover:bg-zinc-800/30 transition-colors duration-150 cursor-pointer"
                  >
                    {/* Rank */}
                    <td className="px-3 py-3 text-center font-mono text-xs text-zinc-500">
                      {index + 1}
                    </td>

                    {/* Name / Artist */}
                    <td className="px-3 py-3">
                      <div className="text-sm font-medium text-zinc-100 truncate max-w-[200px]">
                        {entity.name || entity.title || 'Unknown'}
                      </div>
                      {entity.artist?.name && (
                        <div className="text-xs text-zinc-500 truncate">
                          {entity.artist.name}
                        </div>
                      )}
                    </td>

                    {/* Score */}
                    <td className="px-3 py-3 text-right">
                      <div className="flex items-center justify-end gap-2">
                        <div className="w-14 h-1.5 bg-zinc-800 rounded-full overflow-hidden">
                          <div
                            className="h-full rounded-full bg-violet-500 transition-all duration-300"
                            style={{
                              width: `${Math.min(100, Math.max(0, compositeScore))}%`,
                            }}
                          />
                        </div>
                        <span className="font-mono text-xs text-zinc-200 w-8 text-right">
                          {formatScore(compositeScore)}
                        </span>
                      </div>
                    </td>

                    {/* Velocity */}
                    <td className="px-3 py-3 text-right">
                      <span
                        className={`font-mono text-xs ${velocity > 0 ? 'text-emerald-400' : velocity < 0 ? 'text-rose-400' : 'text-zinc-500'}`}
                      >
                        {velocity > 0 ? '+' : ''}
                        {formatNumber(velocity)}
                      </span>
                    </td>

                    {/* Platforms */}
                    <td className="px-3 py-3">
                      <div className="flex gap-1 flex-wrap">
                        {platformKeys.slice(0, 4).map((platform, pi) => (
                          <span
                            key={`${platform}-${pi}`}
                            className="text-[9px] font-mono font-semibold px-1.5 py-0.5 rounded"
                            style={{
                              backgroundColor: `${PLATFORM_COLORS[platform] || '#52525b'}20`,
                              color:
                                PLATFORM_COLORS[platform] || '#a1a1aa',
                            }}
                          >
                            {PLATFORM_LABELS[platform] ||
                              platform.slice(0, 2).toUpperCase()}
                          </span>
                        ))}
                      </div>
                    </td>

                    {/* Sparkline */}
                    <td className="px-3 py-3">
                      <SparkLine data={sparkline} width={80} height={24} />
                    </td>
                  </tr>
                )
              })}

          {!isLoading && sorted.length === 0 && (
            <tr>
              <td
                colSpan={COLUMNS.length}
                className="px-3 py-12 text-center text-sm text-zinc-500"
              >
                No trending data available
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  )
}
