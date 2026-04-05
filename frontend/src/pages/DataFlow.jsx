import { useRef, useEffect, useState, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { GitBranch, RefreshCw, CheckCircle, XCircle, Clock, Database, Cpu, Globe, Monitor, Zap } from 'lucide-react'
import { useDataFlow } from '../hooks/useSoundPulse'

// ── Diagram topology ─────────────────────────────────────────────────────────

const COLUMNS = [
  { id: 'sources',  label: 'Data Sources', Icon: Globe,    color: '#60a5fa' },
  { id: 'workers',  label: 'Pipeline',     Icon: Cpu,      color: '#fb923c' },
  { id: 'storage',  label: 'Database',     Icon: Database, color: '#a78bfa' },
  { id: 'computed', label: 'Computed',     Icon: Zap,      color: '#34d399' },
  { id: 'frontend', label: 'UI Pages',     Icon: Monitor,  color: '#f472b6' },
]

const NODES = [
  // Sources
  { id: 'chartmetric',    col: 'sources', label: 'Chartmetric',   scraperKey: 'chartmetric' },
  { id: 'spotify',        col: 'sources', label: 'Spotify',       scraperKey: 'spotify' },
  { id: 'spotify_audio',  col: 'sources', label: 'Spotify Audio', scraperKey: 'spotify_audio', subtitle: 'Audio features' },
  { id: 'shazam',         col: 'sources', label: 'Shazam',        scraperKey: 'shazam' },
  { id: 'apple_music',    col: 'sources', label: 'Apple Music',   scraperKey: 'apple_music' },
  { id: 'musicbrainz',    col: 'sources', label: 'MusicBrainz',   scraperKey: 'musicbrainz', subtitle: 'Metadata' },
  { id: 'radio',          col: 'sources', label: 'Radio',         scraperKey: 'radio' },

  // Workers
  { id: 'celery_beat',   col: 'workers', label: 'Celery Beat',   subtitle: 'Scheduler (cron)' },
  { id: 'celery_worker', col: 'workers', label: 'Celery Worker', subtitle: 'Task executor' },

  // Storage
  { id: 'trending_snapshots', col: 'storage', label: 'trending_snapshots', tableKey: 'trending_snapshots' },
  { id: 'tracks',             col: 'storage', label: 'tracks',             tableKey: 'tracks' },
  { id: 'predictions',        col: 'storage', label: 'predictions',        tableKey: 'predictions' },
  { id: 'backtest_results',   col: 'storage', label: 'backtest_results',   tableKey: 'backtest_results' },

  // Computed (on-the-fly or model)
  { id: 'composite_scores', col: 'computed', label: 'Composite Scores',     subtitle: 'Weighted platform avg' },
  { id: 'genre_opps',       col: 'computed', label: 'Genre Opportunities',  subtitle: '0.4×mom + 0.4×qual + 0.2×sat' },
  { id: 'blueprints',       col: 'computed', label: 'Blueprints',           subtitle: 'Song DNA templates' },
  { id: 'ml_model',         col: 'computed', label: 'ML Model',             subtitle: 'GradientBoosting (GBM)' },

  // UI Pages
  { id: 'dashboard', col: 'frontend', label: 'Dashboard',        path: '/' },
  { id: 'explore',   col: 'frontend', label: 'Explore',          path: '/explore' },
  { id: 'song_lab',  col: 'frontend', label: 'Song Lab',         path: '/song-lab' },
  { id: 'model_val', col: 'frontend', label: 'Model Validation', path: '/model-validation' },
  { id: 'assistant', col: 'frontend', label: 'Assistant',        path: null },
]

const EDGES = [
  // Sources → Worker
  { from: 'chartmetric',   to: 'celery_worker' },
  { from: 'spotify',       to: 'celery_worker' },
  { from: 'spotify_audio', to: 'celery_worker' },
  { from: 'shazam',        to: 'celery_worker' },
  { from: 'apple_music',   to: 'celery_worker' },
  { from: 'musicbrainz',   to: 'celery_worker' },
  { from: 'radio',         to: 'celery_worker' },
  { from: 'celery_beat',   to: 'celery_worker' },

  // Worker → Storage
  { from: 'celery_worker', to: 'trending_snapshots' },
  { from: 'celery_worker', to: 'tracks' },
  { from: 'celery_worker', to: 'predictions' },
  { from: 'celery_worker', to: 'backtest_results' },

  // Storage → Computed
  { from: 'trending_snapshots', to: 'composite_scores' },
  { from: 'trending_snapshots', to: 'genre_opps' },
  { from: 'trending_snapshots', to: 'blueprints' },
  { from: 'trending_snapshots', to: 'ml_model' },
  { from: 'tracks',             to: 'blueprints' },
  { from: 'tracks',             to: 'ml_model' },
  { from: 'predictions',        to: 'ml_model' },

  // Computed → Frontend
  { from: 'composite_scores', to: 'dashboard' },
  { from: 'composite_scores', to: 'explore' },
  { from: 'composite_scores', to: 'assistant' },
  { from: 'genre_opps',       to: 'song_lab' },
  { from: 'genre_opps',       to: 'assistant' },
  { from: 'blueprints',       to: 'song_lab' },
  { from: 'ml_model',         to: 'model_val' },
  { from: 'ml_model',         to: 'assistant' },
]

// ── Helpers ──────────────────────────────────────────────────────────────────

function relativeTime(isoStr) {
  if (!isoStr) return null
  const diff = Math.floor((Date.now() - new Date(isoStr)) / 1000)
  if (diff < 60)  return `${diff}s ago`
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
  return `${Math.floor(diff / 86400)}d ago`
}

function fmtNum(n) {
  if (n == null) return '—'
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M'
  if (n >= 1_000) return (n / 1_000).toFixed(1) + 'k'
  return String(n)
}

function statusColor(status) {
  if (status === 'success') return '#34d399'
  if (status === 'error')   return '#f87171'
  if (status === 'running') return '#60a5fa'
  return '#52525b'  // null / never run
}

// ── Sub-components ────────────────────────────────────────────────────────────

function ColumnHeader({ col }) {
  const { Icon, label, color } = col
  return (
    <div className="flex items-center gap-1.5 mb-3 px-1">
      <Icon size={13} style={{ color }} />
      <span className="text-xs font-semibold uppercase tracking-wider" style={{ color }}>
        {label}
      </span>
    </div>
  )
}

function ScraperBadge({ status, lastRun, recordCount }) {
  const color = statusColor(status)
  return (
    <div className="flex items-center gap-1.5 mt-0.5">
      <div className="w-1.5 h-1.5 rounded-full flex-shrink-0" style={{ backgroundColor: color }} />
      <span className="text-[10px]" style={{ color }}>
        {status || 'never run'}
      </span>
      {lastRun && (
        <span className="text-[10px] text-zinc-600">{relativeTime(lastRun)}</span>
      )}
      {recordCount != null && recordCount > 0 && (
        <span className="text-[10px] text-zinc-500">{fmtNum(recordCount)} records</span>
      )}
    </div>
  )
}

function TableBadge({ tableData }) {
  if (!tableData) return <div className="text-[10px] text-zinc-600 mt-0.5">loading…</div>
  const rows = tableData.total_rows
  return (
    <div className="flex items-center gap-1.5 mt-0.5">
      <div
        className="w-1.5 h-1.5 rounded-full flex-shrink-0"
        style={{ backgroundColor: rows > 0 ? '#34d399' : '#52525b' }}
      />
      <span className={`text-[10px] ${rows > 0 ? 'text-zinc-300' : 'text-zinc-600'}`}>
        {fmtNum(rows)} rows
      </span>
      {tableData.latest_date && (
        <span className="text-[10px] text-zinc-600">latest {tableData.latest_date}</span>
      )}
    </div>
  )
}

function DiagramNode({ node, nodeRef, live }) {
  const colDef = COLUMNS.find(c => c.id === node.col)
  const accentColor = colDef?.color || '#71717a'

  // Build badge content
  let badge = null
  if (node.scraperKey && live?.scrapers) {
    const s = live.scrapers.find(sc => sc.id === node.scraperKey)
    badge = s
      ? <ScraperBadge status={s.last_status} lastRun={s.last_run_at} recordCount={s.last_record_count} />
      : <div className="text-[10px] text-zinc-600 mt-0.5">not configured</div>
  } else if (node.tableKey && live?.tables) {
    badge = <TableBadge tableData={live.tables[node.tableKey]} />
  } else if (node.col === 'computed') {
    badge = <div className="text-[10px] text-zinc-500 mt-0.5">{node.subtitle}</div>
  } else if (node.col === 'workers') {
    badge = <div className="text-[10px] text-zinc-500 mt-0.5">{node.subtitle}</div>
  } else if (node.col === 'frontend' && node.path) {
    badge = (
      <Link to={node.path} className="text-[10px] text-violet-400 hover:text-violet-300 mt-0.5 block">
        open →
      </Link>
    )
  }

  // Extra detail line for tracks
  let extraDetail = null
  if (node.tableKey === 'tracks' && live?.tables?.tracks) {
    const t = live.tables.tracks
    extraDetail = (
      <div className="text-[10px] text-zinc-600 mt-0.5">
        {fmtNum(t.with_audio_features)} / {fmtNum(t.total_rows)} with audio features
      </div>
    )
  }
  if (node.tableKey === 'trending_snapshots' && live?.tables?.trending_snapshots) {
    const sn = live.tables.trending_snapshots
    extraDetail = (
      <div className="text-[10px] text-zinc-600 mt-0.5">
        {sn.distinct_dates} distinct dates
      </div>
    )
  }

  return (
    <div
      ref={nodeRef}
      className="rounded-lg border bg-zinc-900 px-3 py-2 mb-2 select-none"
      style={{ borderColor: `${accentColor}30` }}
    >
      <div className="text-xs font-medium text-zinc-200 leading-tight">{node.label}</div>
      {badge}
      {extraDetail}
    </div>
  )
}

// ── Main component ────────────────────────────────────────────────────────────

export default function DataFlow() {
  const { data: rawData, isLoading, refetch, dataUpdatedAt } = useDataFlow()
  const live = rawData?.data?.data

  const containerRef = useRef(null)
  const nodeRefs = useRef({})
  const [svgLines, setSvgLines] = useState([])
  const [svgSize, setSvgSize] = useState({ w: 0, h: 0 })

  const recalcLines = useCallback(() => {
    if (!containerRef.current) return
    const containerRect = containerRef.current.getBoundingClientRect()
    setSvgSize({ w: containerRect.width, h: containerRect.height })

    const newLines = EDGES.map(edge => {
      const fromEl = nodeRefs.current[edge.from]
      const toEl   = nodeRefs.current[edge.to]
      if (!fromEl || !toEl) return null
      const fr = fromEl.getBoundingClientRect()
      const tr = toEl.getBoundingClientRect()

      const x1 = fr.right  - containerRect.left
      const y1 = fr.top    + fr.height / 2 - containerRect.top
      const x2 = tr.left   - containerRect.left
      const y2 = tr.top    + tr.height / 2 - containerRect.top

      // Cubic bezier control points for smooth S-curves
      const cx = (x1 + x2) / 2
      const d  = `M${x1},${y1} C${cx},${y1} ${cx},${y2} ${x2},${y2}`

      // Determine edge color based on source column
      const fromNode = NODES.find(n => n.id === edge.from)
      const fromCol  = COLUMNS.find(c => c.id === fromNode?.col)
      const color    = fromCol ? fromCol.color + '30' : '#ffffff15'

      return { d, color, key: `${edge.from}-${edge.to}` }
    }).filter(Boolean)

    setSvgLines(newLines)
  }, [])

  useEffect(() => {
    // Initial calc + recalc after data loads
    const timer = setTimeout(recalcLines, 50)
    return () => clearTimeout(timer)
  }, [recalcLines, live])

  useEffect(() => {
    const ro = new ResizeObserver(recalcLines)
    if (containerRef.current) ro.observe(containerRef.current)
    return () => ro.disconnect()
  }, [recalcLines])

  // Group nodes by column
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
            <p className="text-sm text-zinc-500">Live architecture — sources, storage, computation, and UI</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {lastUpdated && (
            <span className="text-xs text-zinc-500">Updated {lastUpdated}</span>
          )}
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
        <div className="flex gap-4 flex-wrap">
          {[
            { label: 'Audio Features Coverage', value: `${live.coverage.audio_features_pct}%`, ok: live.coverage.audio_features_pct > 50 },
            { label: 'Prediction Coverage',     value: `${live.coverage.prediction_coverage_pct}%`, ok: live.coverage.prediction_coverage_pct > 0 },
            { label: 'Model Trained',            value: live.coverage.model_trained ? 'Yes' : 'No', ok: live.coverage.model_trained },
            { label: 'Snapshot Dates',           value: live.tables?.trending_snapshots?.distinct_dates ?? '—', ok: (live.tables?.trending_snapshots?.distinct_dates || 0) >= 14 },
          ].map(({ label, value, ok }) => (
            <div key={label} className="flex items-center gap-2 bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-2">
              {ok
                ? <CheckCircle size={12} className="text-emerald-400 flex-shrink-0" />
                : <XCircle size={12} className="text-rose-400 flex-shrink-0" />
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
        style={{ minHeight: 480 }}
      >
        {/* SVG overlay for edges */}
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

        {/* Columns */}
        <div className="relative z-10 grid gap-6" style={{ gridTemplateColumns: `repeat(${COLUMNS.length}, minmax(160px, 1fr))` }}>
          {COLUMNS.map(col => (
            <div key={col.id}>
              <ColumnHeader col={col} />
              {nodesByCol[col.id].map(node => (
                <DiagramNode
                  key={node.id}
                  node={node}
                  nodeRef={el => { nodeRefs.current[node.id] = el }}
                  live={live}
                />
              ))}
            </div>
          ))}
        </div>
      </div>

      {/* Platform breakdown table */}
      {live?.tables?.trending_snapshots?.platforms && Object.keys(live.tables.trending_snapshots.platforms).length > 0 && (
        <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-4">
          <h3 className="text-sm font-semibold text-zinc-300 mb-3 flex items-center gap-2">
            <Database size={14} className="text-violet-400" />
            Snapshots by Platform
          </h3>
          <div className="flex flex-wrap gap-3">
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

      {/* Scraper status table */}
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
                  <th className="text-center py-1.5 px-2">Enabled</th>
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
                    <td className="py-1.5 px-2">
                      <span style={{ color: statusColor(s.last_status) }}>{s.last_status || 'never'}</span>
                    </td>
                    <td className="py-1.5 px-2 text-zinc-500">{relativeTime(s.last_run_at) || '—'}</td>
                    <td className="py-1.5 px-2 text-right text-zinc-400">{s.last_record_count != null ? fmtNum(s.last_record_count) : '—'}</td>
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
