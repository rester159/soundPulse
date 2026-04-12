import { useState } from 'react'
import {
  Music, Sparkles, Copy, Check, TrendingUp, Zap, Target,
  Activity, RefreshCw, Loader2, ChevronDown, ChevronUp,
} from 'lucide-react'
import { useTopOpportunities } from '../hooks/useSoundPulse'

const MODELS = [
  { id: 'suno', name: 'Suno' },
  { id: 'udio', name: 'Udio' },
  { id: 'soundraw', name: 'SOUNDRAW' },
  { id: 'musicgen', name: 'MusicGen' },
]

function ConfidenceBadge({ confidence }) {
  const map = {
    high:   'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
    medium: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
    low:    'bg-rose-500/15 text-rose-300 border-rose-500/30',
  }
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded border text-[10px] font-semibold uppercase tracking-wider ${map[confidence] || 'bg-zinc-800 text-zinc-400 border-zinc-700'}`}>
      <Activity size={9} /> {confidence || '?'} confidence
    </span>
  )
}

function MomentumBadge({ momentum }) {
  const cls = momentum === 'rising'
    ? 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30'
    : momentum === 'declining'
    ? 'bg-rose-500/15 text-rose-300 border-rose-500/30'
    : 'bg-zinc-800 text-zinc-400 border-zinc-700'
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded border text-[10px] font-semibold uppercase tracking-wider ${cls}`}>
      <TrendingUp size={9} /> {momentum}
    </span>
  )
}

function BlueprintCard({ blueprint, index }) {
  const [copied, setCopied] = useState(false)
  const [expanded, setExpanded] = useState(index === 0)  // first card open by default

  const handleCopy = () => {
    if (!blueprint.prompt) return
    navigator.clipboard.writeText(blueprint.prompt)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  if (blueprint.error) {
    return (
      <div className="rounded-xl border border-rose-500/30 bg-rose-500/5 p-5">
        <div className="text-rose-300 text-sm font-medium mb-1">{blueprint.genre_name}</div>
        <div className="text-rose-400/70 text-xs">{blueprint.error}</div>
      </div>
    )
  }

  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900 overflow-hidden">
      {/* Header — always visible */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full p-5 text-left hover:bg-zinc-900/50 transition-colors"
      >
        <div className="flex items-start justify-between gap-4 mb-3">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <span className="text-zinc-500 text-xs font-mono">#{index + 1}</span>
              <h3 className="text-lg font-bold text-zinc-100 truncate">{blueprint.genre_name}</h3>
            </div>
            <div className="flex flex-wrap items-center gap-2 mb-2">
              <ConfidenceBadge confidence={blueprint.confidence} />
              <MomentumBadge momentum={blueprint.momentum} />
              <span className="text-[10px] text-zinc-500">
                {blueprint.breakout_count} breakouts · {blueprint.track_count} tracks
              </span>
            </div>
          </div>
          <div className="flex flex-col items-end gap-1">
            <div className="text-2xl font-bold text-violet-300 tabular-nums">
              {(blueprint.opportunity_score * 100).toFixed(0)}
            </div>
            <div className="text-[9px] text-zinc-500 uppercase tracking-wider">opportunity</div>
          </div>
        </div>

        {/* Stats strip */}
        <div className="grid grid-cols-3 gap-2 text-[10px] text-zinc-500">
          <div className="bg-zinc-950 border border-zinc-800/60 rounded px-2 py-1.5">
            <div className="text-zinc-300 font-bold tabular-nums">{blueprint.avg_composite_ratio?.toFixed(1)}x</div>
            <div>composite ratio</div>
          </div>
          <div className="bg-zinc-950 border border-zinc-800/60 rounded px-2 py-1.5">
            <div className="text-zinc-300 font-bold tabular-nums">{blueprint.avg_velocity_ratio?.toFixed(1)}x</div>
            <div>velocity ratio</div>
          </div>
          <div className="bg-zinc-950 border border-zinc-800/60 rounded px-2 py-1.5">
            <div className="text-zinc-300 font-bold tabular-nums">{((blueprint.breakout_rate || 0) * 100).toFixed(0)}%</div>
            <div>breakout rate</div>
          </div>
        </div>

        <div className="flex items-center justify-end mt-3 text-zinc-500 text-xs">
          {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
        </div>
      </button>

      {/* Expanded section */}
      {expanded && blueprint.prompt && (
        <div className="border-t border-zinc-800 p-5 space-y-4 bg-zinc-950/30">
          {/* Rationale */}
          {blueprint.rationale && (
            <div className="space-y-2">
              <div className="flex items-center gap-2 text-zinc-400 text-xs font-semibold uppercase tracking-wider">
                <Target size={12} /> Why this blueprint
              </div>
              {blueprint.rationale.sonic_targeting && (
                <div className="text-xs text-zinc-300">
                  <span className="text-zinc-500">Sonic: </span>{blueprint.rationale.sonic_targeting}
                </div>
              )}
              {blueprint.rationale.lyrical_targeting && (
                <div className="text-xs text-zinc-300">
                  <span className="text-zinc-500">Lyrical: </span>{blueprint.rationale.lyrical_targeting}
                </div>
              )}
              {blueprint.rationale.differentiation && (
                <div className="text-xs text-zinc-300">
                  <span className="text-zinc-500">Edge: </span>{blueprint.rationale.differentiation}
                </div>
              )}
            </div>
          )}

          {/* The actual prompt */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-zinc-400 text-xs font-semibold uppercase tracking-wider">
                <Zap size={12} /> Generated Prompt — {blueprint.model}
              </div>
              <button
                onClick={handleCopy}
                className="flex items-center gap-1.5 px-3 py-1.5 bg-violet-600/20 hover:bg-violet-600/30 border border-violet-500/40 rounded text-xs text-violet-200 transition-colors"
              >
                {copied ? <Check size={12} className="text-emerald-400" /> : <Copy size={12} />}
                {copied ? 'Copied!' : 'Copy to clipboard'}
              </button>
            </div>
            <pre className="bg-zinc-950 border border-zinc-800 rounded-lg p-4 text-xs text-zinc-300 whitespace-pre-wrap font-mono leading-relaxed max-h-96 overflow-y-auto">
              {blueprint.prompt}
            </pre>
          </div>

          {/* Based on */}
          {blueprint.based_on && (
            <div className="text-[10px] text-zinc-600 border-t border-zinc-800 pt-3">
              Based on {blueprint.based_on.breakout_count} breakouts ·{' '}
              {blueprint.based_on.feature_deltas_count} delta-analyzed ·{' '}
              {blueprint.based_on.gap_clusters} sonic clusters ·{' '}
              {blueprint.based_on.lyrical_analysis_present ? 'lyrical intel ✓' : 'lyrical intel pending'}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default function SongLab() {
  const [model, setModel] = useState('suno')
  const { data, isLoading, isError, error, refetch, isFetching } = useTopOpportunities(5, model)

  const blueprints = data?.data?.data?.blueprints || []
  const generatedAt = data?.data?.data?.generated_at

  return (
    <div className="p-6 max-w-5xl mx-auto">
      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <div className="flex items-center gap-3 mb-1">
            <Music size={24} className="text-violet-400" />
            <h1 className="text-2xl font-bold text-zinc-100">Song Lab</h1>
          </div>
          <p className="text-sm text-zinc-500">
            Top 5 breakout opportunities right now — each with a ready-to-use prompt for {model}.
          </p>
        </div>

        <div className="flex items-center gap-3">
          {/* Model picker */}
          <div className="flex gap-1 bg-zinc-900 border border-zinc-800 rounded-lg p-1">
            {MODELS.map(m => (
              <button
                key={m.id}
                onClick={() => setModel(m.id)}
                className={`px-3 py-1 text-xs rounded font-medium transition-colors ${
                  model === m.id
                    ? 'bg-violet-600/30 text-violet-200 border border-violet-500/50'
                    : 'text-zinc-500 hover:text-zinc-300'
                }`}
              >
                {m.name}
              </button>
            ))}
          </div>

          <button
            onClick={() => refetch()}
            disabled={isFetching}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-zinc-900 hover:bg-zinc-800 border border-zinc-800 text-zinc-300 text-xs rounded-lg disabled:opacity-50"
          >
            {isFetching ? <Loader2 size={12} className="animate-spin" /> : <RefreshCw size={12} />}
            Refresh
          </button>
        </div>
      </div>

      {/* Loading state */}
      {isLoading && (
        <div className="flex flex-col items-center justify-center py-20 text-zinc-500 gap-3">
          <Loader2 size={28} className="animate-spin text-violet-400" />
          <div className="text-sm">Generating 5 smart blueprints in parallel...</div>
          <div className="text-[10px] text-zinc-600">5 LLM calls × ~1.5s — should be ready in ~2 sec</div>
        </div>
      )}

      {/* Error state */}
      {isError && (
        <div className="bg-rose-500/10 border border-rose-500/30 rounded-xl p-4 text-rose-300 text-sm">
          Failed to load opportunities: {error?.message}
        </div>
      )}

      {/* Empty state */}
      {!isLoading && !isError && blueprints.length === 0 && (
        <div className="flex flex-col items-center justify-center py-20 text-center">
          <Sparkles size={48} className="text-zinc-700 mb-4" />
          <h3 className="text-lg font-medium text-zinc-300 mb-1">No breakout opportunities yet</h3>
          <p className="text-sm text-zinc-500 max-w-sm">
            The breakout detection sweep needs to find tracks before blueprints can be generated.
            Run the sweep from the admin panel or wait for the next scheduled run.
          </p>
        </div>
      )}

      {/* Blueprint cards */}
      {blueprints.length > 0 && (
        <>
          <div className="space-y-4">
            {blueprints.map((bp, i) => (
              <BlueprintCard key={bp.genre} blueprint={bp} index={i} />
            ))}
          </div>

          {generatedAt && (
            <div className="mt-6 text-center text-[10px] text-zinc-600">
              Generated at {new Date(generatedAt).toLocaleTimeString()} ·{' '}
              Cached for 5 minutes · Click Refresh for new analysis
            </div>
          )}
        </>
      )}
    </div>
  )
}
