import { useState } from 'react'
import {
  Disc3, Loader2, ChevronDown, ChevronUp, CheckCircle2, Music2,
  Clock, FileAudio, AlertCircle, PlayCircle, Layers, Mic2,
  Crosshair, Minus, Plus, Save,
} from 'lucide-react'
import { useQueryClient } from '@tanstack/react-query'
import {
  useSongs, useSong, useMarkQaPassed, useSongStems, getBaseUrl,
  useInstrumentalAnalysis, useNudgeVocalEntry,
} from '../hooks/useSoundPulse'

// Reuse the backend-relative → absolute URL helper
function resolveAudioUrl(url) {
  if (!url) return url
  if (/^https?:\/\//i.test(url)) return url
  if (url.startsWith('/api/v1/')) {
    const base = getBaseUrl().replace(/\/api\/v1\/?$/, '')
    return base + url
  }
  return url
}

const STATUS_COLORS = {
  draft:               'bg-zinc-700/30 text-zinc-300 border-zinc-600/40',
  qa_pending:          'bg-amber-500/15 text-amber-300 border-amber-500/30',
  qa_failed:           'bg-rose-500/15 text-rose-300 border-rose-500/30',
  qa_passed:           'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
  assigned_to_release: 'bg-violet-500/15 text-violet-300 border-violet-500/30',
  submitted:           'bg-sky-500/15 text-sky-300 border-sky-500/30',
  live:                'bg-emerald-500/25 text-emerald-200 border-emerald-500/40',
  archived:            'bg-zinc-800 text-zinc-500 border-zinc-700',
  taken_down:          'bg-rose-500/10 text-rose-400 border-rose-500/30',
}

function StatusPill({ status }) {
  const cls = STATUS_COLORS[status] || 'bg-zinc-800 text-zinc-400 border-zinc-700'
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded border text-[10px] font-semibold uppercase tracking-wider ${cls}`}>
      {status?.replace(/_/g, ' ')}
    </span>
  )
}

// Stem-aware audio player. Default-plays final_mixed (the vocal-on-
// original-instrumental mix) if available, otherwise falls back to
// the master audio asset. Shows a toggle strip so the CEO can A/B
// between mixed / vocals-only / suno-original / drums / bass / other.
function StemAwareAudioPlayer({ song, masterUrl, masterMeta }) {
  const { data: stemsData, isLoading: stemsLoading } = useSongStems(song.song_id)
  const stems = stemsData?.data?.stems || []
  const job = stemsData?.data?.job
  const [selectedStem, setSelectedStem] = useState(null)

  // Pick the default playback source: final_mixed > master
  const hasFinalMixed = stems.find(s => s.stem_type === 'final_mixed')
  const activeStem = selectedStem || (hasFinalMixed ? hasFinalMixed.stem_type : null)
  const playbackUrl = activeStem
    ? resolveAudioUrl(stems.find(s => s.stem_type === activeStem)?.stream_url || masterUrl)
    : resolveAudioUrl(masterUrl)

  const STEM_META = {
    final_mixed:   { label: 'Mixed',   desc: 'vocals over original instrumental', Icon: Layers },
    vocals_only:   { label: 'Vocals',  desc: 'isolated vocal stem',               Icon: Mic2 },
    suno_original: { label: 'Suno',    desc: 'full Suno output (no mix)',         Icon: Music2 },
    drums:         { label: 'Drums',   desc: 'drum stem',                         Icon: Music2 },
    bass:          { label: 'Bass',    desc: 'bass stem',                         Icon: Music2 },
    other:         { label: 'Other',   desc: 'other instruments',                 Icon: Music2 },
  }

  const currentLabel = activeStem ? STEM_META[activeStem]?.label : 'Master'
  const currentDesc = activeStem
    ? STEM_META[activeStem]?.desc
    : `${masterMeta.provider} · ${masterMeta.format} · ${masterMeta.duration_seconds?.toFixed(1)}s`

  return (
    <div className="space-y-2">
      <div className="text-[10px] uppercase tracking-wider text-zinc-500 flex items-center gap-1">
        <PlayCircle size={10} /> Playing: <span className="text-violet-300">{currentLabel}</span> — {currentDesc}
      </div>
      <audio
        key={playbackUrl}
        controls
        src={playbackUrl}
        className="w-full"
        style={{ filter: 'invert(0.9) hue-rotate(180deg)' }}
      />

      {/* Stem toggle strip — only visible if we have at least one stem */}
      {stems.length > 0 && (
        <div className="flex items-center gap-1.5 flex-wrap pt-1">
          <div className="text-[10px] text-zinc-500 uppercase tracking-wider mr-1">
            <Layers size={10} className="inline mr-0.5" /> Stems:
          </div>
          {stems.map(s => {
            const meta = STEM_META[s.stem_type] || { label: s.stem_type, Icon: FileAudio }
            const isActive = activeStem === s.stem_type
            const Icon = meta.Icon
            return (
              <button
                key={s.id}
                onClick={() => setSelectedStem(s.stem_type)}
                className={`px-2 py-0.5 text-[10px] rounded border flex items-center gap-1 transition-colors ${
                  isActive
                    ? 'bg-violet-500/20 border-violet-500 text-violet-200'
                    : 'bg-zinc-900 border-zinc-800 text-zinc-400 hover:border-zinc-700 hover:text-zinc-200'
                }`}
                title={meta.desc}
              >
                <Icon size={10} />
                {meta.label}
                {s.size_bytes && (
                  <span className="text-[9px] opacity-60">
                    {Math.round(s.size_bytes / 1024)} KB
                  </span>
                )}
              </button>
            )
          })}
        </div>
      )}

      {/* Job status — shown while stems are being processed */}
      {job && job.status === 'pending' && (
        <div className="flex items-center gap-1.5 text-[10px] text-amber-400">
          <Clock size={10} /> Stem extraction queued — waiting for stem-extractor microservice
        </div>
      )}
      {job && job.status === 'in_progress' && (
        <div className="flex items-center gap-1.5 text-[10px] text-violet-300">
          <Loader2 size={10} className="animate-spin" /> {job.job_type === 'remix_only'
            ? 'Remixing vocals onto instrumental…'
            : 'Demucs separating vocals + mixing onto original instrumental…'}
        </div>
      )}
      {job && job.status === 'failed' && job.error_message && (
        <div className="text-[10px] text-rose-400 flex items-center gap-1">
          <AlertCircle size={10} /> Stem extraction failed: {job.error_message.slice(0, 100)}
        </div>
      )}
      {stemsLoading && !job && (
        <div className="text-[10px] text-zinc-600 flex items-center gap-1">
          <Loader2 size={10} className="animate-spin" /> Checking for stems…
        </div>
      )}

      {/* Nudge vocal entry — CEO correction for the auto-detected
          verse-1 start point on the source instrumental. Only shown
          once the first full stem extraction has completed (the
          remix_only path requires a cached vocals_only stem). */}
      {job?.source_instrumental_id && stems.some(s => s.stem_type === 'vocals_only') && (
        <VocalEntryNudge
          instrumentalId={job.source_instrumental_id}
          songId={song.song_id}
          jobStatus={job.status}
        />
      )}
    </div>
  )
}


// Nudge control for the instrumental's vocal entry point. Shown when
// a song has a completed stem job and a source instrumental. The
// value lives on the instrumentals row (so it's reused across every
// song that uses this beat); the "save" action here writes the new
// value + enqueues a remix_only job for this specific song so the CEO
// can hear the corrected mix without waiting 15 min for Demucs again.
function VocalEntryNudge({ instrumentalId, songId, jobStatus }) {
  const { data: analysisData } = useInstrumentalAnalysis(instrumentalId)
  const analysis = analysisData?.data
  const nudge = useNudgeVocalEntry()
  const [localValue, setLocalValue] = useState(null)

  // Initialize local state when server value arrives / changes
  const serverValue = analysis?.vocal_entry_seconds
  const source = analysis?.vocal_entry_source
  const current = localValue !== null ? localValue : (serverValue ?? 0)
  const dirty = localValue !== null && localValue !== serverValue

  const adjust = (delta) => {
    setLocalValue(Math.max(0, Number((current + delta).toFixed(3))))
  }

  const save = () => {
    if (!dirty) return
    nudge.mutate(
      { instrumentalId, vocalEntrySeconds: current, songId },
      { onSuccess: () => setLocalValue(null) },
    )
  }

  const busy = nudge.isPending || jobStatus === 'in_progress' || jobStatus === 'pending'

  return (
    <div className="mt-2 p-2 rounded border border-zinc-800 bg-zinc-950/60 text-[10px]">
      <div className="flex items-center gap-1.5 text-zinc-400 mb-1.5">
        <Crosshair size={10} className="text-violet-300" />
        <span className="uppercase tracking-wider">Vocal entry on instrumental</span>
        {source && (
          <span className={`ml-auto px-1.5 py-0.5 rounded text-[9px] ${
            source === 'manual' ? 'bg-violet-500/20 text-violet-300' : 'bg-zinc-800 text-zinc-500'
          }`}>
            {source === 'manual' ? 'CEO-set' : 'auto-detected'}
          </span>
        )}
      </div>
      <div className="flex items-center gap-1.5">
        <button
          onClick={() => adjust(-1)}
          disabled={busy}
          className="px-1.5 py-0.5 rounded border border-zinc-800 hover:border-zinc-700 text-zinc-400 disabled:opacity-40"
          title="−1 second"
        ><Minus size={10} /> 1s</button>
        <button
          onClick={() => adjust(-0.5)}
          disabled={busy}
          className="px-1.5 py-0.5 rounded border border-zinc-800 hover:border-zinc-700 text-zinc-400 disabled:opacity-40"
          title="−500 ms"
        ><Minus size={10} /> 0.5s</button>
        <button
          onClick={() => adjust(-0.1)}
          disabled={busy}
          className="px-1.5 py-0.5 rounded border border-zinc-800 hover:border-zinc-700 text-zinc-400 disabled:opacity-40"
          title="−100 ms"
        ><Minus size={10} /> 0.1s</button>
        <div className="px-2 py-0.5 mx-1 rounded border border-zinc-800 bg-zinc-900 min-w-[60px] text-center font-mono">
          {current.toFixed(3)}s
        </div>
        <button
          onClick={() => adjust(0.1)}
          disabled={busy}
          className="px-1.5 py-0.5 rounded border border-zinc-800 hover:border-zinc-700 text-zinc-400 disabled:opacity-40"
          title="+100 ms"
        ><Plus size={10} /> 0.1s</button>
        <button
          onClick={() => adjust(0.5)}
          disabled={busy}
          className="px-1.5 py-0.5 rounded border border-zinc-800 hover:border-zinc-700 text-zinc-400 disabled:opacity-40"
          title="+500 ms"
        ><Plus size={10} /> 0.5s</button>
        <button
          onClick={() => adjust(1)}
          disabled={busy}
          className="px-1.5 py-0.5 rounded border border-zinc-800 hover:border-zinc-700 text-zinc-400 disabled:opacity-40"
          title="+1 second"
        ><Plus size={10} /> 1s</button>
        <button
          onClick={save}
          disabled={!dirty || busy}
          className={`ml-2 px-2 py-0.5 rounded border flex items-center gap-1 ${
            dirty && !busy
              ? 'bg-violet-500/20 border-violet-500 text-violet-200 hover:bg-violet-500/30'
              : 'border-zinc-800 text-zinc-600 cursor-not-allowed'
          }`}
        >
          {nudge.isPending ? <Loader2 size={10} className="animate-spin" /> : <Save size={10} />}
          Save &amp; Remix
        </button>
      </div>
      <div className="mt-1.5 text-[9px] text-zinc-500">
        Nudge where verse 1 starts on the instrumental, then Save & Remix re-runs only
        the ffmpeg mix (~10 s) using the cached vocals stem. Value is saved to the
        instrumental so all future songs using this beat inherit the correction.
      </div>
    </div>
  )
}


function SongDetailPanel({ songId, onQaPassed }) {
  const { data, isLoading } = useSong(songId)
  const song = data?.data

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 text-zinc-500 text-xs py-4">
        <Loader2 size={14} className="animate-spin" /> Loading song detail...
      </div>
    )
  }
  if (!song) return null

  const master = song.audio_assets?.find(a => a.is_master_candidate) || song.audio_assets?.[0]
  const coverUrl = song.primary_artwork_asset_id
    ? resolveAudioUrl(`/api/v1/admin/visual/${song.primary_artwork_asset_id}.png`)
    : null

  return (
    <div className="space-y-4 bg-zinc-950/40 p-4 border-t border-zinc-800">
      {/* Cover art */}
      {coverUrl && (
        <div className="flex justify-center">
          <img
            src={coverUrl}
            alt={song.title}
            className="w-64 h-64 rounded-lg object-cover border border-zinc-700 shadow-lg"
          />
        </div>
      )}
      {/* Audio player with stem toggle */}
      {master && master.storage_url && (
        <StemAwareAudioPlayer song={song} masterUrl={master.storage_url} masterMeta={master} />
      )}
      {(!master || !master.storage_url) && song.status !== 'draft' && (
        <div className="flex items-start gap-2 bg-amber-500/10 border border-amber-500/30 rounded p-2.5 text-[11px] text-amber-300">
          <AlertCircle size={14} className="flex-shrink-0 mt-0.5" />
          No playable audio asset — the generation may still be in flight or the bytes expired before self-hosting.
        </div>
      )}

      {/* Grid of key metadata */}
      <div className="grid grid-cols-4 gap-2 text-[10px]">
        <MetaBox label="Tempo"    value={song.tempo_bpm ? `${song.tempo_bpm} BPM` : '—'} />
        <MetaBox label="Key"      value={song.key_camelot || '—'} />
        <MetaBox label="Duration" value={song.duration_seconds ? `${song.duration_seconds}s` : '—'} />
        <MetaBox label="Language" value={song.language || 'en'} />
        <MetaBox label="Provider" value={song.generation_provider || '—'} />
        <MetaBox label="Cost"     value={song.generation_cost_usd ? `$${song.generation_cost_usd.toFixed(3)}` : '—'} />
        <MetaBox label="ISRC"     value={song.isrc || '—'} />
        <MetaBox label="Release"  value={song.release_title || (song.release_id ? song.release_id.slice(0, 8) : '—')} />
      </div>

      {/* Prompt */}
      {song.generation_prompt && (
        <div className="space-y-1">
          <div className="text-[10px] uppercase tracking-wider text-zinc-500">Generation Prompt</div>
          <pre className="bg-zinc-950 border border-zinc-800 rounded p-3 text-[10px] text-zinc-300 whitespace-pre-wrap max-h-48 overflow-y-auto font-mono leading-relaxed">
            {song.generation_prompt}
          </pre>
        </div>
      )}

      {/* Actions */}
      <div className="flex items-center gap-2 pt-2 border-t border-zinc-800">
        {(song.status === 'draft' || song.status === 'qa_pending') && (
          <button
            onClick={() => onQaPassed(song.song_id)}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-medium rounded-lg transition-colors"
          >
            <CheckCircle2 size={12} /> Mark QA passed (bypass)
          </button>
        )}
        {song.audio_assets?.length > 1 && (
          <span className="text-[10px] text-zinc-500">
            {song.audio_assets.length} audio assets
          </span>
        )}
      </div>
    </div>
  )
}

function MetaBox({ label, value }) {
  return (
    <div className="bg-zinc-950 border border-zinc-800 rounded px-2 py-1.5">
      <div className="text-zinc-200 font-semibold tabular-nums truncate">{value}</div>
      <div className="text-zinc-600 text-[9px] uppercase tracking-wider">{label}</div>
    </div>
  )
}

function SongRow({ song, expanded, onToggle, onQaPassed }) {
  const coverUrl = song.primary_artwork_asset_id
    ? resolveAudioUrl(`/api/v1/admin/visual/${song.primary_artwork_asset_id}.png`)
    : null
  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-900 overflow-hidden">
      <button
        onClick={onToggle}
        className="w-full flex items-center gap-3 px-4 py-3 hover:bg-zinc-900/60 transition-colors text-left"
      >
        {coverUrl ? (
          <img src={coverUrl} alt="" className="w-10 h-10 rounded object-cover border border-zinc-700 flex-shrink-0" />
        ) : (
          <FileAudio size={14} className="text-zinc-600 flex-shrink-0" />
        )}
        <div className="flex-1 min-w-0">
          <div className="text-sm font-semibold text-zinc-100 truncate">{song.title}</div>
          <div className="text-[10px] text-zinc-500 truncate">
            {song.primary_genre} · {song.song_id.slice(0, 8)}
          </div>
        </div>
        <StatusPill status={song.status} />
        <div className="text-[10px] text-zinc-600 tabular-nums w-20 text-right flex-shrink-0">
          {song.created_at ? new Date(song.created_at).toLocaleDateString() : ''}
        </div>
        {expanded ? <ChevronUp size={14} className="text-zinc-500" /> : <ChevronDown size={14} className="text-zinc-500" />}
      </button>
      {expanded && <SongDetailPanel songId={song.song_id} onQaPassed={onQaPassed} />}
    </div>
  )
}

export default function Songs() {
  const [statusFilter, setStatusFilter] = useState(null)
  const [expandedId, setExpandedId] = useState(null)
  const { data, isLoading, isError, error } = useSongs({ status: statusFilter })
  const markQa = useMarkQaPassed()
  const qc = useQueryClient()

  const songs = data?.data?.songs || []

  const handleQaPass = async (songId) => {
    await markQa.mutateAsync({ songId })
    qc.invalidateQueries({ queryKey: ['admin', 'songs'] })
  }

  const statusCounts = songs.reduce((acc, s) => {
    acc[s.status] = (acc[s.status] || 0) + 1
    return acc
  }, {})

  const filters = [
    { id: null,                   label: 'All' },
    { id: 'draft',                label: 'Draft' },
    { id: 'qa_pending',           label: 'QA Pending' },
    { id: 'qa_passed',            label: 'QA Passed' },
    { id: 'assigned_to_release',  label: 'Assigned' },
    { id: 'live',                 label: 'Live' },
  ]

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <div className="flex items-start justify-between mb-6">
        <div>
          <div className="flex items-center gap-3 mb-1">
            <Disc3 size={24} className="text-violet-400" />
            <h1 className="text-2xl font-bold text-zinc-100">Songs</h1>
          </div>
          <p className="text-sm text-zinc-500">
            Every song the system has produced. Click a row to play it and see its generation provenance.
          </p>
        </div>
      </div>

      {/* Filter bar */}
      <div className="flex gap-1 bg-zinc-900 border border-zinc-800 rounded-lg p-1 mb-4 w-fit">
        {filters.map(f => (
          <button
            key={f.id || 'all'}
            onClick={() => setStatusFilter(f.id)}
            className={`px-3 py-1 text-xs rounded font-medium transition-colors ${
              statusFilter === f.id
                ? 'bg-violet-600/30 text-violet-200 border border-violet-500/50'
                : 'text-zinc-500 hover:text-zinc-300'
            }`}
          >
            {f.label}
            {f.id && statusCounts[f.id] ? (
              <span className="ml-1.5 text-[10px] text-zinc-600">({statusCounts[f.id]})</span>
            ) : null}
          </button>
        ))}
      </div>

      {isLoading && (
        <div className="flex items-center justify-center py-20 text-zinc-500 gap-2">
          <Loader2 size={18} className="animate-spin" /> Loading songs...
        </div>
      )}

      {isError && (
        <div className="bg-rose-500/10 border border-rose-500/30 rounded-xl p-4 text-rose-300 text-sm">
          Failed to load songs: {error?.message}
        </div>
      )}

      {!isLoading && songs.length === 0 && (
        <div className="flex flex-col items-center justify-center py-20 text-center">
          <Music2 size={40} className="text-zinc-700 mb-3" />
          <div className="text-sm text-zinc-400 mb-1">No songs yet</div>
          <div className="text-xs text-zinc-600 max-w-sm">
            Use Song Lab to generate a song, or POST /admin/blueprints/{`{id}`}/generate-song directly against an approved blueprint.
          </div>
        </div>
      )}

      <div className="space-y-2">
        {songs.map(song => (
          <SongRow
            key={song.song_id}
            song={song}
            expanded={expandedId === song.song_id}
            onToggle={() => setExpandedId(expandedId === song.song_id ? null : song.song_id)}
            onQaPassed={handleQaPass}
          />
        ))}
      </div>

      {songs.length > 0 && (
        <div className="mt-6 flex items-center gap-3 text-[10px] text-zinc-600">
          <Clock size={10} /> Auto-refreshes every 15 seconds
        </div>
      )}
    </div>
  )
}
