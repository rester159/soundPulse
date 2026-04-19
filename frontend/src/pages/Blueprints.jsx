/**
 * Blueprints tab — generate, create, edit, and pick song blueprints.
 *
 * Two creation flows:
 *   1. Generate from genre — runs the smart_prompt LLM on the chosen
 *      genre/subgenre and persists the result. One-click to a saved
 *      blueprint.
 *   2. Manual from scratch — operator fills every dimension by hand.
 *      Useful when an opportunity isn't surfaced by the breakout
 *      engine and the operator has a directional bet.
 *
 * Existing blueprints are listed below with Edit / Assign artist /
 * Generate song actions. Saved blueprints automatically appear in the
 * SongLab generation panel's blueprint dropdown.
 */
import { useState } from 'react'
import {
  Sparkles, Plus, Edit3, Loader2, X, AlertCircle, CheckCircle2,
  Users, Music, ChevronDown, Trash2, RefreshCw, Wand2, HelpCircle,
} from 'lucide-react'
import { useQueryClient } from '@tanstack/react-query'
import {
  useBlueprints,
  useBlueprintDetail,
  useGenerateBlueprintFromGenre,
  useCreateBlueprintManual,
  useUpdateBlueprint,
  useAssignBlueprint,
  useGenerateSongForBlueprint,
  useGenreOpportunities,
  useSynthesizePromptFromFields,
} from '../hooks/useSoundPulse'
import GenreMultiPicker from '../components/GenreMultiPicker'

// Sonic-profile field tooltips. Numbers come from Spotify's audio-features
// scale (0..1) where applicable. The semantic anchors at 0 and 1 help an
// operator pick a value without having to look up reference docs.
const SONIC_TOOLTIPS = {
  tempo: 'Tempo in BPM (beats per minute). Examples: 70 (lo-fi), 95 (reggaeton), 120 (pop), 140 (drill), 175 (DnB).',
  key: 'Pitch class 0-11. 0=C, 1=C♯/D♭, 2=D, 3=D♯/E♭, 4=E, 5=F, 6=F♯/G♭, 7=G, 8=G♯/A♭, 9=A, 10=A♯/B♭, 11=B.',
  mode: 'Modality. 0 = minor (darker, melancholy), 1 = major (brighter, resolved).',
  energy: 'Perceptual intensity, 0–1. 0 = whisper-quiet ambient piano. 1 = blistering metal or hard EDM. Pop typically 0.6–0.85.',
  danceability: 'How suitable for dancing, 0–1. 0 = free jazz, ballad, classical solo. 1 = club-ready house or reggaeton. Pop typically 0.6–0.8.',
  valence: 'Musical positivity, 0–1. 0 = sad / angry / depressing. 1 = euphoric / cheerful / triumphant. Heartbreak ballads ~0.2; party anthems ~0.85.',
  acousticness: 'Confidence the track is acoustic, 0–1. 0 = fully electronic / synthesized. 1 = solo guitar + voice or unplugged session. Pop typically 0.05–0.3.',
  loudness: 'Average track loudness in LUFS (typical range -60 to 0). Spotify normalizes to ~-14 LUFS. -8 = aggressively loud master; -20 = quiet, dynamic.',
}

function FieldTooltip({ text }) {
  return (
    <span className="ml-1 inline-flex items-center" title={text}>
      <HelpCircle size={11} className="text-zinc-500 hover:text-zinc-300 cursor-help" />
    </span>
  )
}

// CSV helpers
const csvSplit = (s) => (s || '').split(',').map((x) => x.trim()).filter(Boolean)
const arr = (v) => (Array.isArray(v) ? v.join(', ') : (v || ''))

const STATUS_LABELS = {
  pending_assignment: { color: 'amber', label: 'pending assignment' },
  assigned: { color: 'cyan', label: 'assigned to artist' },
  assigned_pending_creation: { color: 'violet', label: 'awaiting song' },
  assigned_to_release: { color: 'emerald', label: 'song generated' },
}

function StatusBadge({ status }) {
  const meta = STATUS_LABELS[status] || { color: 'zinc', label: status || 'unknown' }
  const colorClass = {
    amber: 'text-amber-300 bg-amber-500/10 border-amber-500/30',
    cyan: 'text-cyan-300 bg-cyan-500/10 border-cyan-500/30',
    violet: 'text-violet-300 bg-violet-500/10 border-violet-500/30',
    emerald: 'text-emerald-300 bg-emerald-500/10 border-emerald-500/30',
    zinc: 'text-zinc-300 bg-zinc-500/10 border-zinc-500/30',
  }[meta.color]
  return (
    <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded border text-[9px] uppercase tracking-wider ${colorClass}`}>
      {meta.label}
    </span>
  )
}

function BlueprintCard({ blueprint, onEdit, onAssign, onGenerateSong, onView }) {
  const [busy, setBusy] = useState(null)

  const themes = blueprint.target_themes || []
  const audience = blueprint.target_audience_tags || []

  const handleAssign = async () => {
    setBusy('assign')
    try { await onAssign(blueprint) } finally { setBusy(null) }
  }
  const handleGenSong = async () => {
    setBusy('gen')
    try { await onGenerateSong(blueprint) } finally { setBusy(null) }
  }

  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900 p-4 space-y-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <code className="text-sm font-semibold text-violet-300">{blueprint.primary_genre || blueprint.genre_id}</code>
            <StatusBadge status={blueprint.status} />
            {blueprint.predicted_success_score != null && (
              <span className="text-[10px] text-zinc-500 tabular-nums">
                score {blueprint.predicted_success_score.toFixed(2)}
              </span>
            )}
          </div>
          <div className="text-[10px] text-zinc-600 mt-0.5">
            id {blueprint.id.slice(0, 8)} · created {new Date(blueprint.created_at).toLocaleDateString()}
            {blueprint.assigned_artist_id && ` · artist ${blueprint.assigned_artist_id.slice(0, 8)}`}
          </div>
        </div>
        <div className="flex items-center gap-1 flex-shrink-0">
          <button
            onClick={() => onEdit(blueprint)}
            className="flex items-center gap-1 px-2 py-1 text-zinc-400 hover:text-violet-300 hover:bg-violet-500/10 rounded text-xs"
            title="Edit blueprint"
          >
            <Edit3 size={11} /> Edit
          </button>
        </div>
      </div>

      {themes.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {themes.slice(0, 6).map((t) => (
            <span key={t} className="text-[10px] text-cyan-200 bg-cyan-500/10 border border-cyan-500/30 rounded px-1.5 py-0.5">
              {t}
            </span>
          ))}
          {themes.length > 6 && <span className="text-[10px] text-zinc-500">+{themes.length - 6}</span>}
        </div>
      )}

      {audience.length > 0 && (
        <div className="text-[10px] text-zinc-500">
          audience: <span className="text-zinc-400">{audience.join(', ')}</span>
        </div>
      )}

      {blueprint.smart_prompt_text && (
        <div className="text-xs text-zinc-400 line-clamp-3 leading-relaxed bg-zinc-950/50 border border-zinc-800 rounded p-2">
          {blueprint.smart_prompt_text}
        </div>
      )}

      <div className="flex items-center gap-2 pt-1 border-t border-zinc-800">
        <button
          onClick={() => onView(blueprint)}
          className="text-xs text-zinc-400 hover:text-zinc-200 underline"
        >
          View full
        </button>
        {blueprint.status === 'pending_assignment' && (
          <button
            onClick={handleAssign}
            disabled={busy === 'assign'}
            className="ml-auto flex items-center gap-1 px-2 py-1 bg-cyan-600/20 hover:bg-cyan-600/40 border border-cyan-500/40 text-cyan-200 text-xs rounded disabled:opacity-50"
          >
            {busy === 'assign' ? <Loader2 size={11} className="animate-spin" /> : <Users size={11} />}
            Assign artist
          </button>
        )}
        {blueprint.assigned_artist_id && blueprint.status !== 'assigned_to_release' && (
          <button
            onClick={handleGenSong}
            disabled={busy === 'gen'}
            className="ml-auto flex items-center gap-1 px-2 py-1 bg-violet-600/20 hover:bg-violet-600/40 border border-violet-500/40 text-violet-200 text-xs rounded disabled:opacity-50"
          >
            {busy === 'gen' ? <Loader2 size={11} className="animate-spin" /> : <Music size={11} />}
            Generate song
          </button>
        )}
      </div>
    </div>
  )
}

// ── Modal: generate from genre ───────────────────────────────────────────

function GenerateFromGenreModal({ onClose, onCreated }) {
  const generate = useGenerateBlueprintFromGenre()
  const opps = useGenreOpportunities()
  const qc = useQueryClient()
  const [genre, setGenre] = useState('pop')
  const [model, setModel] = useState('suno')
  const [edgeProfile, setEdgeProfile] = useState('')
  const [error, setError] = useState(null)
  const [result, setResult] = useState(null)

  // Genres ranked by opportunity score from /blueprint/genres. Smart-prompt
  // generation requires breakout data for the genre — if none exists in the
  // last 30 days, the LLM call short-circuits with an empty result. The
  // suggestions list shows operators which genres are guaranteed to work
  // (so they don't get the cryptic "no breakouts" failure).
  const genreSuggestions = (opps.data?.data?.data || []).slice(0, 30)

  const handleSubmit = async () => {
    setError(null)
    setResult(null)
    if (!genre.trim()) {
      setError('Genre is required')
      return
    }
    try {
      const body = { genre: genre.trim(), model }
      if (edgeProfile) body.edge_profile = edgeProfile
      const res = await generate.mutateAsync({ body })
      setResult(res?.data)
      qc.invalidateQueries({ queryKey: ['admin', 'blueprints'] })
      setTimeout(() => { onCreated?.(); onClose?.() }, 1800)
    } catch (e) {
      setError(e?.response?.data?.detail || e?.message || 'generation failed')
    }
  }

  return (
    <div className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-zinc-950 border border-zinc-800 rounded-xl max-w-lg w-full" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between p-4 border-b border-zinc-800">
          <div className="flex items-center gap-2 text-sm font-semibold text-zinc-200">
            <Sparkles size={14} className="text-violet-400" />
            Generate blueprint from genre
          </div>
          <button onClick={onClose} className="text-zinc-500 hover:text-zinc-300"><X size={16} /></button>
        </div>

        <div className="p-5 space-y-4">
          <p className="text-xs text-zinc-500 leading-relaxed">
            Runs the smart-prompt LLM (Layer 5 of the Breakout Engine) on the chosen
            genre. Pulls in this week's pop-culture references, edge rules, hook
            isolation, earworm rules. Saves the result so it appears in the SongLab
            blueprint dropdown.
          </p>

          <div>
            <label className="text-xs text-zinc-400 block mb-1">Genre / subgenre</label>
            <input
              type="text"
              value={genre}
              onChange={(e) => setGenre(e.target.value)}
              placeholder="pop.k-pop, hip-hop.trap, latin.reggaeton…"
              className="w-full px-3 py-2 bg-zinc-900 border border-zinc-800 rounded text-sm text-zinc-100 font-mono"
            />
            {genreSuggestions.length > 0 && (
              <div className="mt-2">
                <div className="text-[10px] text-zinc-500 mb-1">
                  Quick pick (genres with recent breakout data — guaranteed to generate):
                </div>
                <div className="flex flex-wrap gap-1">
                  {genreSuggestions.map((g) => {
                    const id = g.genre_id || g.id || g.genre
                    if (!id) return null
                    const isActive = id === genre
                    return (
                      <button
                        key={id}
                        type="button"
                        onClick={() => setGenre(id)}
                        className={`px-2 py-0.5 text-[10px] rounded font-mono border transition-colors ${
                          isActive
                            ? 'bg-violet-600/30 text-violet-200 border-violet-500/50'
                            : 'text-zinc-300 border-zinc-700 hover:border-violet-500/50 hover:text-violet-200'
                        }`}
                        title={g.breakout_count ? `${g.breakout_count} breakouts in 30d` : ''}
                      >
                        {id}
                      </button>
                    )
                  })}
                </div>
              </div>
            )}
            <div className="text-[10px] text-zinc-600 mt-2">
              Or type any canonical dotted-genre id from <code>shared/genre_taxonomy.py</code>.
              The smart-prompt LLM needs ≥1 breakout event in the last 30 days for the chosen
              genre — pick one above to be safe, or use <strong>Create manually</strong> for
              genres without breakout data.
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-zinc-400 block mb-1">Model</label>
              <select
                value={model}
                onChange={(e) => setModel(e.target.value)}
                className="w-full px-3 py-2 bg-zinc-900 border border-zinc-800 rounded text-sm text-zinc-100"
              >
                <option value="suno">Suno</option>
                <option value="udio">Udio</option>
                <option value="musicgen">MusicGen</option>
              </select>
            </div>
            <div>
              <label className="text-xs text-zinc-400 block mb-1">Edge profile (override)</label>
              <select
                value={edgeProfile}
                onChange={(e) => setEdgeProfile(e.target.value)}
                className="w-full px-3 py-2 bg-zinc-900 border border-zinc-800 rounded text-sm text-zinc-100"
              >
                <option value="">— use genre default —</option>
                <option value="clean_edge">clean_edge</option>
                <option value="flirty_edge">flirty_edge</option>
                <option value="savage_edge">savage_edge</option>
              </select>
            </div>
          </div>

          {error && (
            <div className="bg-rose-500/10 border border-rose-500/30 rounded p-2 text-xs text-rose-300 flex items-center gap-2">
              <AlertCircle size={14} /> {error}
            </div>
          )}

          {result && (
            <div className="bg-emerald-500/10 border border-emerald-500/30 rounded p-3 text-xs text-emerald-300 space-y-1">
              <div className="flex items-center gap-2"><CheckCircle2 size={14} /> Created blueprint for {result.genre_id}</div>
              <div className="text-[10px] text-emerald-400/70 font-mono">id: {result.id}</div>
              <div className="text-[10px]">edge: {result.edge_profile} · confidence: {result.confidence} · pop-culture refs offered: {result.pop_culture_refs_offered}</div>
            </div>
          )}
        </div>

        <div className="flex items-center justify-end gap-2 p-4 border-t border-zinc-800">
          <button onClick={onClose} className="px-4 py-2 text-zinc-400 text-xs hover:text-zinc-200">Cancel</button>
          <button
            onClick={handleSubmit}
            disabled={generate.isPending || !genre.trim()}
            className="px-5 py-2 bg-violet-600 hover:bg-violet-500 disabled:bg-zinc-800 disabled:text-zinc-600 text-white text-sm font-medium rounded flex items-center gap-2"
          >
            {generate.isPending ? <Loader2 size={14} className="animate-spin" /> : <Sparkles size={14} />}
            {generate.isPending ? 'Generating…' : 'Generate & save'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ── Modal: manual create / edit ──────────────────────────────────────────

function ManualBlueprintModal({ onClose, onSaved, existingBlueprint = null }) {
  const create = useCreateBlueprintManual()
  const update = useUpdateBlueprint()
  const synthesize = useSynthesizePromptFromFields()
  const qc = useQueryClient()
  const [error, setError] = useState(null)
  const [result, setResult] = useState(null)
  const [synthError, setSynthError] = useState(null)

  const isEdit = Boolean(existingBlueprint)
  const e = existingBlueprint || {}

  // Identity — primary + adjacent are now both multi-select. The first
  // primary entry maps to the schema's single primary_genre column; the
  // rest spill into adjacent_genres on save (deduplicated).
  const initialPrimary = (() => {
    const seed = []
    if (e.primary_genre) seed.push(e.primary_genre)
    else if (e.genre_id) seed.push(e.genre_id)
    return seed
  })()
  const [primaryGenres, setPrimaryGenres] = useState(initialPrimary)
  const [adjacentGenres, setAdjacentGenres] = useState(
    Array.isArray(e.adjacent_genres) ? e.adjacent_genres : []
  )

  // Sonic profile
  const [tempo, setTempo] = useState(e.target_tempo ?? '')
  const [keyVal, setKeyVal] = useState(e.target_key ?? '')
  const [mode, setMode] = useState(e.target_mode ?? '')
  const [energy, setEnergy] = useState(e.target_energy ?? '')
  const [danceability, setDanceability] = useState(e.target_danceability ?? '')
  const [valence, setValence] = useState(e.target_valence ?? '')
  const [acousticness, setAcousticness] = useState(e.target_acousticness ?? '')

  // Lyrical
  const [targetThemes, setTargetThemes] = useState(arr(e.target_themes))
  const [avoidThemes, setAvoidThemes] = useState(arr(e.avoid_themes))
  const [vocabularyTone, setVocabularyTone] = useState(e.vocabulary_tone || '')

  // Audience + voice — voice is now a single free-text field. We persist
  // it as voice_requirements.description so the JSONB column shape stays
  // intact for any downstream consumer that already reads keys from it.
  const [audienceTags, setAudienceTags] = useState(arr(e.target_audience_tags))
  const initialVoiceText = (() => {
    const vr = e.voice_requirements
    if (!vr) return ''
    if (typeof vr === 'string') return vr
    if (typeof vr === 'object') {
      if (vr.description) return vr.description
      // Older payloads may have a richer JSON shape — flatten readable
      // keys so the user sees what's there and can edit as prose.
      return Object.entries(vr).map(([k, v]) =>
        typeof v === 'string' ? `${k}: ${v}` : `${k}: ${JSON.stringify(v)}`
      ).join('\n')
    }
    return String(vr)
  })()
  const [voiceText, setVoiceText] = useState(initialVoiceText)

  // Production
  const [productionNotes, setProductionNotes] = useState(e.production_notes || '')
  const [referenceTracks, setReferenceTracks] = useState(arr(e.reference_track_descriptors))

  // Smart prompt body
  const [smartPromptText, setSmartPromptText] = useState(e.smart_prompt_text || '')

  const mut = isEdit ? update : create

  // Resolve "primary genre" from the multi-select. First entry is the
  // canonical primary; everything else (plus the adjacent picker's
  // contents) becomes adjacent_genres on save.
  const buildBodyShape = () => {
    const primary = primaryGenres[0] || ''
    const restFromPrimary = primaryGenres.slice(1)
    const adjacentMerged = Array.from(new Set([...restFromPrimary, ...adjacentGenres]))
      .filter((g) => g && g !== primary)
    const voiceReq = voiceText.trim() ? { description: voiceText.trim() } : null
    return {
      genre_id: primary,
      primary_genre: primary || undefined,
      adjacent_genres: adjacentMerged,
      target_themes: csvSplit(targetThemes),
      avoid_themes: csvSplit(avoidThemes),
      vocabulary_tone: vocabularyTone.trim() || undefined,
      target_audience_tags: csvSplit(audienceTags),
      voice_requirements: voiceReq,
      target_tempo: tempo === '' ? undefined : parseFloat(tempo),
      target_key: keyVal === '' ? undefined : parseInt(keyVal, 10),
      target_mode: mode === '' ? undefined : parseInt(mode, 10),
      target_energy: energy === '' ? undefined : parseFloat(energy),
      target_danceability: danceability === '' ? undefined : parseFloat(danceability),
      target_valence: valence === '' ? undefined : parseFloat(valence),
      target_acousticness: acousticness === '' ? undefined : parseFloat(acousticness),
      production_notes: productionNotes.trim() || undefined,
      reference_track_descriptors: csvSplit(referenceTracks),
    }
  }

  const handleSynthesize = async () => {
    setSynthError(null)
    if (primaryGenres.length === 0) {
      setSynthError('Pick at least one primary genre first')
      return
    }
    try {
      const body = buildBodyShape()
      const res = await synthesize.mutateAsync({ body })
      const promptText = res?.data?.prompt
      if (promptText) {
        setSmartPromptText(promptText)
      } else {
        setSynthError('LLM returned an empty prompt')
      }
    } catch (e2) {
      setSynthError(e2?.response?.data?.detail || e2?.message || 'synthesis failed')
    }
  }

  const handleSubmit = async () => {
    setError(null)
    setResult(null)
    if (primaryGenres.length === 0 || !smartPromptText.trim()) {
      setError('At least one primary genre AND smart prompt text are required')
      return
    }
    const body = { ...buildBodyShape(), smart_prompt_text: smartPromptText.trim() }
    try {
      const res = isEdit
        ? await update.mutateAsync({ blueprintId: existingBlueprint.id, body })
        : await create.mutateAsync({ body })
      setResult(res?.data)
      qc.invalidateQueries({ queryKey: ['admin', 'blueprints'] })
      setTimeout(() => { onSaved?.(); onClose?.() }, 1200)
    } catch (e2) {
      setError(e2?.response?.data?.detail || e2?.message || 'save failed')
    }
  }

  const num = (val, setter, placeholder, step = '0.01') => (
    <input
      type="number"
      step={step}
      value={val}
      onChange={(ev) => setter(ev.target.value)}
      placeholder={placeholder}
      className="w-full px-3 py-2 bg-zinc-950 border border-zinc-800 rounded text-sm text-zinc-100 placeholder-zinc-600"
    />
  )
  const inp = (val, setter, placeholder) => (
    <input
      type="text"
      value={val}
      onChange={(ev) => setter(ev.target.value)}
      placeholder={placeholder}
      className="w-full px-3 py-2 bg-zinc-950 border border-zinc-800 rounded text-sm text-zinc-100 placeholder-zinc-600"
    />
  )
  const ta = (val, setter, placeholder, rows = 2) => (
    <textarea
      value={val}
      onChange={(ev) => setter(ev.target.value)}
      placeholder={placeholder}
      rows={rows}
      className="w-full px-3 py-2 bg-zinc-950 border border-zinc-800 rounded text-sm text-zinc-100 placeholder-zinc-600 resize-y"
    />
  )
  const lbl = (label, child, hint) => (
    <label className="block text-xs text-zinc-400">
      {label}
      <div className="mt-1">{child}</div>
      {hint && <div className="text-[10px] text-zinc-600 mt-0.5">{hint}</div>}
    </label>
  )

  return (
    <div className="fixed inset-0 z-50 bg-black/80 flex items-start justify-center p-4 overflow-y-auto" onClick={onClose}>
      <div className="bg-zinc-950 border border-zinc-800 rounded-xl max-w-3xl w-full my-4" onClick={(ev) => ev.stopPropagation()}>
        <div className="flex items-center justify-between p-4 border-b border-zinc-800 sticky top-0 bg-zinc-950 z-10">
          <div className="flex items-center gap-2 text-sm font-semibold text-zinc-200">
            <Edit3 size={14} className="text-violet-400" />
            {isEdit ? `Edit blueprint — ${existingBlueprint.primary_genre || existingBlueprint.genre_id}` : 'Create blueprint manually'}
          </div>
          <button onClick={onClose} className="text-zinc-500 hover:text-zinc-300"><X size={16} /></button>
        </div>

        <div className="p-5 space-y-6">
          <section>
            <div className="text-[11px] uppercase tracking-wider text-violet-400 font-semibold mb-3">Identity</div>
            <div className="space-y-3">
              <label className="block text-xs text-zinc-400">
                Primary genre(s) *
                <FieldTooltip text="Pick one or more from the 959-genre taxonomy. The first selected becomes the canonical primary genre on the blueprint (used by genre_structures + genre_traits resolution); the rest are auto-merged into Adjacent genres. This does NOT add a new genre to the system taxonomy — it just references an existing one." />
                <div className="mt-1">
                  <GenreMultiPicker
                    value={primaryGenres}
                    onChange={setPrimaryGenres}
                    placeholder="Search the taxonomy — type 'k-pop', 'house', 'reggae'…"
                  />
                </div>
              </label>
              <label className="block text-xs text-zinc-400">
                Adjacent genres
                <FieldTooltip text="Genres beyond the primary that this song touches. Used by the assignment engine to score voice/audience overlap and by the smart-prompt LLM to flavor the production. Same picker — pick as many as fit." />
                <div className="mt-1">
                  <GenreMultiPicker
                    value={adjacentGenres}
                    onChange={setAdjacentGenres}
                    placeholder="Add adjacent genres…"
                  />
                </div>
              </label>
            </div>
          </section>

          <section>
            <div className="text-[11px] uppercase tracking-wider text-violet-400 font-semibold mb-3">Sonic profile</div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <label className="block text-xs text-zinc-400">
                Tempo (BPM)<FieldTooltip text={SONIC_TOOLTIPS.tempo} />
                <div className="mt-1">{num(tempo, setTempo, '120', '1')}</div>
              </label>
              <label className="block text-xs text-zinc-400">
                Key (0–11)<FieldTooltip text={SONIC_TOOLTIPS.key} />
                <div className="mt-1">{num(keyVal, setKeyVal, '0', '1')}</div>
              </label>
              <label className="block text-xs text-zinc-400">
                Mode<FieldTooltip text={SONIC_TOOLTIPS.mode} />
                <div className="mt-1">{num(mode, setMode, '1', '1')}</div>
              </label>
              <label className="block text-xs text-zinc-400">
                Energy (0–1)<FieldTooltip text={SONIC_TOOLTIPS.energy} />
                <div className="mt-1">{num(energy, setEnergy, '0.75')}</div>
              </label>
              <label className="block text-xs text-zinc-400">
                Danceability (0–1)<FieldTooltip text={SONIC_TOOLTIPS.danceability} />
                <div className="mt-1">{num(danceability, setDanceability, '0.7')}</div>
              </label>
              <label className="block text-xs text-zinc-400">
                Valence (0–1)<FieldTooltip text={SONIC_TOOLTIPS.valence} />
                <div className="mt-1">{num(valence, setValence, '0.6')}</div>
              </label>
              <label className="block text-xs text-zinc-400">
                Acousticness (0–1)<FieldTooltip text={SONIC_TOOLTIPS.acousticness} />
                <div className="mt-1">{num(acousticness, setAcousticness, '0.2')}</div>
              </label>
            </div>
            <div className="text-[10px] text-zinc-600 mt-2">
              Hover the <HelpCircle size={9} className="inline" /> icons for what 0 vs 1 means on each axis. Leave blank to omit (the orchestrator + smart-prompt LLM will fall back to genre defaults).
            </div>
          </section>

          <section>
            <div className="text-[11px] uppercase tracking-wider text-violet-400 font-semibold mb-3">Lyrical & themes</div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {lbl('Target themes', ta(targetThemes, setTargetThemes, 'midnight drives, longing, neon (csv)'))}
              {lbl('Avoid themes', ta(avoidThemes, setAvoidThemes, 'generic self-empowerment (csv)'))}
              <div className="md:col-span-2">
                {lbl('Vocabulary tone', inp(vocabularyTone, setVocabularyTone, 'conversational / poetic / abstract / tabloid'))}
              </div>
            </div>
          </section>

          <section>
            <div className="text-[11px] uppercase tracking-wider text-violet-400 font-semibold mb-3">Audience & voice</div>
            <div className="space-y-3">
              {lbl('Target audience tags', ta(audienceTags, setAudienceTags, 'gen_z, female_lean, urban (csv)'))}
              {lbl('Voice requirements',
                ta(voiceText, setVoiceText, 'Free-text: e.g. "soft warm tenor, half-sung delivery with whispered doubles, light autotune, occasional ad-libs (mhm, yeah)"', 4),
                'Plain English description of the vocal direction. Used by the assignment engine to match a roster artist + by the smart-prompt LLM to compose the final prompt.')}
            </div>
          </section>

          <section>
            <div className="text-[11px] uppercase tracking-wider text-violet-400 font-semibold mb-3">Production</div>
            <div className="space-y-3">
              {lbl('Production notes', ta(productionNotes, setProductionNotes, 'sidechained pads, gritty 808s, vocal chops on prechorus', 3))}
              {lbl('Reference tracks', ta(referenceTracks, setReferenceTracks, 'reference descriptors, e.g. "Sabrina Carpenter Espresso intro feel" (csv)'))}
            </div>
          </section>

          <section>
            <div className="flex items-center justify-between mb-3">
              <div className="text-[11px] uppercase tracking-wider text-violet-400 font-semibold">Smart prompt *</div>
              <button
                type="button"
                onClick={handleSynthesize}
                disabled={synthesize.isPending || primaryGenres.length === 0}
                className="flex items-center gap-1.5 px-3 py-1 bg-violet-600/20 hover:bg-violet-600/40 border border-violet-500/40 disabled:opacity-50 text-violet-200 text-xs font-medium rounded transition-colors"
                title="Generate the smart prompt from all the fields above using the LLM"
              >
                {synthesize.isPending ? <Loader2 size={11} className="animate-spin" /> : <Wand2 size={11} />}
                {synthesize.isPending ? 'Composing…' : 'Generate from fields'}
              </button>
            </div>
            <div className="text-[11px] text-zinc-500 mb-2 leading-relaxed">
              The actual text the orchestrator sends to Suno (after prepending [STRUCTURE] from §70 + voice DNA from the assigned artist). Click <strong>Generate from fields</strong> to have an LLM compose this from everything above, or paste/write directly. Edit freely — the textarea is the source of truth for what gets saved.
            </div>
            {ta(smartPromptText, setSmartPromptText, 'STYLE: …\nLYRICS:\n[Verse 1] …\n[Chorus] …', 12)}
            {synthError && (
              <div className="mt-2 bg-rose-500/10 border border-rose-500/30 rounded p-2 text-xs text-rose-300 flex items-center gap-2">
                <AlertCircle size={12} /> {synthError}
              </div>
            )}
          </section>

          {error && (
            <div className="bg-rose-500/10 border border-rose-500/30 rounded p-2 text-xs text-rose-300 flex items-center gap-2">
              <AlertCircle size={14} /> {error}
            </div>
          )}

          {result && (
            <div className="bg-emerald-500/10 border border-emerald-500/30 rounded p-3 text-xs text-emerald-300 space-y-1">
              <div className="flex items-center gap-2"><CheckCircle2 size={14} /> {isEdit ? 'Saved' : 'Created'} blueprint {result.id?.slice(0, 8)}</div>
              {isEdit && Array.isArray(result.fields_updated) && (
                <div className="text-[10px] text-emerald-400/70">updated: {result.fields_updated.join(', ')}</div>
              )}
            </div>
          )}
        </div>

        <div className="flex items-center justify-end gap-2 p-4 border-t border-zinc-800 sticky bottom-0 bg-zinc-950">
          <button onClick={onClose} className="px-4 py-2 text-zinc-400 text-xs hover:text-zinc-200">Cancel</button>
          <button
            onClick={handleSubmit}
            disabled={mut.isPending || !genreId.trim() || !smartPromptText.trim()}
            className="px-5 py-2 bg-violet-600 hover:bg-violet-500 disabled:bg-zinc-800 disabled:text-zinc-600 text-white text-sm font-medium rounded flex items-center gap-2"
          >
            {mut.isPending ? <Loader2 size={14} className="animate-spin" /> : <Edit3 size={14} />}
            {mut.isPending ? (isEdit ? 'Saving…' : 'Creating…') : (isEdit ? 'Save changes' : 'Create blueprint')}
          </button>
        </div>
      </div>
    </div>
  )
}

// ── Modal: full-detail view (read-only) ──────────────────────────────────

function BlueprintViewModal({ blueprintId, onClose }) {
  const { data, isLoading } = useBlueprintDetail(blueprintId)
  const bp = data?.data

  return (
    <div className="fixed inset-0 z-50 bg-black/80 flex items-start justify-center p-4 overflow-y-auto" onClick={onClose}>
      <div className="bg-zinc-950 border border-zinc-800 rounded-xl max-w-3xl w-full my-4" onClick={(ev) => ev.stopPropagation()}>
        <div className="flex items-center justify-between p-4 border-b border-zinc-800 sticky top-0 bg-zinc-950 z-10">
          <div className="text-sm font-semibold text-zinc-200">
            Blueprint detail
            {bp && <span className="ml-2 font-mono text-violet-300">{bp.primary_genre || bp.genre_id}</span>}
          </div>
          <button onClick={onClose} className="text-zinc-500 hover:text-zinc-300"><X size={16} /></button>
        </div>
        <div className="p-5">
          {isLoading && (
            <div className="flex items-center gap-2 text-zinc-500 text-sm">
              <Loader2 size={14} className="animate-spin" /> Loading…
            </div>
          )}
          {bp && (
            <pre className="text-xs text-zinc-300 whitespace-pre-wrap break-words font-mono bg-zinc-900 border border-zinc-800 rounded p-3 max-h-[70vh] overflow-y-auto">
              {JSON.stringify(bp, null, 2)}
            </pre>
          )}
        </div>
      </div>
    </div>
  )
}

// ── Page ─────────────────────────────────────────────────────────────────

export default function Blueprints() {
  const [statusFilter, setStatusFilter] = useState('')
  const { data, isLoading, isError, error, refetch, isFetching } = useBlueprints({
    status: statusFilter || null,
  })
  const blueprints = data?.data?.blueprints || []
  const qc = useQueryClient()

  const [showGenerate, setShowGenerate] = useState(false)
  const [showManual, setShowManual] = useState(false)
  const [editing, setEditing] = useState(null)
  const [viewing, setViewing] = useState(null)

  const assign = useAssignBlueprint()
  const generateSong = useGenerateSongForBlueprint()
  const [actionStatus, setActionStatus] = useState(null)  // {kind, msg}

  const handleAssign = async (blueprint) => {
    setActionStatus(null)
    try {
      const res = await assign.mutateAsync({ blueprintId: blueprint.id })
      setActionStatus({
        kind: 'success',
        msg: `Assignment proposal queued — check Settings → Pending Decisions to approve. Decision id ${res?.data?.decision_id?.slice(0, 8) || ''}`,
      })
      qc.invalidateQueries({ queryKey: ['admin', 'blueprints'] })
      qc.invalidateQueries({ queryKey: ['admin', 'ceo-decisions'] })
    } catch (e) {
      setActionStatus({
        kind: 'error',
        msg: e?.response?.data?.detail || e?.message || 'assign failed',
      })
    }
  }

  const handleGenerateSong = async (blueprint) => {
    setActionStatus(null)
    try {
      const res = await generateSong.mutateAsync({ blueprintId: blueprint.id, body: {} })
      setActionStatus({
        kind: 'success',
        msg: `Song generation kicked off — song id ${res?.data?.song_id?.slice(0, 8) || ''}. Check Songs tab in ~60s.`,
      })
      qc.invalidateQueries({ queryKey: ['admin', 'blueprints'] })
      qc.invalidateQueries({ queryKey: ['admin', 'songs'] })
    } catch (e) {
      setActionStatus({
        kind: 'error',
        msg: e?.response?.data?.detail || e?.message || 'song generation failed',
      })
    }
  }

  return (
    <div className="p-4 md:p-6 max-w-5xl mx-auto">
      <div className="flex items-start justify-between mb-6 gap-3 flex-wrap">
        <div>
          <div className="flex items-center gap-3 mb-1">
            <Sparkles size={24} className="text-violet-400" />
            <h1 className="text-2xl font-bold text-zinc-100">Blueprints</h1>
          </div>
          <p className="text-sm text-zinc-500">
            Song recipes. Generate from a genre using the smart-prompt LLM, or build one manually from scratch. Saved blueprints appear in the SongLab dropdown when generating songs.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowGenerate(true)}
            className="flex items-center gap-1.5 px-3 py-2 bg-zinc-800 hover:bg-zinc-700 text-zinc-200 text-xs font-medium rounded-lg border border-zinc-700"
          >
            <Sparkles size={14} /> Generate from genre
          </button>
          <button
            onClick={() => setShowManual(true)}
            className="flex items-center gap-1.5 px-3 py-2 bg-violet-600 hover:bg-violet-500 text-white text-xs font-medium rounded-lg"
          >
            <Plus size={14} /> Create manually
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-3 mb-4">
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="px-3 py-1.5 bg-zinc-900 border border-zinc-800 rounded text-xs text-zinc-200"
        >
          <option value="">all statuses</option>
          <option value="pending_assignment">pending assignment</option>
          <option value="assigned">assigned</option>
          <option value="assigned_pending_creation">awaiting song</option>
          <option value="assigned_to_release">song generated</option>
        </select>
        <button
          onClick={() => refetch()}
          disabled={isFetching}
          className="flex items-center gap-1 px-2 py-1.5 text-xs text-zinc-400 hover:text-zinc-200 disabled:opacity-50"
        >
          <RefreshCw size={12} className={isFetching ? 'animate-spin' : ''} /> Refresh
        </button>
        <span className="text-xs text-zinc-600 ml-auto">
          {blueprints.length} blueprint{blueprints.length === 1 ? '' : 's'}
        </span>
      </div>

      {actionStatus && (
        <div className={`mb-4 p-3 rounded border text-xs ${
          actionStatus.kind === 'success'
            ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
            : 'bg-rose-500/10 border-rose-500/30 text-rose-300'
        }`}>
          {actionStatus.msg}
        </div>
      )}

      {isLoading && (
        <div className="flex items-center justify-center py-20 text-zinc-500">
          <Loader2 size={20} className="animate-spin mr-2" /> Loading blueprints…
        </div>
      )}

      {isError && (
        <div className="bg-rose-500/10 border border-rose-500/30 rounded p-3 text-xs text-rose-300">
          Failed to load: {error?.message}
        </div>
      )}

      {!isLoading && blueprints.length === 0 && (
        <div className="border border-dashed border-zinc-800 rounded-xl p-10 text-center text-zinc-500">
          <Sparkles size={32} className="mx-auto mb-3 text-zinc-600" />
          <div className="text-sm font-medium text-zinc-400">No blueprints yet</div>
          <div className="text-xs mt-1">Generate one from a genre, or create one from scratch.</div>
          <div className="flex items-center justify-center gap-2 mt-4">
            <button
              onClick={() => setShowGenerate(true)}
              className="flex items-center gap-1.5 px-3 py-2 bg-zinc-800 hover:bg-zinc-700 text-zinc-200 text-xs rounded"
            >
              <Sparkles size={12} /> Generate from genre
            </button>
            <button
              onClick={() => setShowManual(true)}
              className="flex items-center gap-1.5 px-3 py-2 bg-violet-600 hover:bg-violet-500 text-white text-xs rounded"
            >
              <Plus size={12} /> Create manually
            </button>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {blueprints.map((bp) => (
          <BlueprintCard
            key={bp.id}
            blueprint={bp}
            onEdit={(b) => setEditing(b)}
            onAssign={handleAssign}
            onGenerateSong={handleGenerateSong}
            onView={(b) => setViewing(b.id)}
          />
        ))}
      </div>

      {showGenerate && (
        <GenerateFromGenreModal
          onClose={() => setShowGenerate(false)}
          onCreated={() => qc.invalidateQueries({ queryKey: ['admin', 'blueprints'] })}
        />
      )}
      {showManual && (
        <ManualBlueprintModal
          onClose={() => setShowManual(false)}
          onSaved={() => qc.invalidateQueries({ queryKey: ['admin', 'blueprints'] })}
        />
      )}
      {editing && (
        <ManualBlueprintModal
          existingBlueprint={editing}
          onClose={() => setEditing(null)}
          onSaved={() => qc.invalidateQueries({ queryKey: ['admin', 'blueprints'] })}
        />
      )}
      {viewing && (
        <BlueprintViewModal blueprintId={viewing} onClose={() => setViewing(null)} />
      )}
    </div>
  )
}
