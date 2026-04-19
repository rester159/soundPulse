import { useState, useMemo } from 'react'
import {
  Music, Sparkles, Copy, Check, TrendingUp, Zap, Target,
  Activity, RefreshCw, Loader2, ChevronDown, ChevronUp,
  Play, AlertTriangle,
} from 'lucide-react'
import { Link } from 'react-router-dom'
import {
  useTopOpportunities, useMusicProviders, useMusicGenerate, useMusicPoll,
  useMusicGenerations, getBaseUrl,
  useBlueprints, useGenerateSongForBlueprint,
} from '../hooks/useSoundPulse'

// Backend-served audio URLs come back as /api/v1/... paths. Resolve
// them against the backend base so the frontend can play them from a
// different origin in production.
function resolveAudioUrl(url) {
  if (!url) return url
  if (/^https?:\/\//i.test(url)) return url
  if (url.startsWith('/api/v1/')) {
    const base = getBaseUrl().replace(/\/api\/v1\/?$/, '')
    return base + url
  }
  return url
}

// Display mapping from generation provider id → prompt-style id used by
// /blueprint/top-opportunities.
const PROVIDER_TO_PROMPT_STYLE = {
  musicgen: 'musicgen',
  suno_kie: 'suno',
  udio: 'suno',  // Udio speaks the Suno-style prompt format
}

const PROVIDER_DISPLAY = {
  musicgen: 'MusicGen',
  suno_kie: 'Suno v5.5',
  udio: 'Udio',
  soundraw: 'SOUNDRAW',
}

// Genres that are best served instrumentally (MusicGen) vs with lyrics (Udio).
// Lyrical genres auto-default to Udio when it's live; instrumental ones
// auto-default to MusicGen.
const INSTRUMENTAL_GENRE_TOKENS = [
  'classical', 'ambient', 'orchestral', 'soundtrack', 'score', 'new-age',
  'experimental', 'jazz', 'lo-fi', 'electronic', 'downtempo',
]

function isInstrumentalGenre(genre) {
  if (!genre) return false
  const g = genre.toLowerCase()
  return INSTRUMENTAL_GENRE_TOKENS.some(tok => g.includes(tok))
}

function pickDefaultProvider(providers, genre) {
  const live = providers.filter(p => p.live)
  if (live.length === 0) return providers[0]?.id || 'musicgen'
  const liveIds = new Set(live.map(p => p.id))
  const instrumental = isInstrumentalGenre(genre)
  // Preference order
  if (instrumental && liveIds.has('musicgen')) return 'musicgen'
  // Suno v5.5 beats Udio on vocal quality — prefer when available
  if (!instrumental && liveIds.has('suno_kie')) return 'suno_kie'
  if (!instrumental && liveIds.has('udio')) return 'udio'
  // Fall back to the first live provider
  return live[0].id
}

// MusicGen is text-to-instrumental — strip the LYRICS section so the
// model isn't confused by verse/chorus markup it can't act on.
function stripLyricsForMusicgen(prompt) {
  if (!prompt) return prompt
  const idx = prompt.indexOf('LYRICS:')
  if (idx < 0) return prompt
  return prompt.slice(0, idx).replace(/^STYLE:\s*/i, '').trim()
}

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

function RecentGenerationCard({ gen }) {
  const submitted = gen.submitted_at ? new Date(gen.submitted_at) : null
  const ago = submitted
    ? (() => {
        const mins = Math.floor((Date.now() - submitted.getTime()) / 60_000)
        if (mins < 1) return 'just now'
        if (mins < 60) return `${mins}m ago`
        const hrs = Math.floor(mins / 60)
        if (hrs < 24) return `${hrs}h ago`
        return `${Math.floor(hrs / 24)}d ago`
      })()
    : ''
  const statusCls =
    gen.status === 'succeeded' ? 'text-emerald-300 bg-emerald-500/10 border-emerald-500/30'
    : gen.status === 'failed' ? 'text-rose-300 bg-rose-500/10 border-rose-500/30'
    : 'text-amber-300 bg-amber-500/10 border-amber-500/30'
  return (
    <div className="flex-shrink-0 w-72 bg-zinc-900 border border-zinc-800 rounded-lg p-3 space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-[10px] font-semibold uppercase tracking-wider text-zinc-500">
          {gen.genre_hint || 'unknown'} · {PROVIDER_DISPLAY[gen.provider] || gen.provider}
        </span>
        <span className={`text-[9px] px-1.5 py-0.5 rounded border uppercase tracking-wider ${statusCls}`}>
          {gen.status}
        </span>
      </div>
      <div className="text-[11px] text-zinc-400 line-clamp-2 min-h-[2.2em]">
        {gen.prompt}
      </div>
      {gen.status === 'succeeded' && gen.audio_url && (
        <audio
          controls
          src={resolveAudioUrl(gen.audio_url)}
          className="w-full"
          style={{ filter: 'invert(0.9) hue-rotate(180deg)' }}
        />
      )}
      {gen.status === 'succeeded' && !gen.audio_url && (
        <div className="text-[10px] text-amber-300 italic">
          audio expired — provider purged the file before we could self-host it
        </div>
      )}
      {gen.status === 'failed' && gen.error_message && (
        <div className="text-[10px] text-rose-300 line-clamp-1">{gen.error_message}</div>
      )}
      <div className="flex items-center justify-between text-[9px] text-zinc-600">
        <span>{ago}</span>
        <span className="tabular-nums">${(gen.actual_cost_usd ?? gen.estimated_cost_usd ?? 0).toFixed(3)}</span>
      </div>
    </div>
  )
}

function RecentGenerations() {
  const { data, isLoading } = useMusicGenerations(20)
  const gens = data?.data?.generations || []
  if (isLoading && gens.length === 0) return null
  if (!gens.length) return null
  return (
    <div className="mb-6 space-y-2">
      <div className="flex items-center gap-2 text-zinc-400 text-xs font-semibold uppercase tracking-wider">
        <Music size={12} /> Recent generations ({gens.length})
      </div>
      <div className="flex gap-3 overflow-x-auto pb-2 -mx-2 px-2">
        {gens.map(g => <RecentGenerationCard key={g.id} gen={g} />)}
      </div>
    </div>
  )
}

function GenerationPanel({ blueprint, providerId, providerLive }) {
  const [taskId, setTaskId] = useState(null)
  const generate = useMusicGenerate()
  const poll = useMusicPoll(providerId, taskId, { enabled: !!taskId })

  const result = poll.data?.data
  const status = result?.status
  const audioUrl = result?.audio_url
  const pollError = result?.error
  const submitError = generate.error?.response?.data?.detail || generate.error?.message

  const buildGenerateBody = () => {
    let prompt = blueprint.prompt
    if (providerId === 'musicgen') {
      prompt = stripLyricsForMusicgen(prompt)
    }
    return {
      provider: providerId,
      prompt,
      duration_seconds: providerId === 'musicgen' ? 30 : 90,
      genre_hint: blueprint.genre,
      mood_tags: [],
    }
  }

  const handleGenerate = async () => {
    setTaskId(null)
    try {
      const res = await generate.mutateAsync({ body: buildGenerateBody() })
      const newTaskId = res?.data?.task_id
      if (newTaskId) setTaskId(newTaskId)
    } catch (_) {
      // error surfaced via generate.error
    }
  }

  const handleReset = () => {
    setTaskId(null)
    generate.reset()
  }

  const estCost = providerId === 'musicgen' ? '$0.06' : '~$0.11'

  return (
    <div className="space-y-3 border-t border-zinc-800 pt-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-zinc-400 text-xs font-semibold uppercase tracking-wider">
          <Play size={12} /> Generate
        </div>
        <div className="text-[10px] text-zinc-500">
          via {PROVIDER_DISPLAY[providerId] || providerId} · {estCost}
        </div>
      </div>

      {!providerLive && (
        <div className="flex items-start gap-2 bg-amber-500/10 border border-amber-500/30 rounded p-2.5 text-[11px] text-amber-300">
          <AlertTriangle size={14} className="flex-shrink-0 mt-0.5" />
          <div>
            <strong>{PROVIDER_DISPLAY[providerId] || providerId}</strong> is not configured.
            Add the credential in Railway env vars to enable live generation.
          </div>
        </div>
      )}

      {providerLive && !taskId && !generate.isPending && (
        <button
          onClick={handleGenerate}
          className="flex items-center gap-2 px-4 py-2.5 bg-violet-600 hover:bg-violet-500 disabled:opacity-40 text-white text-sm font-medium rounded-lg transition-colors"
        >
          <Sparkles size={14} /> Generate song ({estCost})
        </button>
      )}

      {(generate.isPending || (taskId && (status === 'pending' || status === 'processing'))) && (
        <div className="flex items-center gap-2 text-violet-300 text-xs">
          <Loader2 size={14} className="animate-spin" />
          {generate.isPending
            ? 'Submitting to provider...'
            : status === 'pending'
              ? 'Queued at provider...'
              : 'Generating — 30s classical audio typically takes 60-90s...'}
        </div>
      )}

      {submitError && !taskId && (
        <div className="bg-rose-500/10 border border-rose-500/30 rounded p-2.5 text-[11px] text-rose-300">
          <strong>Submission failed:</strong> {String(submitError)}
          <button onClick={handleReset} className="ml-2 underline">dismiss</button>
        </div>
      )}

      {status === 'failed' && (
        <div className="bg-rose-500/10 border border-rose-500/30 rounded p-2.5 text-[11px] text-rose-300">
          <strong>Generation failed:</strong> {pollError || 'unknown error'}
          <button onClick={handleReset} className="ml-2 underline">retry</button>
        </div>
      )}

      {status === 'succeeded' && audioUrl && (
        <div className="space-y-2">
          <div className="flex items-center gap-2 text-emerald-300 text-xs">
            <Check size={14} /> Ready — {result.duration_seconds?.toFixed(1)}s · ${result.actual_cost_usd?.toFixed(3)}
          </div>
          <audio
            controls
            src={resolveAudioUrl(audioUrl)}
            className="w-full"
            style={{ filter: 'invert(0.9) hue-rotate(180deg)' }}
          />
          <div className="flex items-center gap-3 text-[10px] text-zinc-500">
            <a href={resolveAudioUrl(audioUrl)} target="_blank" rel="noreferrer" className="underline hover:text-zinc-300">
              open in new tab
            </a>
            <button onClick={handleReset} className="underline hover:text-zinc-300">
              generate another
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

function BlueprintCard({ blueprint, index, providerId, providerLive }) {
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

          {/* Live generation */}
          {providerId && (
            <GenerationPanel
              blueprint={blueprint}
              providerId={providerId}
              providerLive={providerLive}
            />
          )}
        </div>
      )}
    </div>
  )
}

// Compact picker section — lists every blueprint saved via the
// /blueprints tab so the operator can kick off a generation without
// leaving SongLab. Renders empty (just a hint) when there are no saved
// blueprints, so the section never gets in the way of the top-5 cards.
function SavedBlueprintsPicker() {
  const { data, isLoading, refetch } = useBlueprints({ limit: 50 })
  const blueprints = data?.data?.blueprints || []
  // Only show ones that haven't already produced a song.
  const usable = blueprints.filter(b => b.status !== 'assigned_to_release')
  const generate = useGenerateSongForBlueprint()
  const [selectedId, setSelectedId] = useState('')
  const [status, setStatus] = useState(null)  // {kind, msg}

  const selected = usable.find(b => b.id === selectedId)

  const handleGenerate = async () => {
    if (!selected) return
    setStatus(null)
    try {
      const res = await generate.mutateAsync({ blueprintId: selected.id, body: {} })
      setStatus({
        kind: 'success',
        msg: `Song generation started — id ${res?.data?.song_id?.slice(0, 8) || ''}. Check Songs tab in ~60s.`,
      })
      refetch()
    } catch (e) {
      setStatus({
        kind: 'error',
        msg: e?.response?.data?.detail || e?.message || 'generation failed',
      })
    }
  }

  if (isLoading || usable.length === 0) {
    // Don't render the section if there's nothing useful to pick.
    // Provide a discoverability hint pointing to the /blueprints tab.
    return (
      <div className="mb-4 text-xs text-zinc-500">
        Want to use a custom recipe?{' '}
        <Link to="/blueprints" className="text-violet-400 hover:text-violet-300 underline">
          Open the Blueprints tab
        </Link>{' '}
        to generate one from a genre or build it from scratch.
      </div>
    )
  }

  return (
    <div className="mb-6 p-4 rounded-xl border border-violet-500/30 bg-violet-500/5">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Sparkles size={14} className="text-violet-400" />
          <span className="text-sm font-semibold text-violet-200">Use a saved blueprint</span>
          <span className="text-xs text-zinc-500">({usable.length} available)</span>
        </div>
        <Link to="/blueprints" className="text-xs text-violet-400 hover:text-violet-300 underline">
          Manage all →
        </Link>
      </div>
      <div className="flex items-center gap-2 flex-wrap">
        <select
          value={selectedId}
          onChange={(e) => setSelectedId(e.target.value)}
          className="flex-1 min-w-[280px] px-3 py-2 bg-zinc-950 border border-zinc-800 rounded text-sm text-zinc-100"
        >
          <option value="">— pick a saved blueprint —</option>
          {usable.map((b) => {
            const themePreview = (b.target_themes || []).slice(0, 2).join(', ')
            return (
              <option key={b.id} value={b.id}>
                {b.primary_genre || b.genre_id}
                {themePreview && ` · ${themePreview}`}
                {b.assigned_artist_id && ` · artist assigned`}
                {b.predicted_success_score != null && ` · score ${b.predicted_success_score.toFixed(2)}`}
              </option>
            )
          })}
        </select>
        <button
          onClick={handleGenerate}
          disabled={!selected || generate.isPending || !selected.assigned_artist_id}
          className="flex items-center gap-1.5 px-4 py-2 bg-violet-600 hover:bg-violet-500 disabled:bg-zinc-800 disabled:text-zinc-600 text-white text-sm font-medium rounded"
          title={selected && !selected.assigned_artist_id ? 'Assign an artist on the Blueprints tab first' : ''}
        >
          {generate.isPending ? <Loader2 size={14} className="animate-spin" /> : <Music size={14} />}
          {generate.isPending ? 'Generating…' : 'Generate song'}
        </button>
      </div>
      {selected && !selected.assigned_artist_id && (
        <div className="mt-2 text-xs text-amber-300/80">
          This blueprint has no assigned artist yet. <Link to="/blueprints" className="underline">Assign one on the Blueprints tab</Link> before generating.
        </div>
      )}
      {selected && (
        <div className="mt-2 text-xs text-zinc-500 line-clamp-2">
          {selected.smart_prompt_text}
        </div>
      )}
      {status && (
        <div className={`mt-3 p-2 rounded text-xs ${
          status.kind === 'success'
            ? 'bg-emerald-500/10 border border-emerald-500/30 text-emerald-300'
            : 'bg-rose-500/10 border border-rose-500/30 text-rose-300'
        }`}>
          {status.msg}
        </div>
      )}
    </div>
  )
}

export default function SongLab() {
  const { data: providersData } = useMusicProviders()
  const providers = providersData?.data?.providers || []

  // Opportunities are fetched once with a neutral prompt style
  // (Suno-format, which Udio also understands and MusicGen can safely
  // receive after stripping the LYRICS block).
  const { data, isLoading, isError, error, refetch, isFetching } =
    useTopOpportunities(5, 'suno')

  const blueprints = data?.data?.data?.blueprints || []
  const generatedAt = data?.data?.data?.generated_at

  // User can override via the picker; otherwise the provider is auto-
  // picked from the live providers based on the top blueprint's genre.
  const [providerId, setProviderId] = useState(null)
  const autoPickedId = useMemo(() => {
    const topGenre = blueprints[0]?.genre
    return pickDefaultProvider(providers, topGenre)
  }, [providers, blueprints])
  const activeProviderId = providerId || autoPickedId
  const activeProvider = providers.find(p => p.id === activeProviderId)
  const providerLive = !!activeProvider?.live

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
            Top 5 breakout opportunities right now — each ready to generate via {PROVIDER_DISPLAY[activeProviderId] || activeProviderId}.
          </p>
        </div>

        <div className="flex items-center gap-3">
          {/* Provider picker — driven by live registry */}
          <div className="flex gap-1 bg-zinc-900 border border-zinc-800 rounded-lg p-1">
            {providers.map(p => (
              <button
                key={p.id}
                onClick={() => setProviderId(p.id)}
                title={p.live ? `${p.display_name} — live` : `${p.display_name} — not configured`}
                className={`px-3 py-1 text-xs rounded font-medium transition-colors flex items-center gap-1.5 ${
                  activeProviderId === p.id
                    ? 'bg-violet-600/30 text-violet-200 border border-violet-500/50'
                    : 'text-zinc-500 hover:text-zinc-300'
                }`}
              >
                <span className={`w-1.5 h-1.5 rounded-full ${p.live ? 'bg-emerald-400' : 'bg-zinc-600'}`} />
                {PROVIDER_DISPLAY[p.id] || p.display_name}
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

      {/* Saved blueprints picker (from the /blueprints tab) */}
      <SavedBlueprintsPicker />

      {/* Recent generations — persisted across sessions */}
      <RecentGenerations />

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
              <BlueprintCard
                key={bp.genre}
                blueprint={bp}
                index={i}
                providerId={activeProviderId}
                providerLive={providerLive}
              />
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
