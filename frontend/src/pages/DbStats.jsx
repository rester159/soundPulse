import { useMemo, useState } from 'react'
import {
  Activity, AlertTriangle, CheckCircle2, Database, Loader2, Play, RefreshCw, TrendingUp,
} from 'lucide-react'
import {
  Area, Bar, BarChart, CartesianGrid, ComposedChart, Legend, Line, LineChart, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
} from 'recharts'
import {
  useDbStats,
  useDbStatsHistory,
  useHydrationHistory,
  useHydrationSnapshot,
  useSweepStatus,
  useTriggerClassificationSweep,
  useTriggerCompositeSweep,
} from '../hooks/useSoundPulse'

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
const healthForPct = (p) => {
  if (p >= 60) return { label: 'good', cls: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30' }
  if (p >= 10) return { label: 'fair', cls: 'bg-amber-500/10 text-amber-400 border-amber-500/30' }
  return { label: 'weak', cls: 'bg-rose-500/10 text-rose-400 border-rose-500/30' }
}

const RANGE_OPTIONS = [
  { value: 7,   label: '7d' },
  { value: 30,  label: '30d' },
  { value: 90,  label: '90d' },
  { value: 365, label: '1y' },
]

function fmt(n) {
  if (n === null || n === undefined) return '—'
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`
  return n.toLocaleString()
}

function pct(num, den) {
  if (!den) return 0
  return Math.round((num / den) * 100)
}

function HealthBadge({ value, total, warnBelow = 50, errorBelow = 10, label }) {
  const p = pct(value, total)
  let color = 'text-emerald-400'
  let bg = 'bg-emerald-500/10 border-emerald-500/30'
  let icon = <CheckCircle2 size={12} />
  if (p < errorBelow) {
    color = 'text-rose-400'
    bg = 'bg-rose-500/10 border-rose-500/30'
    icon = <AlertTriangle size={12} />
  } else if (p < warnBelow) {
    color = 'text-amber-400'
    bg = 'bg-amber-500/10 border-amber-500/30'
    icon = <AlertTriangle size={12} />
  }
  return (
    <div className={`inline-flex items-center gap-1 px-2 py-0.5 rounded border text-[10px] font-medium ${bg} ${color}`}>
      {icon}
      <span>{p}% {label}</span>
    </div>
  )
}

function StatCard({ title, total, subStats = [], wide = false }) {
  return (
    <div className={`bg-zinc-900 border border-zinc-800 rounded-xl p-5 ${wide ? 'col-span-2' : ''}`}>
      <div className="flex items-baseline justify-between mb-3">
        <div className="text-zinc-500 text-xs font-medium uppercase tracking-wider">{title}</div>
      </div>
      <div className="text-3xl font-bold text-zinc-100 mb-3">{fmt(total)}</div>
      {subStats.length > 0 && (
        <div className="space-y-1.5">
          {subStats.map((s) => (
            <div key={s.label} className="flex items-center justify-between text-xs">
              <span className="text-zinc-500">{s.label}</span>
              <div className="flex items-center gap-2">
                <span className="text-zinc-300 tabular-nums">{fmt(s.value)}</span>
                {s.health && <HealthBadge value={s.value} total={total} label={s.health} />}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
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

function LiveBadge() {
  return (
    <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 bg-emerald-500/10 border border-emerald-500/30 rounded text-[10px] font-medium text-emerald-400">
      <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
      LIVE · auto-refresh 10s
    </span>
  )
}

function buildHydrationChartData(history) {
  if (!history?.series?.length) return { data: [], sourceKeys: [] }
  const sourceSet = new Set()
  for (const bucket of history.series) {
    for (const src of Object.keys(bucket.per_source_pct || {})) sourceSet.add(src)
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

function HydrationTooltip({ active, payload, label }) {
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

function HydrationSection() {
  const snapshot = useHydrationSnapshot()
  const history = useHydrationHistory(24)
  const totals = snapshot.data?.data?.totals || {}
  const perSource = snapshot.data?.data?.per_source || []
  const { data: chartData, sourceKeys } = useMemo(
    () => buildHydrationChartData(history.data?.data),
    [history.data?.data]
  )
  const sortedSources = [...perSource].sort((a, b) => b.track_count - a.track_count)

  return (
    <div className="mt-8 pt-6 border-t border-zinc-800">
      <div className="flex items-center gap-2 mb-4">
        <Activity size={16} className="text-violet-400" />
        <h2 className="text-zinc-200 text-sm font-semibold uppercase tracking-wider">Hydration coverage</h2>
        <LiveBadge />
      </div>

      {snapshot.isError && (
        <div className="bg-rose-500/10 border border-rose-500/30 rounded-xl p-4 text-rose-300 text-sm mb-4">
          <AlertTriangle size={14} className="inline mr-1.5" />
          Failed to load hydration snapshot: {snapshot.error?.message}
        </div>
      )}

      {snapshot.data && (
        <>
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

          <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 mb-6">
            <div className="flex items-center justify-between mb-4">
              <div className="text-zinc-500 text-xs font-medium uppercase tracking-wider">
                Live hydration growth
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
                  <Tooltip content={<HydrationTooltip />} />
                  <Legend wrapperStyle={{ fontSize: 10 }} iconType="line" />
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

          <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
            <div className="flex items-center justify-between mb-4">
              <div className="text-zinc-500 text-xs font-medium uppercase tracking-wider">
                Tracks hydrated per source
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

function SweepPanel() {
  const sweepStatus = useSweepStatus()
  const triggerClassification = useTriggerClassificationSweep()
  const triggerComposite = useTriggerCompositeSweep()

  const status = sweepStatus.data?.data
  const tracksPending = status?.classification?.tracks_pending ?? 0
  const artistsPending = status?.classification?.artists_pending ?? 0
  const snapshotsPending = status?.normalization?.snapshots_pending_normalization ?? 0
  const tracksSkipped = status?.classification?.tracks_permanently_skipped ?? 0

  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <RefreshCw size={14} className="text-violet-400" />
          <span className="text-zinc-200 text-sm font-semibold">Deferred sweeps</span>
        </div>
        <button
          onClick={() => sweepStatus.refetch()}
          className="text-zinc-500 hover:text-zinc-300 text-xs"
        >
          refresh
        </button>
      </div>

      <div className="grid grid-cols-2 gap-3 mb-4">
        <div className="bg-zinc-950 border border-zinc-800/60 rounded-lg p-3">
          <div className="text-[10px] text-zinc-500 uppercase tracking-wider mb-1">Classification queue</div>
          <div className="text-2xl font-bold text-zinc-100">{fmt(tracksPending + artistsPending)}</div>
          <div className="text-[10px] text-zinc-600 mt-1">
            {fmt(tracksPending)} tracks · {fmt(artistsPending)} artists
            {tracksSkipped > 0 && ` · ${fmt(tracksSkipped)} skipped`}
          </div>
        </div>
        <div className="bg-zinc-950 border border-zinc-800/60 rounded-lg p-3">
          <div className="text-[10px] text-zinc-500 uppercase tracking-wider mb-1">Normalization queue</div>
          <div className="text-2xl font-bold text-zinc-100">{fmt(snapshotsPending)}</div>
          <div className="text-[10px] text-zinc-600 mt-1">snapshots pending recalc</div>
        </div>
      </div>

      <div className="flex gap-2">
        <button
          onClick={() => triggerClassification.mutate({}, { onSuccess: () => sweepStatus.refetch() })}
          disabled={triggerClassification.isPending}
          className="flex-1 flex items-center justify-center gap-2 px-3 py-2 bg-violet-600/20 hover:bg-violet-600/30 border border-violet-500/30 text-violet-300 text-xs font-medium rounded-lg transition-colors disabled:opacity-50"
        >
          {triggerClassification.isPending ? <Loader2 size={12} className="animate-spin" /> : <Play size={12} />}
          Run classification sweep
        </button>
        <button
          onClick={() => triggerComposite.mutate({}, { onSuccess: () => sweepStatus.refetch() })}
          disabled={triggerComposite.isPending}
          className="flex-1 flex items-center justify-center gap-2 px-3 py-2 bg-violet-600/20 hover:bg-violet-600/30 border border-violet-500/30 text-violet-300 text-xs font-medium rounded-lg transition-colors disabled:opacity-50"
        >
          {triggerComposite.isPending ? <Loader2 size={12} className="animate-spin" /> : <Play size={12} />}
          Run composite sweep
        </button>
      </div>

      {(triggerClassification.data || triggerComposite.data) && (
        <div className="mt-3 text-[10px] text-zinc-500 font-mono leading-relaxed">
          {triggerClassification.data && (
            <div>classification: {JSON.stringify(triggerClassification.data?.data?.stats)}</div>
          )}
          {triggerComposite.data && (
            <div>composite: {JSON.stringify(triggerComposite.data?.data?.stats)}</div>
          )}
        </div>
      )}
    </div>
  )
}

export default function DbStats() {
  const [days, setDays] = useState(90)
  const stats = useDbStats()
  const history = useDbStatsHistory(days)

  const tables = stats.data?.data?.tables || {}
  const tracks = tables.tracks || {}
  const artists = tables.artists || {}
  const snapshots = tables.trending_snapshots || {}
  const genres = tables.genres || {}
  const predictions = tables.predictions || {}
  const backtest = tables.backtest_results || {}
  const scrapers = tables.scraper_configs || {}

  const series = history.data?.data?.series || []

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Database size={18} className="text-violet-400" />
            <h1 className="text-xl font-bold text-zinc-100">Database stats</h1>
          </div>
          <p className="text-xs text-zinc-500">Live counts across every operational table. Auto-refreshes every 60s.</p>
        </div>
        <button
          onClick={() => { stats.refetch(); history.refetch() }}
          className="flex items-center gap-2 px-3 py-1.5 bg-zinc-900 hover:bg-zinc-800 border border-zinc-800 text-zinc-300 text-xs rounded-lg"
        >
          <RefreshCw size={12} /> Refresh
        </button>
      </div>

      {stats.isLoading && (
        <div className="flex items-center justify-center py-20 text-zinc-500">
          <Loader2 size={20} className="animate-spin mr-2" /> Loading stats...
        </div>
      )}

      {stats.isError && (
        <div className="bg-rose-500/10 border border-rose-500/30 rounded-xl p-4 text-rose-300 text-sm">
          Failed to load stats: {stats.error?.message}
        </div>
      )}

      {stats.data && (
        <>
          {/* Top — current state cards */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
            <StatCard
              title="Tracks"
              total={tracks.total}
              subStats={[
                { label: 'with audio features', value: tracks.with_audio_features, health: 'audio' },
                { label: 'classified (genres)',  value: tracks.with_genres,         health: 'classified' },
                { label: 'with ISRC',            value: tracks.with_isrc },
                { label: 'pending classification', value: tracks.pending_classification },
              ]}
            />
            <StatCard
              title="Artists"
              total={artists.total}
              subStats={[
                { label: 'classified (genres)', value: artists.with_genres,        health: 'classified' },
                { label: 'with Spotify ID',     value: artists.with_spotify_id },
                { label: 'pending classification', value: artists.pending_classification },
              ]}
            />
            <StatCard
              title="Trending snapshots"
              total={snapshots.total}
              subStats={[
                { label: 'distinct dates',         value: snapshots.distinct_dates },
                { label: 'distinct platforms',     value: snapshots.distinct_platforms },
                { label: 'pending normalization',  value: snapshots.pending_normalization },
                { label: 'with composite score',   value: snapshots.with_composite, health: 'scored' },
              ]}
            />
            <StatCard
              title="Genres"
              total={genres.total}
              subStats={[
                { label: 'active',           value: genres.active },
                { label: 'with audio profile', value: genres.with_audio_profile },
              ]}
            />
            <StatCard
              title="Predictions"
              total={predictions.total}
              subStats={[
                { label: '7d horizon',  value: predictions.h_7d },
                { label: '30d horizon', value: predictions.h_30d },
                { label: '90d horizon', value: predictions.h_90d },
                { label: 'resolved',    value: predictions.resolved },
              ]}
            />
            <StatCard
              title="Backtest runs"
              total={backtest.total}
              subStats={[
                { label: 'completed', value: backtest.completed_runs },
                { label: 'running',   value: backtest.running_runs },
                { label: 'failed',    value: backtest.failed_runs },
              ]}
            />
            <StatCard
              title="Scrapers"
              total={scrapers.total}
              subStats={[
                { label: 'enabled',     value: scrapers.enabled },
                { label: 'last success', value: scrapers.last_success },
                { label: 'last error',  value: scrapers.last_error },
              ]}
            />
            <SweepPanel />
          </div>

          {/* Snapshot date range */}
          {snapshots.earliest_date && (
            <div className="mb-6 text-xs text-zinc-500">
              Snapshot range: <span className="text-zinc-300 font-mono">{snapshots.earliest_date}</span> →{' '}
              <span className="text-zinc-300 font-mono">{snapshots.latest_date}</span>
            </div>
          )}

          {/* Per-platform breakdown */}
          {tables.trending_snapshots_per_source?.length > 0 && (
            <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 mb-6">
              <div className="text-zinc-500 text-xs font-medium uppercase tracking-wider mb-3">
                Snapshots per source platform
              </div>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs">
                {tables.trending_snapshots_per_source.map((row) => (
                  <div key={row.source_platform} className="flex justify-between bg-zinc-950 border border-zinc-800/60 rounded px-3 py-1.5">
                    <span className="text-zinc-400">{row.source_platform || '—'}</span>
                    <span className="text-zinc-200 font-mono">{fmt(row.total)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Date range selector */}
          <div className="flex items-center gap-2 mb-3">
            <TrendingUp size={14} className="text-violet-400" />
            <span className="text-zinc-200 text-sm font-semibold">Growth over time</span>
            <div className="ml-auto flex gap-1">
              {RANGE_OPTIONS.map((r) => (
                <button
                  key={r.value}
                  onClick={() => setDays(r.value)}
                  className={`px-2.5 py-1 text-xs rounded ${
                    days === r.value
                      ? 'bg-violet-600/30 text-violet-200 border border-violet-500/40'
                      : 'bg-zinc-900 text-zinc-500 border border-zinc-800 hover:text-zinc-300'
                  }`}
                >
                  {r.label}
                </button>
              ))}
            </div>
          </div>

          {history.isLoading && (
            <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-12 text-center text-zinc-500 text-sm">
              <Loader2 size={16} className="animate-spin inline-block mr-2" /> Loading history...
            </div>
          )}

          {history.data && series.length > 0 && (
            <>
              {/* Daily additions chart */}
              <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 mb-6">
                <div className="text-zinc-500 text-xs font-medium uppercase tracking-wider mb-3">
                  Daily additions ({series.length} days)
                </div>
                <ResponsiveContainer width="100%" height={260}>
                  <BarChart data={series}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
                    <XAxis dataKey="date" stroke="#71717a" tick={{ fontSize: 10 }} />
                    <YAxis stroke="#71717a" tick={{ fontSize: 10 }} />
                    <Tooltip
                      contentStyle={{ background: '#18181b', border: '1px solid #3f3f46', fontSize: 11 }}
                      labelStyle={{ color: '#a1a1aa' }}
                    />
                    <Legend wrapperStyle={{ fontSize: 11 }} />
                    <Bar dataKey="snapshots_added" stackId="a" fill="#8b5cf6" name="snapshots" />
                    <Bar dataKey="tracks_added"    stackId="a" fill="#06b6d4" name="tracks" />
                    <Bar dataKey="artists_added"   stackId="a" fill="#10b981" name="artists" />
                    <Bar dataKey="predictions_added" stackId="a" fill="#f59e0b" name="predictions" />
                  </BarChart>
                </ResponsiveContainer>
              </div>

              {/* Cumulative totals chart */}
              <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
                <div className="text-zinc-500 text-xs font-medium uppercase tracking-wider mb-3">
                  Cumulative totals
                </div>
                <ResponsiveContainer width="100%" height={260}>
                  <LineChart data={series}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
                    <XAxis dataKey="date" stroke="#71717a" tick={{ fontSize: 10 }} />
                    <YAxis stroke="#71717a" tick={{ fontSize: 10 }} />
                    <Tooltip
                      contentStyle={{ background: '#18181b', border: '1px solid #3f3f46', fontSize: 11 }}
                      labelStyle={{ color: '#a1a1aa' }}
                    />
                    <Legend wrapperStyle={{ fontSize: 11 }} />
                    <Line type="monotone" dataKey="snapshots_total" stroke="#8b5cf6" name="snapshots" dot={false} strokeWidth={2} />
                    <Line type="monotone" dataKey="tracks_total"    stroke="#06b6d4" name="tracks"    dot={false} strokeWidth={2} />
                    <Line type="monotone" dataKey="artists_total"   stroke="#10b981" name="artists"   dot={false} strokeWidth={2} />
                    <Line type="monotone" dataKey="predictions_total" stroke="#f59e0b" name="predictions" dot={false} strokeWidth={2} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </>
          )}

          <HydrationSection />
        </>
      )}
    </div>
  )
}
