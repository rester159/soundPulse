import { useState } from 'react'
import {
  Sliders, Loader2, Upload, Trash2, Music2, Play,
  Zap, Hash, AlertCircle, CheckCircle2, Sparkles, X,
} from 'lucide-react'
import { useQueryClient } from '@tanstack/react-query'
import {
  useInstrumentals, useUploadInstrumental, useDeleteInstrumental,
  useBlueprints, useGenerateSongWithInstrumental,
  getBaseUrl,
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
  const upload = useUploadInstrumental()
  const qc = useQueryClient()

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
    <form onSubmit={handleSubmit} className="bg-zinc-900/50 border border-zinc-800 rounded-lg p-4 space-y-3">
      <div className="flex items-center gap-2 text-sm font-medium text-zinc-300">
        <Upload size={14} /> Upload Instrumental
      </div>

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
          File (mp3/wav/flac, max 40MB) <span className="text-rose-400">*</span>
          <input
            type="file"
            accept="audio/mpeg,audio/mp3,audio/wav,audio/x-wav,audio/flac,audio/x-flac,audio/ogg,audio/aac,audio/mp4,audio/x-m4a,.mp3,.wav,.flac,.ogg,.aac,.m4a"
            onChange={(e) => setFile(e.target.files?.[0] || null)}
            className="w-full mt-1 px-3 py-2 bg-zinc-950 border border-zinc-800 rounded text-sm text-zinc-100 file:mr-3 file:px-3 file:py-1 file:bg-zinc-800 file:text-zinc-300 file:border-0 file:rounded file:text-xs"
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

      <div className="flex items-center justify-end gap-2 pt-1">
        <button
          type="submit"
          disabled={upload.isPending}
          className="px-4 py-2 bg-violet-600 hover:bg-violet-500 disabled:bg-zinc-800 disabled:text-zinc-600 text-white text-sm rounded flex items-center gap-2 transition-colors"
        >
          {upload.isPending ? <Loader2 size={14} className="animate-spin" /> : <Upload size={14} />}
          {upload.isPending ? 'Uploading…' : 'Upload'}
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
  const { data: bpData, isLoading } = useBlueprints({ limit: 100 })
  const generate = useGenerateSongWithInstrumental()
  const qc = useQueryClient()
  const [selected, setSelected] = useState(null)
  const [title, setTitle] = useState('')
  const [vocalGender, setVocalGender] = useState('')
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  const blueprints = (bpData?.data?.blueprints || bpData?.data || [])
    .filter(b => b.id && b.assigned_artist_id)

  const handleGenerate = async () => {
    setError(null)
    setResult(null)
    if (!selected) { setError('pick a blueprint'); return }
    try {
      const res = await generate.mutateAsync({
        blueprintId: selected.id,
        body: {
          instrumental_id: instrumental.instrumental_id,
          duration_seconds: 90,
          title: title.trim() || undefined,
          vocal_gender: vocalGender || undefined,
        },
      })
      setResult(res?.data)
      qc.invalidateQueries({ queryKey: ['admin', 'instrumentals'] })
    } catch (e) {
      setError(e?.response?.data?.detail || e?.message || 'generation failed')
    }
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

          <div>
            <div className="text-xs text-zinc-400 mb-2">Pick a blueprint (assigned artists only)</div>
            {isLoading ? (
              <div className="text-xs text-zinc-500 flex items-center gap-1"><Loader2 size={12} className="animate-spin" /> Loading…</div>
            ) : blueprints.length === 0 ? (
              <div className="text-xs text-zinc-500">No blueprints with an assigned artist. Assign one via the CEO gate first.</div>
            ) : (
              <div className="space-y-1 max-h-64 overflow-y-auto">
                {blueprints.map(b => {
                  const level = compatibilityLevel(b, instrumental)
                  const dot = { green: 'bg-emerald-400', yellow: 'bg-amber-400', red: 'bg-rose-400' }[level]
                  return (
                    <button
                      key={b.id}
                      onClick={() => setSelected(b)}
                      className={`w-full text-left px-3 py-2 rounded border ${selected?.id === b.id ? 'border-violet-500 bg-violet-500/10' : 'border-zinc-800 bg-zinc-900/40 hover:border-zinc-700'} flex items-center gap-2`}
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
              </div>
            )}
          </div>

          <div className="grid grid-cols-2 gap-3">
            <label className="text-xs text-zinc-400">
              Override title (optional)
              <input
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="auto from blueprint"
                className="w-full mt-1 px-3 py-2 bg-zinc-950 border border-zinc-800 rounded text-sm text-zinc-100 placeholder-zinc-600 focus:outline-none focus:border-violet-500"
              />
            </label>
            <label className="text-xs text-zinc-400">
              Vocal gender (optional)
              <select
                value={vocalGender}
                onChange={(e) => setVocalGender(e.target.value)}
                className="w-full mt-1 px-3 py-2 bg-zinc-950 border border-zinc-800 rounded text-sm text-zinc-100"
              >
                <option value="">auto</option>
                <option value="m">male</option>
                <option value="f">female</option>
              </select>
            </label>
          </div>

          {error && (
            <div className="text-xs text-rose-400 flex items-center gap-1">
              <AlertCircle size={12} /> {error}
            </div>
          )}

          {result && (
            <div className="bg-emerald-500/10 border border-emerald-500/30 rounded p-3 text-[11px] text-emerald-300 space-y-1">
              <div className="flex items-center gap-1"><CheckCircle2 size={12} /> Submitted to Kie.ai add-vocals</div>
              <div>song_id: {result.song_id}</div>
              <div>task_id: {result.task_id}</div>
              <div className="text-emerald-400/60">poll via /admin/music/generate/suno_kie/{result.task_id}</div>
            </div>
          )}

          <div className="flex items-center justify-end gap-2">
            <button
              onClick={onClose}
              className="px-3 py-2 text-zinc-400 text-xs hover:text-zinc-200"
            >
              Close
            </button>
            <button
              onClick={handleGenerate}
              disabled={!selected || generate.isPending}
              className="px-4 py-2 bg-violet-600 hover:bg-violet-500 disabled:bg-zinc-800 disabled:text-zinc-600 text-white text-sm rounded flex items-center gap-2 transition-colors"
            >
              {generate.isPending ? <Loader2 size={14} className="animate-spin" /> : <Sparkles size={14} />}
              {generate.isPending ? 'Submitting…' : 'Generate song ($0.06)'}
            </button>
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
