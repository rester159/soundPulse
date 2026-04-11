import { useMemo } from 'react'
import {
  Activity, AlertTriangle, CheckCircle2, Loader2, RefreshCw,
} from 'lucide-react'
import {
  Area, CartesianGrid, ComposedChart, Legend, Line, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
} from 'recharts'
import { useHydrationSnapshot, useHydrationHistory } from '../hooks/useSoundPulse'

// Source brand colors — matches the approved mock
const SOURCE_COLORS = {
  shazam:        '#0066ff',
  spotify:       '#1db954',
  apple_music:   '#fa586a',
  applemusic:    '#fa586a',
  itunes:        '#ff4081',
  tiktok:        '#ff0050',
  youtube:       '#ff0000',
  beatport:      '#01ff95',
  radio:         '#fde047',
  airplay:       '#fde047',
  deezer:        '#a238ff',
  amazon:        '#ff9900',
  soundcloud:    '#ff7700',
  chartmetric:   '#8b5cf6',
  playlist_spotify:     '#1db954',
  playlist_applemusic:  '#fa586a',
  playlist_deezer:      '#a238ff',
  applemusic_city:      '#fa586a',
  artist_catalog:       '#c4b5fd',
}

const colorFor = (src) => SOURCE_COLORS[src] || '#71717a'

function fmt(n) {
  if (n === null || n === undefined) return '—'
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`
  return n.toLocaleString()
}

function healthForPct(pct) {
  if (pct >= 60) return { label: 'good', cls: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30' }
  if (pct >= 10) return { label: 'fair', cls: 'bg-amber-500/10 text-amber-400 border-amber-500/30' }
  return { label: 'weak', cls: 'bg-rose-500/10 text-rose-400 border-rose-500/30' }
}

function LiveBadge() {
  return (
    <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 bg-emerald-500/10 border border-emerald-500/30 rounded text-[10px] font-medium text-emerald-400">
      <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
      LIVE · auto-refresh 10s
    </span>
  )
}

function KpiCard({ label, value, sub }) {
  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4">
      <div className="text-[10px] uppercase tracking-wider text-zinc-500 mb-2">{label}</div>
      <div className="text-2xl font-bold text-zinc-100 tabular-nums leading-none">{value}</div>
      {sub && <div className="text-[10px] text-zinc-600 mt-2">{sub}</div>}
    </div>
  )
}

// Build the recharts data shape from the history API
function buildChartData(history) {
  if (!history?.series?.length) return { data: [], sourceKeys: [] }
  // Collect all sources that appear in any bucket
  const sourceSet = new Set()
  for (const bucket of history.series) {
    for (const src of Object.keys(bucket.per_source_pct || {})) {
      sourceSet.add(src)
    }
  }
  const sourceKeys = [...sourceSet].sort()

  const data = history.series.map((bucket) => {
    const date = new Date(bucket.t)
    const row = {
      t: bucket.t,
      tLabel: date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      total_tracks: bucket.total_tracks,
      hydrated_tracks: bucket.hydrated_tracks,
    }
    for (const src of sourceKeys) {
      row[`pct_${src}`] = bucket.per_source_pct?.[src] || 0
    }
    return row
  })
  return { data, sourceKeys }
}

function TooltipBox({ active, payload, label }) {
  if (!active || !payload?.length) return null
  const totalEntry = payload.find((p) => p.dataKey === 'total_tracks')
  const pctEntries = payload.filter((p) => p.dataKey?.startsWith('pct_'))
  return (
    <div className="bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 text-[11px] shadow-xl min-w-[200px]">
      <div className="text-zinc-400 mb-1 font-medium">{label}</div>
      {totalEntry && (
        <div className="flex justify-between gap-4 mb-1 pb-1 border-b border-zinc-800">
          <span className="text-zinc-200 font-semibold">tracks</span>
          <span className="text-zinc-100 tabular-nums">{fmt(totalEntry.value)}</span>
        </div>
      )}
      <div className="space-y-0.5">
        {pctEntries
          .sort((a, b) => (b.value || 0) - (a.value || 0))
          .slice(0, 8)
          .map((e) => {
            const src = e.dataKey.replace('pct_', '')
            return (
              <div key={src} className="flex justify-between gap-4">
                <span className="flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-sm" style={{ background: e.color }} />
                  <span className="text-zinc-400">{src}</span>
                </span>
                <span className="text-zinc-200 tabular-nums">{e.value?.toFixed?.(1) || 0}%</span>
              </div>
            )
          })}
      </div>
    </div>
  )
}

export default function HydrationDashboard() {
  const snapshot = useHydrationSnapshot()
  const history = useHydrationHistory(24)

  const totals = snapshot.data?.data?.totals || {}
  const perSource = snapshot.data?.data?.per_source || []

  const { data: chartData, sourceKeys } = useMemo(
    () => buildChartData(history.data?.data),
    [history.data?.data]
  )

  // Sort per-source by track_count descending (matches the approved mock)
  const sortedSources = [...perSource].sort((a, b) => b.track_count - a.track_count)

  return (
    <div className="p-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Activity size={18} className="text-violet-400" />
            <h1 className="text-xl font-bold text-zinc-100">Hydration Coverage</h1>
          </div>
          <p className="text-xs text-zinc-500">
            Cross-source data coverage across the track corpus · real-time
          </p>
        </div>
        <button
          onClick={() => { snapshot.refetch(); history.refetch() }}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-zinc-900 hover:bg-zinc-800 border border-zinc-800 text-zinc-300 text-xs rounded-lg"
        >
          <RefreshCw size={12} /> refresh
        </button>
      </div>

      {(snapshot.isLoading || history.isLoading) && !snapshot.data && (
        <div className="flex items-center justify-center py-20 text-zinc-500">
          <Loader2 size={20} className="animate-spin mr-2" /> Loading hydration stats...
        </div>
      )}

      {snapshot.isError && (
        <div className="bg-rose-500/10 border border-rose-500/30 rounded-xl p-4 text-rose-300 text-sm mb-6">
          <AlertTriangle size={14} className="inline mr-1.5" />
          Failed to load hydration snapshot: {snapshot.error?.message}
        </div>
      )}

      {snapshot.data && (
        <>
          {/* KPI strip */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
            <KpiCard
              label="Total tracks"
              value={fmt(totals.total_tracks)}
              sub={`${totals.orphan_count || 0} orphan`}
            />
            <KpiCard
              label="Hydrated (≥1 source)"
              value={`${fmt(totals.hydrated_tracks)} ${totals.hydrated_pct?.toFixed?.(0) || 0}%`}
              sub="at least one source"
            />
            <KpiCard
              label="Multi-source (≥2)"
              value={`${fmt(totals.multi_source_tracks)} ${totals.multi_source_pct?.toFixed?.(0) || 0}%`}
              sub="entity resolution working"
            />
            <KpiCard
              label="Deeply covered (≥4)"
              value={`${fmt(totals.deep_source_tracks)} ${totals.deep_source_pct?.toFixed?.(0) || 0}%`}
              sub="chart-mainstream tracks"
            />
          </div>

          {/* Section 1 — live time-series chart */}
          <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 mb-6">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-3">
                <div className="text-zinc-500 text-xs font-medium uppercase tracking-wider">
                  Live hydration growth
                </div>
                <LiveBadge />
              </div>
              <div className="text-[10px] text-zinc-600">
                {history.data?.data?.n_buckets || 0} buckets · {history.data?.data?.hours || 24}h window
              </div>
            </div>

            {history.isLoading && !history.data ? (
              <div className="h-[340px] flex items-center justify-center text-zinc-500 text-sm">
                <Loader2 size={16} className="animate-spin mr-2" /> Loading chart...
              </div>
            ) : chartData.length === 0 ? (
              <div className="h-[340px] flex items-center justify-center text-zinc-500 text-sm">
                No history yet — waiting for first buckets to land.
              </div>
            ) : (
              <ResponsiveContainer width="100%" height={340}>
                <ComposedChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
                  <XAxis dataKey="tLabel" stroke="#71717a" tick={{ fontSize: 10 }} />
                  <YAxis
                    yAxisId="left"
                    stroke="#71717a"
                    tick={{ fontSize: 10 }}
                    label={{ value: 'tracks', angle: -90, position: 'insideLeft', fill: '#a1a1aa', fontSize: 10 }}
                  />
                  <YAxis
                    yAxisId="right"
                    orientation="right"
                    stroke="#71717a"
                    tick={{ fontSize: 10 }}
                    domain={[0, 100]}
                    label={{ value: '% coverage', angle: 90, position: 'insideRight', fill: '#a1a1aa', fontSize: 10 }}
                  />
                  <Tooltip content={<TooltipBox />} />
                  <Legend
                    wrapperStyle={{ fontSize: 10 }}
                    iconType="line"
                  />
                  {/* Total tracks area — bold white, left axis */}
                  <Area
                    yAxisId="left"
                    type="monotone"
                    dataKey="total_tracks"
                    name="total tracks"
                    stroke="#fafafa"
                    fill="rgba(255,255,255,0.06)"
                    strokeWidth={2.5}
                    dot={false}
                    activeDot={{ r: 4, fill: '#fafafa' }}
                  />
                  {/* Per-source percentage lines — right axis */}
                  {sourceKeys.map((src) => (
                    <Line
                      key={src}
                      yAxisId="right"
                      type="monotone"
                      dataKey={`pct_${src}`}
                      name={src}
                      stroke={colorFor(src)}
                      strokeWidth={1.8}
                      dot={false}
                      activeDot={{ r: 3 }}
                    />
                  ))}
                </ComposedChart>
              </ResponsiveContainer>
            )}
          </div>

          {/* Section 2 — per-source hydration bars */}
          <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-3">
                <div className="text-zinc-500 text-xs font-medium uppercase tracking-wider">
                  Tracks hydrated per source
                </div>
                <LiveBadge />
              </div>
              <div className="text-[10px] text-zinc-600">
                sorted by count · bar length = % of total tracks
              </div>
            </div>

            <div className="space-y-0">
              {sortedSources.length === 0 && (
                <div className="text-zinc-500 text-xs py-4">No sources yet — waiting for scrapers to land data.</div>
              )}
              {sortedSources.map((row) => {
                const color = colorFor(row.source)
                const health = healthForPct(row.pct)
                return (
                  <div
                    key={row.source}
                    className="grid grid-cols-[160px_1fr_90px_70px] gap-3 items-center py-2 border-b border-zinc-800/60 last:border-b-0"
                  >
                    <div className="flex items-center gap-2">
                      <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: color }} />
                      <span className="text-zinc-200 text-sm font-medium truncate">{row.source}</span>
                    </div>
                    <div className="relative h-5 bg-zinc-950 border border-zinc-800 rounded overflow-hidden">
                      <div
                        className="h-full rounded flex items-center justify-end pr-2 text-[10px] font-bold text-white"
                        style={{
                          width: `${Math.max(Math.min(row.pct, 100), 2)}%`,
                          background: `linear-gradient(90deg, ${color}33, ${color})`,
                          transition: 'width 0.5s ease',
                        }}
                      >
                        {row.pct.toFixed(0)}%
                      </div>
                    </div>
                    <div className="text-right text-zinc-100 text-sm font-semibold tabular-nums">
                      {fmt(row.track_count)}
                    </div>
                    <div className="text-right">
                      <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded border text-[9px] font-semibold uppercase tracking-wider ${health.cls}`}>
                        {health.label === 'good' ? <CheckCircle2 size={10} /> : <AlertTriangle size={10} />}
                        {health.label}
                      </span>
                    </div>
                  </div>
                )
              })}

              {totals.orphan_count > 0 && (
                <div className="grid grid-cols-[160px_1fr_90px_70px] gap-3 items-center py-2 pt-3 mt-2 border-t border-zinc-800">
                  <div className="flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-zinc-600 flex-shrink-0" />
                    <span className="text-zinc-400 text-sm font-medium">NO hydration</span>
                  </div>
                  <div className="relative h-5 bg-zinc-950 border border-zinc-800 rounded overflow-hidden">
                    <div
                      className="h-full rounded flex items-center justify-end pr-2 text-[10px] font-bold text-white"
                      style={{
                        width: `${Math.max(Math.min(totals.orphan_count / totals.total_tracks * 100, 100), 2)}%`,
                        background: 'linear-gradient(90deg, rgba(82,82,91,0.3), #71717a)',
                      }}
                    >
                      {((totals.orphan_count / totals.total_tracks) * 100).toFixed(0)}%
                    </div>
                  </div>
                  <div className="text-right text-zinc-300 text-sm font-semibold tabular-nums">
                    {fmt(totals.orphan_count)}
                  </div>
                  <div className="text-right">
                    <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded border text-[9px] font-semibold uppercase tracking-wider bg-rose-500/10 text-rose-400 border-rose-500/30">
                      <AlertTriangle size={10} />
                      orphan
                    </span>
                  </div>
                </div>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  )
}
