/**
 * Song Lab (#28).
 *
 * The single entry point for song generation post-pivot.
 *
 * Top element: "Add song" button.
 *
 * Each click adds a draft row with two dropdowns:
 *   1. Genre blueprint
 *   2. Artist (brings in persona/lyrical/voice DNA)
 * When both are selected, the "Create song" button becomes active.
 *
 * Clicking "Create song" opens the song window modal with everything
 * pre-populated (genre, blueprint, artist, structure filtered to
 * structures associated with the genre, content rating Clean default,
 * theme artist-default). All editable. The "Generate smart prompt"
 * button composes the prompt + drafts the lyrics via LLM. The user
 * can edit either textarea, then click "Generate" to fire the music
 * provider call.
 *
 * Drafts are in-memory only — they exist until the user generates
 * (which persists to songs_master) or removes the row.
 */
import { useEffect, useMemo, useState } from 'react'
import {
  Music, Plus, Loader2, X, Trash2, AlertCircle, CheckCircle2, Wand2, Play,
} from 'lucide-react'
import {
  useBlueprints, useAIArtists, useStructuresForGenre, useSongLabPreview,
  useSongLabGenerate,
} from '../hooks/useSoundPulse'

const THEME_OPTIONS = [
  { value: 'artist_default',     label: 'Artist default' },
  { value: 'genre_default',      label: 'Genre default' },
  { value: 'love_relationships', label: 'Love relationships' },
  { value: 'sex',                label: 'Sex' },
  { value: 'introspection',      label: 'Introspection' },
  { value: 'family',             label: 'Family' },
  { value: 'god',                label: 'God / spirituality' },
  { value: 'partying',           label: 'Partying / having fun' },
  { value: 'free_text',          label: 'Free text — type my own' },
]

let DRAFT_COUNTER = 0
const newDraft = () => ({
  draftId: ++DRAFT_COUNTER,
  blueprintId: '',
  artistId: '',
})

// One row in the top-of-page draft list.
function DraftRow({ draft, blueprints, artists, onChange, onRemove, onCreate }) {
  const ready = !!(draft.blueprintId && draft.artistId)
  const bp = blueprints.find((b) => b.id === draft.blueprintId)
  const artist = artists.find((a) => a.artist_id === draft.artistId)

  return (
    <div className="border-t border-zinc-800 first:border-t-0 px-3 py-3 hover:bg-zinc-900/30 flex items-center gap-3 flex-wrap md:flex-nowrap">
      <span className="text-[10px] uppercase tracking-wider text-zinc-600 w-12 flex-shrink-0">draft</span>

      <select
        value={draft.blueprintId}
        onChange={(e) => onChange(draft.draftId, { blueprintId: e.target.value })}
        className="flex-1 min-w-48 px-3 py-2 bg-zinc-900 border border-zinc-800 rounded text-sm text-zinc-100"
      >
        <option value="">— select genre blueprint —</option>
        {blueprints.map((b) => (
          <option key={b.id} value={b.id}>
            {(b.name || b.primary_genre || b.genre_id) + (b.is_genre_default ? ' (base)' : '')}
          </option>
        ))}
      </select>

      <select
        value={draft.artistId}
        onChange={(e) => onChange(draft.draftId, { artistId: e.target.value })}
        className="flex-1 min-w-48 px-3 py-2 bg-zinc-900 border border-zinc-800 rounded text-sm text-zinc-100"
      >
        <option value="">— select artist —</option>
        {artists.map((a) => (
          <option key={a.artist_id} value={a.artist_id}>
            {a.stage_name}{a.primary_genre ? ` · ${a.primary_genre}` : ''}
          </option>
        ))}
      </select>

      <button
        onClick={() => onCreate(draft.draftId)}
        disabled={!ready}
        className={`flex items-center gap-1.5 px-4 py-2 text-xs font-medium rounded transition-colors flex-shrink-0 ${
          ready
            ? 'bg-emerald-600 hover:bg-emerald-500 text-white'
            : 'bg-zinc-800 text-zinc-600 cursor-not-allowed'
        }`}
      >
        <Music size={12} /> Create song
      </button>

      <button
        onClick={() => onRemove(draft.draftId)}
        className="p-2 text-zinc-500 hover:text-rose-300 hover:bg-rose-500/10 rounded flex-shrink-0"
        title="Remove this draft"
      >
        <Trash2 size={12} />
      </button>
    </div>
  )
}

// The song window modal — fully editable, two-step generation.
function SongWindow({ initialDraft, blueprints, artists, onClose, onGenerated }) {
  const [blueprintId, setBlueprintId] = useState(initialDraft.blueprintId)
  const [artistId, setArtistId] = useState(initialDraft.artistId)

  const bp = blueprints.find((b) => b.id === blueprintId)
  const artist = artists.find((a) => a.artist_id === artistId)
  const primaryGenre = bp?.primary_genre || bp?.genre_id || artist?.primary_genre || ''

  // Structure picker — fetch structures whose primary_genre matches the
  // blueprint's genre or any of its ancestors. Default to the most-
  // specific match (first in the returned list).
  const structuresQ = useStructuresForGenre(primaryGenre)
  const structureItems = structuresQ.data?.data?.items || structuresQ.data?.items || []
  const [structureIdx, setStructureIdx] = useState(0)

  useEffect(() => { setStructureIdx(0) }, [structureItems.length, primaryGenre])

  const chosenStructure = structureItems[structureIdx] || null

  // Content rating — Clean default per the user's spec.
  const [contentRating, setContentRating] = useState('clean')

  // Theme — artist_default per the user's spec.
  const [themeChoice, setThemeChoice] = useState('artist_default')
  const [themeFreeText, setThemeFreeText] = useState('')
  const themeForApi = themeChoice === 'free_text' ? themeFreeText.trim() : themeChoice

  // Two textareas the LLM/orchestrator populate, then user can edit.
  const [prompt, setPrompt] = useState('')
  const [lyrics, setLyrics] = useState('')

  // Provider — keep the existing menu small for now; default to suno_kie
  // since that's what the rest of the app uses.
  const [provider, setProvider] = useState('suno_kie')
  const [duration, setDuration] = useState(180)

  const preview = useSongLabPreview()
  const generate = useSongLabGenerate()
  const [genResult, setGenResult] = useState(null)
  const [previewError, setPreviewError] = useState(null)
  const [generateError, setGenerateError] = useState(null)

  const canPreview = !!(blueprintId && artistId) && (themeChoice !== 'free_text' || themeFreeText.trim())
  const canGenerate = !!prompt.trim() && !!(blueprintId && artistId)

  const handlePreview = async () => {
    setPreviewError(null)
    try {
      const res = await preview.mutateAsync({
        blueprint_id: blueprintId,
        artist_id: artistId,
        theme: themeForApi || null,
        content_rating: contentRating,
        structure_override: chosenStructure?.structure || null,
        primary_genre_override: primaryGenre || null,
      })
      const data = res?.data || {}
      setPrompt(data.prompt || '')
      setLyrics(data.lyrics || '')
      if (data.lyrics_error) {
        setPreviewError(`Lyrics: ${data.lyrics_error}`)
      }
    } catch (e) {
      setPreviewError(e?.response?.data?.detail || e?.message || 'preview failed')
    }
  }

  const handleGenerate = async () => {
    setGenerateError(null)
    setGenResult(null)
    try {
      const body = {
        provider,
        duration_seconds: duration,
        artist_id: artistId,
        theme: themeForApi || null,
        content_rating_override: contentRating,
        structure_override: chosenStructure?.structure || null,
        primary_genre_override: primaryGenre || null,
        prompt_override: prompt.trim() || undefined,
        lyrics_override: lyrics.trim() || undefined,
      }
      const res = await generate.mutateAsync({ blueprintId, body })
      setGenResult(res?.data)
      setTimeout(() => { onGenerated?.(res?.data); onClose?.() }, 1800)
    } catch (e) {
      setGenerateError(e?.response?.data?.detail || e?.message || 'generation failed')
    }
  }

  return (
    <div className="fixed inset-0 z-50 bg-black/80 flex items-start justify-center p-3 overflow-y-auto" onClick={onClose}>
      <div className="bg-zinc-950 border border-zinc-800 rounded-xl max-w-4xl w-full my-3" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between p-4 border-b border-zinc-800 sticky top-0 bg-zinc-950 z-10">
          <div className="flex items-center gap-2 text-sm font-semibold text-zinc-200">
            <Music size={14} className="text-violet-400" />
            New song — {artist?.stage_name || '?'} · {primaryGenre || '?'}
          </div>
          <button onClick={onClose} className="text-zinc-500 hover:text-zinc-300"><X size={16} /></button>
        </div>

        <div className="p-5 space-y-5">
          {/* Pre-populated, editable fields */}
          <section className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <Field label="Genre">
              <input
                type="text"
                value={primaryGenre}
                disabled
                className="w-full px-3 py-2 bg-zinc-900 border border-zinc-800 rounded text-sm text-zinc-300 font-mono"
              />
            </Field>
            <Field label="Blueprint">
              <select
                value={blueprintId}
                onChange={(e) => setBlueprintId(e.target.value)}
                className="w-full px-3 py-2 bg-zinc-900 border border-zinc-800 rounded text-sm text-zinc-100"
              >
                {blueprints.map((b) => (
                  <option key={b.id} value={b.id}>
                    {(b.name || b.primary_genre || b.genre_id) + (b.is_genre_default ? ' (base)' : '')}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Artist">
              <select
                value={artistId}
                onChange={(e) => setArtistId(e.target.value)}
                className="w-full px-3 py-2 bg-zinc-900 border border-zinc-800 rounded text-sm text-zinc-100"
              >
                {artists.map((a) => (
                  <option key={a.artist_id} value={a.artist_id}>
                    {a.stage_name}
                  </option>
                ))}
              </select>
            </Field>
            <Field label={`Song structure ${structureItems.length > 1 ? `(${structureItems.length} available for this genre)` : ''}`}>
              {structuresQ.isLoading ? (
                <div className="flex items-center gap-2 text-xs text-zinc-500 px-3 py-2 bg-zinc-900 border border-zinc-800 rounded">
                  <Loader2 size={12} className="animate-spin" /> Loading structures…
                </div>
              ) : structureItems.length === 0 ? (
                <div className="text-xs text-amber-300 px-3 py-2 bg-amber-500/10 border border-amber-500/30 rounded">
                  No structure on this genre — orchestrator will use defaults.
                </div>
              ) : (
                <select
                  value={structureIdx}
                  onChange={(e) => setStructureIdx(parseInt(e.target.value, 10))}
                  className="w-full px-3 py-2 bg-zinc-900 border border-zinc-800 rounded text-sm text-zinc-100"
                  disabled={structureItems.length === 1}
                >
                  {structureItems.map((s, i) => (
                    <option key={s.primary_genre} value={i}>
                      {s.primary_genre} · {(s.structure || []).length} sections
                      {i === 0 ? ' (most specific)' : ''}
                    </option>
                  ))}
                </select>
              )}
            </Field>
            <Field label="Content rating">
              <div className="flex gap-2">
                {[
                  { v: 'clean',    label: 'Clean' },
                  { v: 'explicit', label: 'Explicit' },
                ].map((opt) => (
                  <button
                    key={opt.v}
                    onClick={() => setContentRating(opt.v)}
                    className={`flex-1 px-3 py-2 text-xs rounded border transition-colors ${
                      contentRating === opt.v
                        ? 'bg-violet-600/20 border-violet-500/50 text-violet-100'
                        : 'border-zinc-800 text-zinc-400 hover:text-zinc-200 hover:border-zinc-700'
                    }`}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
            </Field>
            <Field label="Theme">
              <select
                value={themeChoice}
                onChange={(e) => setThemeChoice(e.target.value)}
                className="w-full px-3 py-2 bg-zinc-900 border border-zinc-800 rounded text-sm text-zinc-100"
              >
                {THEME_OPTIONS.map((o) => (
                  <option key={o.value} value={o.value}>{o.label}</option>
                ))}
              </select>
              {themeChoice === 'free_text' && (
                <textarea
                  value={themeFreeText}
                  onChange={(e) => setThemeFreeText(e.target.value)}
                  rows={2}
                  placeholder="e.g. Lyrics about driving back from a wedding at 4am"
                  className="mt-2 w-full px-3 py-2 bg-zinc-900 border border-zinc-800 rounded text-sm text-zinc-100"
                />
              )}
            </Field>
          </section>

          {/* Generate prompt button */}
          <div className="flex items-center justify-between gap-3 pt-2 border-t border-zinc-800">
            <div className="text-[11px] text-zinc-500 leading-relaxed max-w-xl">
              <strong className="text-zinc-300">Step 1 →</strong> compose the smart prompt and draft lyrics from the
              picks above. Both populate below as editable text. Step 2 generates the song.
            </div>
            <button
              onClick={handlePreview}
              disabled={preview.isPending || !canPreview}
              className={`flex items-center gap-1.5 px-4 py-2 text-xs font-medium rounded transition-colors flex-shrink-0 ${
                canPreview
                  ? 'bg-violet-600 hover:bg-violet-500 text-white'
                  : 'bg-zinc-800 text-zinc-600 cursor-not-allowed'
              }`}
            >
              {preview.isPending ? <Loader2 size={12} className="animate-spin" /> : <Wand2 size={12} />}
              {preview.isPending ? 'Composing…' : 'Generate smart prompt'}
            </button>
          </div>

          {previewError && (
            <div className="bg-amber-500/10 border border-amber-500/30 rounded p-2 text-xs text-amber-200 flex items-center gap-2">
              <AlertCircle size={12} /> {previewError}
            </div>
          )}

          {/* Two textareas */}
          <section className="grid grid-cols-1 lg:grid-cols-2 gap-3">
            <div>
              <label className="block text-[10px] uppercase tracking-wider text-violet-400 font-semibold mb-1">
                Smart prompt {prompt && <span className="text-zinc-600 normal-case">· {prompt.length} chars</span>}
              </label>
              <textarea
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                rows={16}
                placeholder="(Click Generate smart prompt above to draft this — or paste your own.)"
                className="w-full px-3 py-2 bg-zinc-950 border border-zinc-800 rounded text-xs text-zinc-100 font-mono leading-relaxed resize-y"
              />
            </div>
            <div>
              <label className="block text-[10px] uppercase tracking-wider text-violet-400 font-semibold mb-1">
                Lyrics {lyrics && <span className="text-zinc-600 normal-case">· {lyrics.length} chars</span>}
              </label>
              <textarea
                value={lyrics}
                onChange={(e) => setLyrics(e.target.value)}
                rows={16}
                placeholder="(Lyrics will appear here after Step 1.)"
                className="w-full px-3 py-2 bg-zinc-950 border border-zinc-800 rounded text-xs text-zinc-100 font-mono leading-relaxed resize-y"
              />
            </div>
          </section>

          {/* Provider + duration */}
          <section className="grid grid-cols-2 md:grid-cols-3 gap-3 pt-2 border-t border-zinc-800">
            <Field label="Provider">
              <select
                value={provider}
                onChange={(e) => setProvider(e.target.value)}
                className="w-full px-3 py-2 bg-zinc-900 border border-zinc-800 rounded text-sm text-zinc-100"
              >
                <option value="suno_kie">Suno (Kie.ai)</option>
                <option value="musicgen">MusicGen</option>
                <option value="udio">Udio</option>
              </select>
            </Field>
            <Field label="Duration (seconds)">
              <input
                type="number"
                value={duration}
                onChange={(e) => setDuration(parseInt(e.target.value, 10) || 180)}
                min="20"
                max="300"
                className="w-full px-3 py-2 bg-zinc-900 border border-zinc-800 rounded text-sm text-zinc-100 tabular-nums"
              />
            </Field>
          </section>

          {generateError && (
            <div className="bg-rose-500/10 border border-rose-500/30 rounded p-2 text-xs text-rose-300 flex items-center gap-2">
              <AlertCircle size={14} /> {generateError}
            </div>
          )}
          {genResult && (
            <div className="bg-emerald-500/10 border border-emerald-500/30 rounded p-3 text-xs text-emerald-300 space-y-1">
              <div className="flex items-center gap-2"><CheckCircle2 size={14} /> Song generation kicked off — id {genResult.song_id?.slice(0, 8)}</div>
              <div className="text-[10px] text-emerald-400/70">Track Songs tab in ~60s.</div>
            </div>
          )}
        </div>

        <div className="flex items-center justify-end gap-2 p-4 border-t border-zinc-800 sticky bottom-0 bg-zinc-950">
          <button onClick={onClose} className="px-4 py-2 text-zinc-400 text-xs hover:text-zinc-200">Cancel</button>
          <button
            onClick={handleGenerate}
            disabled={generate.isPending || !canGenerate}
            className={`flex items-center gap-2 px-5 py-2 text-sm font-medium rounded ${
              canGenerate
                ? 'bg-emerald-600 hover:bg-emerald-500 text-white'
                : 'bg-zinc-800 text-zinc-600 cursor-not-allowed'
            }`}
          >
            {generate.isPending ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}
            {generate.isPending ? 'Submitting…' : 'Generate song'}
          </button>
        </div>
      </div>
    </div>
  )
}

function Field({ label, children }) {
  return (
    <label className="block">
      <div className="text-[10px] uppercase tracking-wider text-zinc-500 mb-1">{label}</div>
      {children}
    </label>
  )
}

export default function SongLab() {
  const [drafts, setDrafts] = useState([newDraft()])
  const [openWindow, setOpenWindow] = useState(null)  // a copied draft snapshot

  const bpQ = useBlueprints({})
  const artistsQ = useAIArtists('active')
  const blueprints = bpQ.data?.data?.blueprints || []
  const artists = artistsQ.data?.data?.artists || artistsQ.data?.artists || []

  const addRow = () => setDrafts((prev) => [...prev, newDraft()])
  const removeRow = (id) => setDrafts((prev) => prev.filter((d) => d.draftId !== id))
  const changeRow = (id, patch) => setDrafts((prev) => prev.map((d) => d.draftId === id ? { ...d, ...patch } : d))
  const createSong = (id) => {
    const d = drafts.find((x) => x.draftId === id)
    if (d) setOpenWindow({ ...d })
  }

  return (
    <div className="p-4 md:p-6 max-w-6xl mx-auto">
      <div className="flex items-center justify-between gap-3 mb-5 flex-wrap">
        <div>
          <div className="flex items-center gap-3 mb-1">
            <Music size={24} className="text-violet-400" />
            <h1 className="text-2xl font-bold text-zinc-100">Song Lab</h1>
          </div>
          <p className="text-sm text-zinc-500 max-w-3xl">
            Pick a genre blueprint + an artist; the artist contributes voice, persona, and lyrical DNA.
            The song window then composes the smart prompt + drafts lyrics, both editable, before
            firing the music provider.
          </p>
        </div>
        <button
          onClick={addRow}
          className="flex items-center gap-1.5 px-4 py-2 bg-violet-600 hover:bg-violet-500 text-white text-sm font-medium rounded-lg"
        >
          <Plus size={14} /> Add song
        </button>
      </div>

      {(bpQ.isLoading || artistsQ.isLoading) && (
        <div className="flex items-center gap-2 text-zinc-500 text-sm py-6">
          <Loader2 size={16} className="animate-spin" /> Loading blueprints + artists…
        </div>
      )}

      {!bpQ.isLoading && blueprints.length === 0 && (
        <div className="bg-amber-500/10 border border-amber-500/30 rounded p-3 text-sm text-amber-200 mb-3">
          No blueprints yet — create one in the Blueprints tab first.
        </div>
      )}
      {!artistsQ.isLoading && artists.length === 0 && (
        <div className="bg-amber-500/10 border border-amber-500/30 rounded p-3 text-sm text-amber-200 mb-3">
          No artists yet — create one in the Artists tab first.
        </div>
      )}

      {drafts.length > 0 && (
        <div className="border border-zinc-800 rounded-lg overflow-hidden bg-zinc-950">
          {drafts.map((d) => (
            <DraftRow
              key={d.draftId}
              draft={d}
              blueprints={blueprints}
              artists={artists}
              onChange={changeRow}
              onRemove={removeRow}
              onCreate={createSong}
            />
          ))}
        </div>
      )}

      {drafts.length === 0 && (
        <div className="border border-dashed border-zinc-800 rounded-xl p-10 text-center text-zinc-500">
          <Music size={32} className="mx-auto mb-3 text-zinc-600" />
          <div className="text-sm">No drafts. Click <strong className="text-zinc-300">Add song</strong> to start.</div>
        </div>
      )}

      {openWindow && (
        <SongWindow
          initialDraft={openWindow}
          blueprints={blueprints}
          artists={artists}
          onClose={() => setOpenWindow(null)}
          onGenerated={() => setDrafts((prev) => prev.filter((d) => d.draftId !== openWindow.draftId))}
        />
      )}
    </div>
  )
}
