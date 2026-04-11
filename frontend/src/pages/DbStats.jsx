import { useState } from 'react'
import { Database, TrendingUp, AlertTriangle, CheckCircle2, RefreshCw, Loader2, Play } from 'lucide-react'
import {
  Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import {
  useDbStats,
  useDbStatsHistory,
  useSweepStatus,
  useTriggerClassificationSweep,
  useTriggerCompositeSweep,
} from '../hooks/useSoundPulse'

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
        </>
      )}
    </div>
  )
}
