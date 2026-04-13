import { useState, useRef, useEffect } from 'react'
import {
  Sliders, Loader2, Upload, Trash2, Music2, Play,
  Zap, Hash, AlertCircle, CheckCircle2, Sparkles, X, FileAudio,
} from 'lucide-react'
import { useQueryClient } from '@tanstack/react-query'
import {
  useInstrumentals, useUploadInstrumental, useDeleteInstrumental,
  useBlueprints, useAIArtists, useGenerateInstrumentalSongForArtist,
  useMusicPoll, getBaseUrl,
} from '../hooks/useSoundPulse'

function formatBytes(b) {
  if (!b) return '—'
  if (b < 1024) return `${b} B`
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(0)} KB`
  return `${(b / (1024 * 1024)).toFixed(1)} MB`
}

function formatDuration(s) {
  if (!s || s <= 0) return null
  const m = Math.floor(s / 60)
  const r = Math.round(s % 60)
  return `${m}:${String(r).padStart(2, '0')}`
}

function UploadForm({ onDone }) {
  const [title, setTitle] = useState('')
  const [file, setFile] = useState(null)
  const [tempoBpm, setTempoBpm] = useState('')
  const [keyHint, setKeyHint] = useState('')
  const [genreHint, setGenreHint] = useState('')
  const [notes, setNotes] = useState('')
  const [error, setError] = useState(null)
  const [dragOver, setDragOver] = useState(false)
  const fileInputRef = useRef(null)
  const upload = useUploadInstrumental()
  const qc = useQueryClient()

  const openFilePicker = () => {
    fileInputRef.current?.click()
  }

  const handleFileChange = (f) => {
    if (!f) return
    setFile(f)
    setError(null)
    // Auto-fill title from filename if title is empty
    if (!title.trim()) {
      const name = f.name.replace(/\.[^.]+$/, '').replace(/[_-]+/g, ' ')
      setTitle(name)
    }
  }

  const handleDrop = (e) => {
    e.preventDefault()
    setDragOver(false)
    const f = e.dataTransfer.files?.[0]
    if (f) handleFileChange(f)
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError(null)
    if (!title.trim() || !file) {
      setError('Title and file are required')
      return
    }
    try {
      await upload.mutateAsync({
        title: title.trim(),
        file,
        tempo_bpm: tempoBpm ? parseFloat(tempoBpm) : undefined,
        key_hint: keyHint.trim() || undefined,
        genre_hint: genreHint.trim() || undefined,
        notes: notes.trim() || undefined,
      })
      setTitle('')
      setFile(null)
      setTempoBpm('')
      setKeyHint('')
      setGenreHint('')
      setNotes('')
      qc.invalidateQueries({ queryKey: ['admin', 'instrumentals'] })
      onDone?.()
    } catch (e) {
      setError(e?.response?.data?.detail || e?.message || 'Upload failed')
    }
  }

  return (
    <form onSubmit={handleSubmit} className="bg-zinc-900/50 border border-zinc-800 rounded-lg p-4 space-y-4">
      <div className="flex items-center gap-2 text-sm font-medium text-zinc-300">
        <Upload size={14} /> Upload Instrumental
      </div>

      {/* Hidden native file input — triggered by the dropzone click */}
      <input
        ref={fileInputRef}
        type="file"
        accept="audio/mpeg,audio/mp3,audio/wav,audio/x-wav,audio/flac,audio/x-flac,audio/ogg,audio/aac,audio/mp4,audio/x-m4a,.mp3,.wav,.flac,.ogg,.aac,.m4a"
        onChange={(e) => handleFileChange(e.target.files?.[0])}
        className="hidden"
      />

      {/* Big obvious drop/click zone */}
      <button
        type="button"
        onClick={openFilePicker}
        onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        className={`w-full border-2 border-dashed rounded-lg p-6 flex flex-col items-center gap-2 transition-colors cursor-pointer ${
          dragOver
            ? 'border-violet-500 bg-violet-500/10'
            : file
              ? 'border-emerald-500/50 bg-emerald-500/5 hover:bg-emerald-500/10'
              : 'border-zinc-700 bg-zinc-950/50 hover:border-violet-500 hover:bg-zinc-900'
        }`}
      >
        {file ? (
          <>
            <FileAudio size={28} className="text-emerald-400" />
            <div className="text-sm font-medium text-zinc-100">{file.name}</div>
            <div className="text-[11px] text-zinc-500">
              {formatBytes(file.size)} · {file.type || 'audio'}
            </div>
            <div className="text-[10px] text-violet-400 mt-1">click to choose a different file</div>
          </>
        ) : (
          <>
            <Upload size={28} className="text-zinc-500" />
            <div className="text-sm font-medium text-zinc-200">
              Click to choose an audio file
            </div>
            <div className="text-[11px] text-zinc-500">
              or drag and drop · mp3 / wav / flac / ogg / aac / m4a · max 40MB
            </div>
          </>
        )}
      </button>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <label className="text-xs text-zinc-400">
          Title <span className="text-rose-400">*</span>
          <input
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="e.g. Kingston Rooftop Beat"
            className="w-full mt-1 px-3 py-2 bg-zinc-950 border border-zinc-800 rounded text-sm text-zinc-100 placeholder-zinc-600 focus:outline-none focus:border-violet-500"
          />
        </label>
        <label className="text-xs text-zinc-400">
          Tempo BPM
          <input
            type="number"
            step="0.1"
            value={tempoBpm}
            onChange={(e) => setTempoBpm(e.target.value)}
            placeholder="e.g. 92"
            className="w-full mt-1 px-3 py-2 bg-zinc-950 border border-zinc-800 rounded text-sm text-zinc-100 placeholder-zinc-600 focus:outline-none focus:border-violet-500"
          />
        </label>
        <label className="text-xs text-zinc-400">
          Key hint
          <input
            type="text"
            value={keyHint}
            onChange={(e) => setKeyHint(e.target.value)}
            placeholder="e.g. A minor"
            className="w-full mt-1 px-3 py-2 bg-zinc-950 border border-zinc-800 rounded text-sm text-zinc-100 placeholder-zinc-600 focus:outline-none focus:border-violet-500"
          />
        </label>
        <label className="text-xs text-zinc-400">
          Genre hint
          <input
            type="text"
            value={genreHint}
            onChange={(e) => setGenreHint(e.target.value)}
            placeholder="e.g. reggae, hip-hop, k-pop"
            className="w-full mt-1 px-3 py-2 bg-zinc-950 border border-zinc-800 rounded text-sm text-zinc-100 placeholder-zinc-600 focus:outline-none focus:border-violet-500"
          />
        </label>
        <label className="text-xs text-zinc-400">
          Notes
          <input
            type="text"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="free text"
            className="w-full mt-1 px-3 py-2 bg-zinc-950 border border-zinc-800 rounded text-sm text-zinc-100 placeholder-zinc-600 focus:outline-none focus:border-violet-500"
          />
        </label>
      </div>

      {error && (
        <div className="text-xs text-rose-400 flex items-center gap-1">
          <AlertCircle size={12} /> {error}
        </div>
      )}

      <div className="flex items-center justify-between gap-2 pt-1">
        <div className="text-[11px] text-zinc-500">
          {!file && 'Pick an audio file above to enable submission'}
          {file && !title.trim() && 'Title is auto-filled from the filename — you can edit it'}
          {file && title.trim() && 'Ready to submit'}
        </div>
        <button
          type="submit"
          disabled={upload.isPending || !file || !title.trim()}
          className="px-5 py-2.5 bg-violet-600 hover:bg-violet-500 disabled:bg-zinc-800 disabled:text-zinc-600 disabled:cursor-not-allowed text-white text-sm font-medium rounded flex items-center gap-2 transition-colors"
        >
          {upload.isPending ? <Loader2 size={14} className="animate-spin" /> : <Upload size={14} />}
          {upload.isPending ? 'Uploading…' : 'Submit upload'}
        </button>
      </div>
    </form>
  )
}

function compatibilityLevel(blueprint, inst) {
  // GREEN if blueprint genre top-level token matches inst.genre_hint
  // and tempos are within ±10 BPM. YELLOW if tempos ±20. RED if outside.
  // If tempo is unknown on either side, fall back to genre-only match.
  const g1 = (blueprint.primary_genre || '').toLowerCase().split('.')[0]
  const g2 = (inst.genre_hint || '').toLowerCase().split('.')[0]
  const genreMatch = g1 && g2 && g1 === g2
  const tempo1 = blueprint.tempo_bpm || null
  const tempo2 = inst.tempo_bpm || null
  if (tempo1 && tempo2) {
    const diff = Math.abs(tempo1 - tempo2)
    if (diff <= 10 && (genreMatch || !g2)) return 'green'
    if (diff <= 20) return 'yellow'
    return 'red'
  }
  return genreMatch ? 'green' : 'yellow'
}

function BlueprintPickerModal({ instrumental, onClose }) {
  const { data: artistsData, isLoading: artistsLoading } = useAIArtists('active')
  const { data: bpData } = useBlueprints({ limit: 100 })
  const generate = useGenerateInstrumentalSongForArtist()
  const qc = useQueryClient()
  const [selectedArtist, setSelectedArtist] = useState(null)
  const [selectedBlueprint, setSelectedBlueprint] = useState(null)
  const [title, setTitle] = useState('')
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [elapsedSec, setElapsedSec] = useState(0)
  const [submittedAt, setSubmittedAt] = useState(null)

  // Poll the generation task once we have a task_id. useMusicPoll auto-
  // polls while status is pending/processing and stops at terminal.
  const poll = useMusicPoll('suno_kie', result?.task_id, { enabled: !!result?.task_id })
  const pollState = poll.data?.data
  const pollStatus = pollState?.status
  const audioUrl = pollState?.audio_url
  const pollError = pollState?.error

  // Elapsed-seconds ticker while a task is in flight
  useEffect(() => {
    if (!submittedAt || pollStatus === 'succeeded' || pollStatus === 'failed') return
    const iv = setInterval(() => {
      setElapsedSec(Math.floor((Date.now() - submittedAt) / 1000))
    }, 1000)
    return () => clearInterval(iv)
  }, [submittedAt, pollStatus])

  const inFlight = !!result?.task_id && pollStatus !== 'succeeded' && pollStatus !== 'failed'

  const artists = artistsData?.data?.artists || []
  const allBlueprints = (bpData?.data?.blueprints || bpData?.data || []).filter(b => b.id)
  // Only show blueprints that match the selected artist OR are unassigned
  const blueprintsForArtist = selectedArtist
    ? allBlueprints.filter(
        b => !b.assigned_artist_id || b.assigned_artist_id === selectedArtist.artist_id,
      )
    : []

  const handleGenerate = async () => {
    setError(null)
    setResult(null)
    setElapsedSec(0)
    setSubmittedAt(null)
    if (!selectedArtist) { setError('Pick an artist'); return }
    try {
      const res = await generate.mutateAsync({
        instrumentalId: instrumental.instrumental_id,
        body: {
          artist_id: selectedArtist.artist_id,
          blueprint_id: selectedBlueprint?.id || undefined,
          duration_seconds: 90,
          title: title.trim() || undefined,
        },
      })
      setResult(res?.data)
      setSubmittedAt(Date.now())
      qc.invalidateQueries({ queryKey: ['admin', 'instrumentals'] })
    } catch (e) {
      setError(e?.response?.data?.detail || e?.message || 'generation failed')
    }
  }

  const handleReset = () => {
    setResult(null)
    setSubmittedAt(null)
    setElapsedSec(0)
    setError(null)
    generate.reset()
  }

  const fmtElapsed = (s) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`
  const resolveUrl = (url) => {
    if (!url) return url
    if (/^https?:\/\//i.test(url)) return url
    if (url.startsWith('/api/v1/')) {
      const base = getBaseUrl().replace(/\/api\/v1\/?$/, '')
      return base + url
    }
    return url
  }

  return (
    <div className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-6" onClick={onClose}>
      <div className="bg-zinc-950 border border-zinc-800 rounded-xl max-w-2xl w-full max-h-[85vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between p-4 border-b border-zinc-800">
          <div className="flex items-center gap-2 text-sm font-semibold text-zinc-200">
            <Sparkles size={14} className="text-violet-400" />
            Generate with "{instrumental.title}"
          </div>
          <button onClick={onClose} className="text-zinc-500 hover:text-zinc-300">
            <X size={16} />
          </button>
        </div>

        <div className="p-4 space-y-4">
          <div className="text-[11px] text-zinc-500">
            Instrumental: {instrumental.tempo_bpm && `${instrumental.tempo_bpm} BPM · `}
            {instrumental.key_hint && `${instrumental.key_hint} · `}
            {instrumental.genre_hint}
          </div>

          {/* ARTIST selector (primary) */}
          <div>
            <div className="text-xs text-zinc-400 mb-2">
              Pick the artist <span className="text-rose-400">*</span>
            </div>
            {artistsLoading ? (
              <div className="text-xs text-zinc-500 flex items-center gap-1">
                <Loader2 size={12} className="animate-spin" /> Loading roster…
              </div>
            ) : artists.length === 0 ? (
              <div className="text-xs text-zinc-500">
                No active AI artists in the roster. Create one via /artists first.
              </div>
            ) : (
              <div className="space-y-1 max-h-56 overflow-y-auto">
                {artists.map(a => {
                  const selected = selectedArtist?.artist_id === a.artist_id
                  const genreBadge = a.primary_genre || '—'
                  const edge = a.edge_profile || 'flirty_edge'
                  const gender = a.gender_presentation || 'unspecified'
                  return (
                    <button
                      key={a.artist_id}
                      onClick={() => { setSelectedArtist(a); setSelectedBlueprint(null) }}
                      className={`w-full text-left px-3 py-2 rounded border flex items-center gap-3 transition-colors ${
                        selected
                          ? 'border-violet-500 bg-violet-500/10'
                          : 'border-zinc-800 bg-zinc-900/40 hover:border-zinc-700'
                      }`}
                    >
                      <div className="flex-1 min-w-0">
                        <div className="text-sm text-zinc-100 truncate flex items-center gap-2">
                          {a.stage_name}
                          {a.ceo_approved && (
                            <span className="text-[9px] px-1 py-0.5 bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 rounded">
                              approved
                            </span>
                          )}
                        </div>
                        <div className="text-[10px] text-zinc-500 flex items-center gap-2 mt-0.5">
                          <span className="text-violet-300">{genreBadge}</span>
                          <span>·</span>
                          <span>{gender}</span>
                          <span>·</span>
                          <span className="uppercase tracking-wider">{edge}</span>
                          {a.song_count !== undefined && (
                            <>
                              <span>·</span>
                              <span>{a.song_count} songs</span>
                            </>
                          )}
                        </div>
                      </div>
                    </button>
                  )
                })}
              </div>
            )}
          </div>

          {/* BLUEPRINT selector (secondary, optional) */}
          {selectedArtist && (
            <div>
              <div className="text-xs text-zinc-400 mb-2">
                Pick a blueprint for theme/style <span className="text-zinc-600">(optional)</span>
              </div>
              <div className="space-y-1 max-h-40 overflow-y-auto">
                <button
                  onClick={() => setSelectedBlueprint(null)}
                  className={`w-full text-left px-3 py-2 rounded border flex items-center gap-2 ${
                    !selectedBlueprint
                      ? 'border-violet-500 bg-violet-500/10'
                      : 'border-zinc-800 bg-zinc-900/40 hover:border-zinc-700'
                  }`}
                >
                  <div className="flex-1 min-w-0">
                    <div className="text-xs text-zinc-200">Freeform — no blueprint</div>
                    <div className="text-[10px] text-zinc-500">
                      Generate with just the artist's voice + edge profile, no specific theme
                    </div>
                  </div>
                </button>
                {blueprintsForArtist.map(b => {
                  const level = compatibilityLevel(b, instrumental)
                  const dot = { green: 'bg-emerald-400', yellow: 'bg-amber-400', red: 'bg-rose-400' }[level]
                  const isSel = selectedBlueprint?.id === b.id
                  return (
                    <button
                      key={b.id}
                      onClick={() => setSelectedBlueprint(b)}
                      className={`w-full text-left px-3 py-2 rounded border flex items-center gap-2 ${
                        isSel ? 'border-violet-500 bg-violet-500/10' : 'border-zinc-800 bg-zinc-900/40 hover:border-zinc-700'
                      }`}
                    >
                      <span className={`w-2 h-2 rounded-full ${dot}`} title={`compatibility: ${level}`} />
                      <div className="flex-1 min-w-0">
                        <div className="text-xs text-zinc-200 truncate">{b.title || b.primary_genre || 'Untitled'}</div>
                        <div className="text-[10px] text-zinc-500 flex items-center gap-2">
                          <span>{b.primary_genre}</span>
                          {b.tempo_bpm && <span>· {b.tempo_bpm} BPM</span>}
                        </div>
                      </div>
                    </button>
                  )
                })}
                {blueprintsForArtist.length === 0 && (
                  <div className="text-[11px] text-zinc-600 py-2 px-1">
                    No blueprints assigned to this artist. Generation will proceed in freeform mode.
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Title override */}
          <label className="block text-xs text-zinc-400">
            Override title <span className="text-zinc-600">(optional)</span>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="auto from blueprint or artist"
              className="w-full mt-1 px-3 py-2 bg-zinc-950 border border-zinc-800 rounded text-sm text-zinc-100 placeholder-zinc-600 focus:outline-none focus:border-violet-500"
            />
          </label>

          {error && (
            <div className="text-xs text-rose-400 flex items-center gap-1">
              <AlertCircle size={12} /> {error}
            </div>
          )}

          {/* In-flight progress display */}
          {result && (
            <div className={`border rounded-lg p-3 text-[11px] space-y-2 ${
              pollStatus === 'succeeded' ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
              : pollStatus === 'failed' ? 'bg-rose-500/10 border-rose-500/30 text-rose-300'
              : 'bg-violet-500/10 border-violet-500/30 text-violet-300'
            }`}>
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2 text-sm font-medium">
                  {pollStatus === 'succeeded' && <><CheckCircle2 size={14} /> Ready to play</>}
                  {pollStatus === 'failed' && <><AlertCircle size={14} /> Generation failed</>}
                  {(pollStatus === 'pending' || !pollStatus) && <><Loader2 size={14} className="animate-spin" /> Queued at Suno — waiting to start…</>}
                  {pollStatus === 'processing' && <><Loader2 size={14} className="animate-spin" /> Suno generating…</>}
                </div>
                <div className="tabular-nums font-mono">
                  {fmtElapsed(elapsedSec)}
                </div>
              </div>

              {/* Progress bar — fills smoothly while in flight; Kie.ai Suno
                  typically takes 60-180s so we cap at 210s linear progress
                  and freeze at 95% if it runs over, then jump to 100% on
                  terminal. */}
              {inFlight && (
                <div className="w-full h-1 bg-zinc-800 rounded overflow-hidden">
                  <div
                    className="h-full bg-violet-500 transition-all duration-1000"
                    style={{ width: `${Math.min(95, (elapsedSec / 210) * 100)}%` }}
                  />
                </div>
              )}

              <div className="text-[10px] opacity-70 font-mono">
                artist: {result.artist_stage_name} · song_id: {result.song_id?.slice(0, 8)} · task: {result.task_id?.slice(0, 12)}
              </div>

              {pollStatus === 'succeeded' && audioUrl && (
                <div className="space-y-1 pt-1">
                  <audio
                    controls
                    src={resolveUrl(audioUrl)}
                    className="w-full"
                    style={{ filter: 'invert(0.9) hue-rotate(180deg)' }}
                  />
                  <div className="text-[10px] opacity-70">
                    {pollState?.duration_seconds?.toFixed(1)}s · ${pollState?.actual_cost_usd?.toFixed(3)}
                  </div>
                </div>
              )}

              {pollStatus === 'failed' && (
                <div className="text-[11px]">
                  {pollError || 'unknown error'}
                </div>
              )}
            </div>
          )}

          <div className="flex items-center justify-between gap-2 pt-2 border-t border-zinc-800">
            <div className="text-[11px] text-zinc-500">
              {!selectedArtist && !result && 'Pick an artist to enable submission'}
              {selectedArtist && !result && !selectedBlueprint && `Generating for ${selectedArtist.stage_name} in freeform mode`}
              {selectedArtist && !result && selectedBlueprint && `${selectedArtist.stage_name} · ${selectedBlueprint.primary_genre || 'blueprint'}`}
              {inFlight && `${selectedArtist?.stage_name} · Kie.ai Suno usually finishes in ~60-180s`}
              {pollStatus === 'succeeded' && 'Finished — song is in the Songs page'}
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={onClose}
                className="px-3 py-2 text-zinc-400 text-xs hover:text-zinc-200"
              >
                Close
              </button>
              {pollStatus === 'failed' && (
                <button
                  onClick={handleReset}
                  className="px-3 py-2 text-xs text-violet-300 hover:text-violet-200 underline"
                >
                  Retry
                </button>
              )}
              <button
                onClick={handleGenerate}
                disabled={!selectedArtist || generate.isPending || inFlight || pollStatus === 'succeeded'}
                className="px-4 py-2 bg-violet-600 hover:bg-violet-500 disabled:bg-zinc-800 disabled:text-zinc-600 disabled:cursor-not-allowed text-white text-sm rounded flex items-center gap-2 transition-colors"
              >
                {generate.isPending || inFlight ? <Loader2 size={14} className="animate-spin" /> : <Sparkles size={14} />}
                {generate.isPending ? 'Submitting…'
                  : inFlight ? `Generating… ${fmtElapsed(elapsedSec)}`
                  : pollStatus === 'succeeded' ? 'Done'
                  : 'Generate song ($0.06)'}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

function InstrumentalRow({ inst, onDelete, onGenerate }) {
  const base = getBaseUrl().replace(/\/api\/v1$/, '')
  const streamUrl = `${base}${inst.public_url_path}`
  return (
    <div className="bg-zinc-900/40 border border-zinc-800 rounded-lg p-3 flex items-center gap-4">
      <Music2 size={18} className="text-violet-400 flex-shrink-0" />
      <div className="flex-1 min-w-0">
        <div className="text-sm font-medium text-zinc-200 truncate">{inst.title}</div>
        <div className="text-[11px] text-zinc-500 mt-0.5 flex items-center gap-3 flex-wrap">
          {inst.tempo_bpm && <span className="flex items-center gap-1"><Zap size={10} /> {inst.tempo_bpm} BPM</span>}
          {inst.key_hint && <span className="flex items-center gap-1"><Hash size={10} /> {inst.key_hint}</span>}
          {inst.genre_hint && <span>{inst.genre_hint}</span>}
          <span>{formatBytes(inst.size_bytes)}</span>
          {inst.duration_seconds && <span>{formatDuration(inst.duration_seconds)}</span>}
          {inst.usage_count > 0 && <span className="text-violet-400">used {inst.usage_count}×</span>}
        </div>
      </div>
      <audio controls src={streamUrl} className="h-8 max-w-[220px]" preload="none" />
      <button
        onClick={() => onGenerate(inst)}
        className="px-3 py-1.5 bg-violet-600 hover:bg-violet-500 text-white text-xs rounded flex items-center gap-1 transition-colors"
        title="Generate song over this beat"
      >
        <Sparkles size={12} /> Generate
      </button>
      <button
        onClick={() => onDelete(inst.instrumental_id, inst.title)}
        className="p-1.5 text-zinc-500 hover:text-rose-400 transition-colors"
        title="Delete"
      >
        <Trash2 size={14} />
      </button>
    </div>
  )
}

export default function Instrumentals() {
  const { data, isLoading, error } = useInstrumentals(true)
  const del = useDeleteInstrumental()
  const qc = useQueryClient()
  const [pickerFor, setPickerFor] = useState(null)
  const instrumentals = data?.data?.instrumentals || []

  const handleDelete = async (id, title) => {
    if (!window.confirm(`Delete instrumental "${title}"? It stays in the DB (soft delete) but won't appear in pickers.`)) return
    await del.mutateAsync({ instrumental_id: id })
    qc.invalidateQueries({ queryKey: ['admin', 'instrumentals'] })
  }

  return (
    <div className="p-6 space-y-6 max-w-6xl mx-auto">
      <div className="flex items-center gap-3">
        <Sliders className="text-violet-400" size={24} />
        <div>
          <h1 className="text-xl font-semibold text-zinc-100">Instrumentals</h1>
          <p className="text-xs text-zinc-500">
            Upload backing tracks for Suno "add-vocals" generation. Suno writes vocals that lock to the instrumental's tempo, key, and structure — the beat stays fixed.
          </p>
        </div>
      </div>

      <UploadForm />

      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <div className="text-xs uppercase tracking-wider text-zinc-500">
            Library ({instrumentals.length})
          </div>
          {instrumentals.length > 0 && (
            <div className="text-[10px] text-zinc-600 flex items-center gap-1">
              <CheckCircle2 size={10} className="text-emerald-400" />
              Public URL available for Kie.ai add-vocals
            </div>
          )}
        </div>

        {isLoading && (
          <div className="flex items-center gap-2 text-sm text-zinc-500 p-4">
            <Loader2 size={14} className="animate-spin" /> Loading…
          </div>
        )}
        {error && (
          <div className="text-xs text-rose-400 p-4 flex items-center gap-1">
            <AlertCircle size={12} /> {error?.message}
          </div>
        )}
        {!isLoading && instrumentals.length === 0 && (
          <div className="bg-zinc-900/30 border border-zinc-800 border-dashed rounded-lg p-8 text-center">
            <Music2 className="mx-auto text-zinc-700 mb-2" size={32} />
            <div className="text-sm text-zinc-400">No instrumentals yet</div>
            <div className="text-xs text-zinc-600 mt-1">Upload a beat above to get started</div>
          </div>
        )}
        {instrumentals.map((inst) => (
          <InstrumentalRow
            key={inst.instrumental_id}
            inst={inst}
            onDelete={handleDelete}
            onGenerate={(i) => setPickerFor(i)}
          />
        ))}
      </div>

      {pickerFor && (
        <BlueprintPickerModal
          instrumental={pickerFor}
          onClose={() => setPickerFor(null)}
        />
      )}

      <div className="bg-zinc-900/30 border border-zinc-800 rounded-lg p-4 text-[11px] text-zinc-500 space-y-2">
        <div className="font-medium text-zinc-400">How this pairs with SongLab</div>
        <ol className="list-decimal list-inside space-y-1">
          <li>Pick an instrumental here (upload one if needed).</li>
          <li>Go to Song Lab and choose a blueprint whose genre/tempo is compatible.</li>
          <li>Toggle "Use instrumental" and select from the picker.</li>
          <li>Suno receives the public URL and writes vocals that lock to the beat.</li>
        </ol>
        <div className="pt-2">
          <div className="font-medium text-zinc-400">What Suno CAN adapt</div>
          <div>Vocal timbre · delivery · melody · cultural flavor · genre blend on top of the beat.</div>
        </div>
        <div>
          <div className="font-medium text-zinc-400">What Suno CANNOT adapt</div>
          <div>Tempo · key · chord progression · rhythmic feel · production. All locked by the instrumental.</div>
        </div>
      </div>
    </div>
  )
}
