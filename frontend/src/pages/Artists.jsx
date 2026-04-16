import { useState } from 'react'
import {
  Users, Loader2, ChevronDown, ChevronUp, Music2, CheckCircle2,
  Mic, Palette, BookOpen, Hash, Plus, X, RefreshCw, Camera, Edit3, AlertCircle,
  Save, Info, Check,
} from 'lucide-react'
import { useQueryClient } from '@tanstack/react-query'
import {
  useAIArtists, useSongs, useCreateArtistFromDescription,
  useRegenerateArtistPortrait, useArtistReferenceSheet,
  useGenerateReferenceSheet, usePreviewPersona,
  useCreateArtistFromPersona, useCreateArtistManual, getBaseUrl,
  usePatchArtistStructure,
} from '../hooks/useSoundPulse'
import GenreStructureEditor, { structureChain } from '../components/GenreStructureEditor'

const VIEW_LABELS = {
  front: 'Front',
  side_l: 'Side L',
  side_r: 'Side R',
  back: 'Back',
  top_l: 'Top L',
  top_r: 'Top R',
  bottom_l: 'Low L',
  bottom_r: 'Low R',
}

function ReferenceSheetGrid({ artistId }) {
  const { data, isLoading } = useArtistReferenceSheet(artistId)
  const generate = useGenerateReferenceSheet()
  const qc = useQueryClient()
  const views = data?.data?.views || []

  const handleGenerate = async () => {
    if (!window.confirm('Generate the full 8-view reference sheet? Cost: $0.64 (8 × DALL-E 3 HD). This takes ~2-3 minutes.')) return
    await generate.mutateAsync({ artistId })
    qc.invalidateQueries({ queryKey: ['admin', 'artists', artistId, 'reference-sheet'] })
    qc.invalidateQueries({ queryKey: ['admin', 'ai-artists'] })
  }

  if (isLoading) {
    return <div className="text-[10px] text-zinc-500 flex items-center gap-1"><Loader2 size={10} className="animate-spin" /> Loading reference sheet...</div>
  }

  if (views.length === 0) {
    return (
      <div className="space-y-2">
        <div className="text-[10px] uppercase tracking-wider text-zinc-500 flex items-center gap-1">
          <Palette size={10} /> 8-View Reference Sheet — PRD §20
        </div>
        <div className="bg-zinc-950 border border-zinc-800 rounded p-3 text-center">
          <div className="text-[11px] text-zinc-500 mb-2">
            No reference sheet yet. 8 angles × $0.08 DALL-E 3 HD = $0.64
          </div>
          <button
            onClick={handleGenerate}
            disabled={generate.isPending}
            className="px-3 py-1.5 bg-violet-600 hover:bg-violet-500 disabled:opacity-40 text-white text-[11px] font-medium rounded"
          >
            {generate.isPending ? (
              <span className="flex items-center gap-1.5"><Loader2 size={10} className="animate-spin" /> Generating 8 views (~2-3 min)...</span>
            ) : (
              'Generate 8-view sheet ($0.64)'
            )}
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <div className="text-[10px] uppercase tracking-wider text-zinc-500 flex items-center gap-1">
          <Palette size={10} /> 8-View Reference Sheet ({views.length}/8)
        </div>
        <button
          onClick={handleGenerate}
          disabled={generate.isPending}
          className="text-[10px] px-2 py-0.5 bg-zinc-800 hover:bg-zinc-700 border border-zinc-700 text-zinc-400 rounded"
        >
          {generate.isPending ? 'Regenerating...' : 'Regen'}
        </button>
      </div>
      <div className="grid grid-cols-4 gap-2">
        {views.map(v => (
          <div key={v.asset_id} className="relative">
            <img
              src={resolveBackendUrl(v.storage_url)}
              alt={v.view_angle}
              className="w-full aspect-square rounded object-cover border border-zinc-800"
            />
            <div className="absolute bottom-1 left-1 bg-zinc-950/90 border border-zinc-700 text-[9px] text-zinc-300 px-1.5 py-0.5 rounded">
              {VIEW_LABELS[v.view_angle] || v.view_angle}
            </div>
            {v.is_canonical_sheet && (
              <div className="absolute top-1 right-1 bg-violet-600/80 text-[9px] text-white px-1.5 py-0.5 rounded font-semibold">
                ★
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

function resolveBackendUrl(url) {
  if (!url) return url
  if (/^https?:\/\//i.test(url)) return url
  if (url.startsWith('/api/v1/')) {
    const base = getBaseUrl().replace(/\/api\/v1\/?$/, '')
    return base + url
  }
  return url
}

function formatDnaValue(value) {
  if (value === null || value === undefined) return null
  if (Array.isArray(value)) return value.join(', ')
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

function humanizeKey(k) {
  return k.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
}

function DNABlock({ icon: Icon, title, data, color = 'violet' }) {
  if (!data || Object.keys(data).length === 0) return null
  const colorCls = {
    violet:  'border-violet-500/30 bg-violet-500/5 text-violet-200',
    cyan:    'border-cyan-500/30 bg-cyan-500/5 text-cyan-200',
    amber:   'border-amber-500/30 bg-amber-500/5 text-amber-200',
    emerald: 'border-emerald-500/30 bg-emerald-500/5 text-emerald-200',
    rose:    'border-rose-500/30 bg-rose-500/5 text-rose-200',
  }[color]
  // Skip UUID-ish fields — they're implementation details, not human-readable
  const skipKeys = new Set([
    'reference_sheet_asset_id', 'seed_song_id', 'suno_persona_id',
    'reference_song_ids', 'consistency_strategy',
  ])
  const entries = Object.entries(data)
    .filter(([k, v]) => !skipKeys.has(k) && v !== null && v !== undefined && v !== '')
    .map(([k, v]) => [humanizeKey(k), formatDnaValue(v)])
    .filter(([, v]) => v && v !== '{}' && v !== '[]')

  if (entries.length === 0) return null

  return (
    <div className={`rounded border ${colorCls} p-3`}>
      <div className="flex items-center gap-1.5 text-[10px] uppercase tracking-wider font-semibold mb-2 opacity-80">
        <Icon size={11} /> {title}
      </div>
      <div className="space-y-1.5">
        {entries.map(([label, val]) => (
          <div key={label} className="text-[11px] leading-snug">
            <span className="text-zinc-500 font-semibold">{label}:</span>{' '}
            <span className="text-zinc-200">{val}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

function ArtistSongsList({ artistId }) {
  const { data } = useSongs({ artistId, limit: 10 })
  const songs = data?.data?.songs || []
  if (!songs.length) {
    return <div className="text-[10px] text-zinc-600 italic">No songs yet under this artist.</div>
  }
  return (
    <div className="space-y-1">
      {songs.map(s => (
        <div key={s.song_id} className="flex items-center justify-between text-[11px] bg-zinc-950 border border-zinc-800 rounded px-2 py-1.5">
          <div className="truncate flex-1">
            <span className="text-zinc-200">{s.title}</span>
            <span className="text-zinc-600 ml-2 font-mono text-[9px]">{s.song_id.slice(0, 8)}</span>
          </div>
          <span className="text-[9px] text-zinc-500 uppercase ml-2 flex-shrink-0">
            {s.status?.replace(/_/g, ' ')}
          </span>
        </div>
      ))}
    </div>
  )
}

function ArtistCard({ artist, expanded, onToggle }) {
  const regenerate = useRegenerateArtistPortrait()
  const qc = useQueryClient()

  const handleRegenerate = async (e) => {
    e.stopPropagation()
    await regenerate.mutateAsync({ artistId: artist.artist_id })
    qc.invalidateQueries({ queryKey: ['admin', 'ai-artists'] })
  }

  const approvedBadge = artist.ceo_approved ? (
    <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded border text-[9px] uppercase tracking-wider bg-emerald-500/10 border-emerald-500/30 text-emerald-300">
      <CheckCircle2 size={8} /> CEO Approved
    </span>
  ) : (
    <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded border text-[9px] uppercase tracking-wider bg-amber-500/10 border-amber-500/30 text-amber-300">
      pending approval
    </span>
  )

  const portraitAssetId = artist.visual_dna?.reference_sheet_asset_id
  const portraitUrl = portraitAssetId
    ? resolveBackendUrl(`/api/v1/admin/visual/${portraitAssetId}.png`)
    : null

  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900 overflow-hidden">
      <button
        onClick={onToggle}
        className="w-full flex items-center gap-3 px-4 py-3 hover:bg-zinc-900/60 transition-colors text-left"
      >
        {portraitUrl ? (
          <img
            src={portraitUrl}
            alt={artist.stage_name}
            className="w-10 h-10 rounded-full object-cover border border-zinc-700 flex-shrink-0"
          />
        ) : (
          <div className="w-10 h-10 rounded-full bg-gradient-to-br from-violet-500/30 to-cyan-500/30 flex items-center justify-center text-zinc-200 font-bold flex-shrink-0">
            {artist.stage_name?.[0] || '?'}
          </div>
        )}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-sm font-bold text-zinc-100 truncate">{artist.stage_name}</span>
            {approvedBadge}
          </div>
          <div className="text-[10px] text-zinc-500 truncate">
            {artist.primary_genre}
            {artist.adjacent_genres?.length > 0 && ` · ${artist.adjacent_genres.slice(0, 3).join(', ')}`}
          </div>
        </div>
        <div className="flex-shrink-0 text-right">
          <div className="text-xs font-semibold text-zinc-200 tabular-nums">{artist.song_count} {artist.song_count === 1 ? 'song' : 'songs'}</div>
          <div className="text-[9px] text-zinc-600">artist_id {artist.artist_id.slice(0, 8)}</div>
        </div>
        {expanded ? <ChevronUp size={14} className="text-zinc-500" /> : <ChevronDown size={14} className="text-zinc-500" />}
      </button>

      {expanded && (
        <div className="border-t border-zinc-800 p-4 space-y-3 bg-zinc-950/40">
          {portraitUrl && (
            <div className="relative flex justify-center">
              <img
                src={portraitUrl}
                alt={artist.stage_name}
                className="w-64 h-64 rounded-lg object-cover border border-zinc-700"
              />
              <button
                onClick={handleRegenerate}
                disabled={regenerate.isPending}
                className="absolute top-2 right-2 flex items-center gap-1 px-2 py-1 bg-zinc-900/80 hover:bg-violet-600/40 border border-zinc-700 text-zinc-300 text-[10px] rounded backdrop-blur transition-colors disabled:opacity-40"
                title="Regenerate portrait"
              >
                {regenerate.isPending ? (
                  <Loader2 size={11} className="animate-spin" />
                ) : (
                  <Camera size={11} />
                )}
                Regen
              </button>
            </div>
          )}
          {/* Audience tags */}
          {artist.audience_tags?.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {artist.audience_tags.map(tag => (
                <span key={tag} className="inline-flex items-center gap-1 text-[10px] text-zinc-300 bg-zinc-800 border border-zinc-700 rounded px-2 py-0.5">
                  <Hash size={9} /> {tag}
                </span>
              ))}
            </div>
          )}

          {/* 8-view reference sheet (PRD §20) */}
          <ReferenceSheetGrid artistId={artist.artist_id} />

          {/* DNA blocks */}
          <div className="grid grid-cols-2 gap-2">
            <DNABlock icon={Mic}      title="Voice DNA"    data={artist.voice_dna}    color="violet" />
            <DNABlock icon={BookOpen} title="Lyrical DNA"  data={artist.lyrical_dna}  color="cyan" />
            <DNABlock icon={Palette}  title="Visual DNA"   data={artist.visual_dna}   color="amber" />
            <DNABlock icon={Users}    title="Persona"      data={artist.persona_dna}  color="emerald" />
          </div>

          {/* Song Structure (task #109) */}
          <ArtistStructureBlock artist={artist} />

          {/* Recent songs */}
          <div className="space-y-1">
            <div className="text-[10px] uppercase tracking-wider text-zinc-500 flex items-center gap-1">
              <Music2 size={10} /> Recent songs
            </div>
            <ArtistSongsList artistId={artist.artist_id} />
          </div>
        </div>
      )}
    </div>
  )
}

// ─── Song Structure block (task #109 Phase 4) ────────────────────────────

function ArtistStructureBlock({ artist }) {
  const initialTemplate = artist.structure_template || null
  const initialOverride = Boolean(artist.genre_structure_override)
  const [template, setTemplate] = useState(initialTemplate)
  const [override, setOverride] = useState(initialOverride)
  const [editing, setEditing] = useState(false)
  const patch = usePatchArtistStructure()
  const qc = useQueryClient()
  const [saved, setSaved] = useState(false)

  const dirty =
    JSON.stringify(template) !== JSON.stringify(initialTemplate) ||
    override !== initialOverride

  const handleSave = async () => {
    await patch.mutateAsync({
      artistId: artist.artist_id,
      structure_template: template, // explicit null clears
      genre_structure_override: override,
    })
    setSaved(true)
    qc.invalidateQueries({ queryKey: ['admin', 'ai-artists'] })
    setTimeout(() => setSaved(false), 2000)
    setEditing(false)
  }

  const handleClear = async () => {
    if (!window.confirm('Clear this artist\'s custom structure? They will follow the genre default afterward.')) return
    setTemplate(null)
    setOverride(false)
    await patch.mutateAsync({
      artistId: artist.artist_id,
      structure_template: null,
      genre_structure_override: false,
    })
    qc.invalidateQueries({ queryKey: ['admin', 'ai-artists'] })
    setEditing(false)
  }

  return (
    <div className="space-y-2 border border-zinc-800 rounded-lg p-3 bg-zinc-950/40">
      <div className="flex items-center justify-between">
        <div className="text-[10px] uppercase tracking-wider text-zinc-500 flex items-center gap-1">
          <Music2 size={10} /> Song Structure
        </div>
        {!editing && (
          <button
            onClick={() => setEditing(true)}
            className="text-xs text-violet-300 hover:text-violet-200 flex items-center gap-1"
          >
            <Edit3 size={10} /> Edit
          </button>
        )}
      </div>

      {!editing && (
        <div className="text-xs text-zinc-400 space-y-1">
          {template ? (
            <>
              <div className="text-zinc-300">
                {structureChain(template)}
              </div>
              <div className="text-[10px] text-zinc-500">
                {override
                  ? 'Override active — genre template ignored, this structure used as-is'
                  : 'Blended with genre default — artist sections override matching genre sections by name'}
              </div>
            </>
          ) : (
            <div className="text-zinc-500 italic">
              No artist override — generation uses the genre default for{' '}
              <code className="text-zinc-400">{artist.primary_genre}</code>.
            </div>
          )}
        </div>
      )}

      {editing && (
        <div className="space-y-3">
          <label className="flex items-start gap-2 text-xs text-zinc-300 cursor-pointer">
            <input
              type="checkbox"
              checked={override}
              onChange={(e) => setOverride(e.target.checked)}
              className="mt-0.5"
            />
            <span className="flex-1">
              <span className="font-medium">Use artist template only (ignore genre blending)</span>
              <span
                className="inline-flex items-center justify-center ml-1.5 w-3.5 h-3.5 rounded-full bg-zinc-800 text-zinc-400 cursor-help"
                title="When unchecked, this artist's song structure is blended with their primary genre's template — genre sets the skeleton, the artist can shorten/lengthen or add/remove named sections. When checked, the genre template is ignored entirely and the artist's custom structure is used as-is."
              >
                <Info size={9} />
              </span>
            </span>
          </label>

          <div>
            <div className="text-[10px] uppercase tracking-wider text-zinc-500 mb-1.5">
              Custom structure {template === null && '(none — add sections to begin)'}
            </div>
            <GenreStructureEditor
              value={template || []}
              onChange={(next) => setTemplate(next.length === 0 ? null : next)}
              disabled={patch.isPending}
            />
          </div>

          {patch.isError && (
            <div className="flex items-center gap-2 text-rose-300 text-xs bg-rose-500/10 border border-rose-500/30 rounded px-3 py-2">
              <AlertCircle size={12} />
              Save failed: {patch.error?.response?.data?.detail || patch.error?.message || 'unknown error'}
            </div>
          )}

          <div className="flex gap-2 justify-end">
            <button
              onClick={handleClear}
              disabled={patch.isPending}
              className="px-3 py-1.5 text-xs text-zinc-500 hover:text-rose-300 disabled:opacity-50"
            >
              Clear
            </button>
            <button
              onClick={() => { setTemplate(initialTemplate); setOverride(initialOverride); setEditing(false) }}
              disabled={patch.isPending}
              className="px-3 py-1.5 text-xs text-zinc-400 hover:text-zinc-200 disabled:opacity-50"
            >
              Cancel
            </button>
            <button
              onClick={handleSave}
              disabled={patch.isPending || !dirty}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-violet-600 hover:bg-violet-700 disabled:opacity-50 text-white rounded text-xs font-medium"
            >
              {patch.isPending ? <Loader2 size={11} className="animate-spin" /> : saved ? <Check size={11} /> : <Save size={11} />}
              {saved ? 'Saved' : 'Save'}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}


function CreateFromDescriptionForm({ onCreated, onCancel }) {
  // Two-step flow:
  //   Step 1: describe + generate preview (5 name candidates + full persona)
  //   Step 2: CEO picks one of the 5 names → finalize + generate portrait
  const [description, setDescription] = useState('')
  const [genre, setGenre] = useState('')
  const [preview, setPreview] = useState(null)
  const [chosenName, setChosenName] = useState(null)
  const [customName, setCustomName] = useState('')
  const previewMut = usePreviewPersona()
  const createMut = useCreateArtistFromPersona()
  const qc = useQueryClient()

  const handlePreview = async (e) => {
    e.preventDefault()
    if (!description || !genre) return
    setPreview(null)
    setChosenName(null)
    try {
      const res = await previewMut.mutateAsync({
        body: { description, target_genre: genre },
      })
      const p = res?.data
      setPreview(p)
      setChosenName(p?.default_choice || null)
    } catch (_) {}
  }

  const handleCreate = async () => {
    if (!preview || !chosenName) return
    try {
      await createMut.mutateAsync({
        body: {
          persona: preview.persona,
          chosen_stage_name: customName.trim() || chosenName,
          target_genre: preview.target_genre,
          auto_approve: true,
        },
      })
      qc.invalidateQueries({ queryKey: ['admin', 'ai-artists'] })
      onCreated?.()
    } catch (_) {}
  }

  const handleReset = () => {
    setPreview(null)
    setChosenName(null)
    setCustomName('')
    previewMut.reset()
    createMut.reset()
  }

  return (
    <div className="rounded-xl border border-violet-500/40 bg-violet-500/5 p-4 space-y-3 mb-4">
      <div className="flex items-center justify-between">
        <div className="text-sm font-semibold text-zinc-100">
          {preview ? 'Step 2 — pick a stage name' : 'Step 1 — describe the artist'}
        </div>
        <button type="button" onClick={onCancel} className="text-zinc-500 hover:text-zinc-200">
          <X size={14} />
        </button>
      </div>

      {/* STEP 1 — description + genre */}
      {!preview && (
        <form onSubmit={handlePreview} className="space-y-3">
          <div>
            <label className="text-[10px] text-zinc-500 block mb-1">Natural-language description</label>
            <textarea
              value={description}
              onChange={e => setDescription(e.target.value)}
              placeholder="e.g. melancholy bedroom-pop girl from Portland, writes about longing and rainy streets, Phoebe Bridgers energy but more dreamy"
              rows={3}
              className="w-full bg-zinc-900 border border-zinc-700 text-zinc-200 text-xs rounded px-2 py-1.5 resize-none"
              required
            />
          </div>
          <div>
            <label className="text-[10px] text-zinc-500 block mb-1">Target genre</label>
            <input
              type="text"
              value={genre}
              onChange={e => setGenre(e.target.value)}
              placeholder="caribbean.reggae"
              className="w-full bg-zinc-900 border border-zinc-700 text-zinc-200 text-xs rounded px-2 py-1.5"
              required
            />
          </div>
          <button
            type="submit"
            disabled={!description || !genre || previewMut.isPending}
            className="w-full flex items-center justify-center gap-1.5 px-3 py-2 bg-violet-600 hover:bg-violet-500 disabled:opacity-40 text-white text-xs font-medium rounded"
          >
            {previewMut.isPending ? <Loader2 size={12} className="animate-spin" /> : <Plus size={12} />}
            {previewMut.isPending ? 'Generating 5 name options + persona...' : 'Generate preview'}
          </button>
          {previewMut.error && (
            <div className="text-[10px] text-rose-300">
              {String(previewMut.error?.response?.data?.detail || previewMut.error?.message)}
            </div>
          )}
        </form>
      )}

      {/* STEP 2 — pick a stage name */}
      {preview && (
        <div className="space-y-3">
          {/* Reference artists used */}
          {preview.references_used?.length > 0 && (
            <div className="bg-zinc-950 border border-zinc-800 rounded p-3">
              <div className="text-[10px] uppercase tracking-wider text-zinc-500 mb-1.5">
                Grounded in these real reference artists (by current momentum)
              </div>
              <div className="flex flex-wrap gap-1.5">
                {preview.references_used.map(r => (
                  <span key={r.name} className="inline-flex items-center gap-1 text-[11px] text-zinc-300 bg-zinc-900 border border-zinc-700 rounded px-2 py-0.5">
                    {r.name}
                    {r.momentum > 0 && <span className="text-zinc-600">×{r.momentum}</span>}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* 5 name candidates */}
          <div>
            <div className="text-[10px] uppercase tracking-wider text-zinc-500 mb-2">
              Pick one of 5 stage names
            </div>
            <div className="grid grid-cols-1 gap-1.5">
              {(preview.stage_name_alternatives || []).map(name => (
                <button
                  key={name}
                  type="button"
                  onClick={() => { setChosenName(name); setCustomName('') }}
                  className={`text-left px-3 py-2 rounded border transition-colors ${
                    (customName.trim() || chosenName) === name
                      ? 'bg-violet-600/30 border-violet-500 text-white'
                      : 'bg-zinc-950 border-zinc-800 text-zinc-300 hover:bg-zinc-900'
                  }`}
                >
                  <div className="font-semibold text-sm">{name}</div>
                </button>
              ))}
            </div>
          </div>

          {/* Or enter a custom name */}
          <div>
            <label className="text-[10px] text-zinc-500 block mb-1">
              Or type a custom name (overrides the picks above)
            </label>
            <input
              type="text"
              value={customName}
              onChange={e => setCustomName(e.target.value)}
              placeholder="Custom stage name"
              className="w-full bg-zinc-900 border border-zinc-700 text-zinc-200 text-xs rounded px-2 py-1.5"
            />
          </div>

          {/* Show the persona's key details so CEO knows what they're approving */}
          <div className="bg-zinc-950 border border-zinc-800 rounded p-3 space-y-1 text-[11px]">
            <div className="text-[10px] uppercase tracking-wider text-zinc-500 mb-1">Persona preview</div>
            {preview.persona?.persona_dna?.backstory && (
              <div>
                <span className="text-zinc-500">Backstory: </span>
                <span className="text-zinc-300">{preview.persona.persona_dna.backstory}</span>
              </div>
            )}
            {preview.persona?.influences?.length > 0 && (
              <div>
                <span className="text-zinc-500">Influences: </span>
                <span className="text-zinc-300">{preview.persona.influences.join(', ')}</span>
              </div>
            )}
            {preview.persona?.lyrical_dna?.recurring_themes?.length > 0 && (
              <div>
                <span className="text-zinc-500">Themes: </span>
                <span className="text-zinc-300">{preview.persona.lyrical_dna.recurring_themes.join(', ')}</span>
              </div>
            )}
          </div>

          <div className="flex gap-2">
            <button
              onClick={handleCreate}
              disabled={createMut.isPending || (!chosenName && !customName.trim())}
              className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 bg-violet-600 hover:bg-violet-500 disabled:opacity-40 text-white text-xs font-medium rounded"
            >
              {createMut.isPending ? <Loader2 size={12} className="animate-spin" /> : <CheckCircle2 size={12} />}
              {createMut.isPending ? 'Creating + generating portrait...' : `Create "${customName.trim() || chosenName}"`}
            </button>
            <button
              onClick={handleReset}
              disabled={createMut.isPending}
              className="px-3 py-2 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 text-xs rounded border border-zinc-700"
            >
              Start over
            </button>
          </div>
          {createMut.error && (
            <div className="text-[10px] text-rose-300">
              {String(createMut.error?.response?.data?.detail || createMut.error?.message)}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// Split a comma-separated string into an array of trimmed non-empty strings.
// Used by the manual-create form to turn "pop, k-pop, r&b" into
// ["pop", "k-pop", "r&b"].
function csvSplit(s) {
  if (!s) return []
  return String(s).split(',').map(x => x.trim()).filter(Boolean)
}

function AddArtistModal({ onClose, onCreated }) {
  const create = useCreateArtistManual()
  const qc = useQueryClient()
  const [error, setError] = useState(null)
  const [result, setResult] = useState(null)

  // Basics
  const [stageName, setStageName] = useState('')
  const [legalName, setLegalName] = useState('')
  const [primaryGenre, setPrimaryGenre] = useState('')
  const [adjacentGenres, setAdjacentGenres] = useState('')
  const [age, setAge] = useState('')
  const [gender, setGender] = useState('')
  const [ethnicity, setEthnicity] = useState('')
  const [edgeProfile, setEdgeProfile] = useState('flirty_edge')
  const [contentRating, setContentRating] = useState('mild')

  // Influences / audience
  const [influences, setInfluences] = useState('')
  const [antiInfluences, setAntiInfluences] = useState('')
  const [audienceTags, setAudienceTags] = useState('')

  // Voice DNA
  const [voiceTimbre, setVoiceTimbre] = useState('')
  const [voiceRange, setVoiceRange] = useState('')
  const [voiceDelivery, setVoiceDelivery] = useState('')
  const [voiceAccent, setVoiceAccent] = useState('')
  const [voiceAutotune, setVoiceAutotune] = useState('light')

  // Visual DNA
  const [faceDescription, setFaceDescription] = useState('')
  const [bodyPresentation, setBodyPresentation] = useState('')
  const [hairSignature, setHairSignature] = useState('')
  const [colorPalette, setColorPalette] = useState('')
  const [artDirection, setArtDirection] = useState('')
  const [fashionStyleSummary, setFashionStyleSummary] = useState('')

  // Fashion DNA
  const [coreGarments, setCoreGarments] = useState('')
  const [fabricInspirations, setFabricInspirations] = useState('')
  const [silhouette, setSilhouette] = useState('')
  const [accessories, setAccessories] = useState('')
  const [footwear, setFootwear] = useState('')
  const [stylingMood, setStylingMood] = useState('')

  // Lyrical / persona
  const [recurringThemes, setRecurringThemes] = useState('')
  const [vocabLevel, setVocabLevel] = useState('conversational')
  const [language, setLanguage] = useState('en')
  const [backstory, setBackstory] = useState('')
  const [personalityTraits, setPersonalityTraits] = useState('')

  const [generatePortrait, setGeneratePortrait] = useState(true)

  const handleSubmit = async () => {
    setError(null)
    setResult(null)
    if (!stageName.trim() || !primaryGenre.trim()) {
      setError('Stage name and primary genre are required')
      return
    }
    const body = {
      stage_name: stageName.trim(),
      legal_name: legalName.trim() || undefined,
      primary_genre: primaryGenre.trim(),
      adjacent_genres: csvSplit(adjacentGenres),
      age: age ? parseInt(age, 10) : undefined,
      gender_presentation: gender || undefined,
      ethnicity_heritage: ethnicity.trim() || undefined,
      edge_profile: edgeProfile,
      content_rating: contentRating,
      influences: csvSplit(influences),
      anti_influences: csvSplit(antiInfluences),
      audience_tags: csvSplit(audienceTags),
      voice_dna: {
        timbre_core: voiceTimbre || 'clean tone',
        range_estimate: voiceRange || 'C3-E5',
        delivery_style: csvSplit(voiceDelivery),
        accent_pronunciation: voiceAccent || 'neutral',
        autotune_profile: voiceAutotune,
      },
      visual_dna: {
        face_description: faceDescription,
        body_presentation: bodyPresentation,
        hair_signature: hairSignature,
        color_palette: csvSplit(colorPalette),
        art_direction: artDirection,
        fashion_style_summary: fashionStyleSummary,
      },
      fashion_dna: {
        core_garments: csvSplit(coreGarments),
        fabric_inspirations: csvSplit(fabricInspirations),
        silhouette,
        accessories: csvSplit(accessories),
        footwear: csvSplit(footwear),
        styling_mood: stylingMood,
      },
      lyrical_dna: {
        recurring_themes: csvSplit(recurringThemes),
        vocab_level: vocabLevel,
        language,
      },
      persona_dna: {
        backstory,
        personality_traits: csvSplit(personalityTraits),
      },
      generate_portrait: generatePortrait,
      ceo_approved: true,
    }
    try {
      const res = await create.mutateAsync({ body })
      setResult(res?.data)
      qc.invalidateQueries({ queryKey: ['admin', 'ai-artists'] })
      setTimeout(() => { onCreated?.(); onClose?.() }, 1200)
    } catch (e) {
      setError(e?.response?.data?.detail || e?.message || 'creation failed')
    }
  }

  const field = (label, inputEl, hint) => (
    <label className="block text-xs text-zinc-400">
      {label}
      {inputEl}
      {hint && <div className="text-[10px] text-zinc-600 mt-0.5">{hint}</div>}
    </label>
  )
  const input = (val, setter, placeholder) => (
    <input
      type="text"
      value={val}
      onChange={(e) => setter(e.target.value)}
      placeholder={placeholder}
      className="w-full mt-1 px-3 py-2 bg-zinc-950 border border-zinc-800 rounded text-sm text-zinc-100 placeholder-zinc-600 focus:outline-none focus:border-violet-500"
    />
  )
  const textarea = (val, setter, placeholder, rows = 2) => (
    <textarea
      value={val}
      onChange={(e) => setter(e.target.value)}
      placeholder={placeholder}
      rows={rows}
      className="w-full mt-1 px-3 py-2 bg-zinc-950 border border-zinc-800 rounded text-sm text-zinc-100 placeholder-zinc-600 focus:outline-none focus:border-violet-500 resize-y"
    />
  )
  const select = (val, setter, options) => (
    <select
      value={val}
      onChange={(e) => setter(e.target.value)}
      className="w-full mt-1 px-3 py-2 bg-zinc-950 border border-zinc-800 rounded text-sm text-zinc-100"
    >
      {options.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  )

  return (
    <div className="fixed inset-0 z-50 bg-black/80 flex items-start justify-center p-4 overflow-y-auto" onClick={onClose}>
      <div className="bg-zinc-950 border border-zinc-800 rounded-xl max-w-4xl w-full my-4" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between p-4 border-b border-zinc-800 sticky top-0 bg-zinc-950 z-10">
          <div className="flex items-center gap-2 text-sm font-semibold text-zinc-200">
            <Edit3 size={14} className="text-violet-400" />
            Add artist manually
          </div>
          <button onClick={onClose} className="text-zinc-500 hover:text-zinc-300">
            <X size={16} />
          </button>
        </div>

        <div className="p-5 space-y-6">
          {/* Basics */}
          <section>
            <div className="text-[11px] uppercase tracking-wider text-violet-400 font-semibold mb-3">Basics</div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {field('Stage name *', input(stageName, setStageName, 'e.g. Kira Lune'))}
              {field('Legal name', input(legalName, setLegalName, 'defaults to stage name'))}
              {field('Primary genre *', input(primaryGenre, setPrimaryGenre, 'e.g. pop.k-pop, caribbean.reggae'), 'Use a dotted genre id from the taxonomy')}
              {field('Adjacent genres', input(adjacentGenres, setAdjacentGenres, 'comma-separated'))}
              {field('Age', input(age, setAge, '22'))}
              {field('Gender', select(gender, setGender, [
                { value: '', label: '—' }, { value: 'female', label: 'female' },
                { value: 'male', label: 'male' }, { value: 'non_binary', label: 'non_binary' },
              ]))}
              {field('Ethnicity / heritage', input(ethnicity, setEthnicity, 'Korean, Jamaican, Nigerian Yoruba…'))}
              {field('Edge profile', select(edgeProfile, setEdgeProfile, [
                { value: 'clean_edge', label: 'clean_edge (Taylor/Olivia)' },
                { value: 'flirty_edge', label: 'flirty_edge (Sabrina/Doja)' },
                { value: 'savage_edge', label: 'savage_edge (Doechii/Ice Spice)' },
              ]))}
              {field('Content rating', select(contentRating, setContentRating, [
                { value: 'clean', label: 'clean' }, { value: 'mild', label: 'mild' }, { value: 'explicit', label: 'explicit' },
              ]))}
            </div>
          </section>

          {/* Influences + audience */}
          <section>
            <div className="text-[11px] uppercase tracking-wider text-violet-400 font-semibold mb-3">Influences & audience</div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              {field('Influences', textarea(influences, setInfluences, 'Sabrina Carpenter, NewJeans, IVE'), 'comma-separated real artists')}
              {field('Anti-influences', textarea(antiInfluences, setAntiInfluences, 'artists to NOT sound like'))}
              {field('Audience tags', textarea(audienceTags, setAudienceTags, 'gen_z, female_lean, urban'))}
            </div>
          </section>

          {/* Voice DNA */}
          <section>
            <div className="text-[11px] uppercase tracking-wider text-violet-400 font-semibold mb-3">Voice DNA</div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {field('Timbre', input(voiceTimbre, setVoiceTimbre, 'soft yet powerful, warm resonance'))}
              {field('Range estimate', input(voiceRange, setVoiceRange, 'A3-B5 chest, falsetto to C6'))}
              {field('Delivery style', input(voiceDelivery, setVoiceDelivery, 'expressive, intimate (csv)'))}
              {field('Accent', input(voiceAccent, setVoiceAccent, 'light Korean with American influence'))}
              {field('Autotune profile', select(voiceAutotune, setVoiceAutotune, [
                { value: 'none', label: 'none' }, { value: 'light', label: 'light' },
                { value: 'medium', label: 'medium' }, { value: 'heavy', label: 'heavy' },
              ]))}
            </div>
          </section>

          {/* Visual DNA */}
          <section>
            <div className="text-[11px] uppercase tracking-wider text-violet-400 font-semibold mb-3">Visual DNA</div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {field('Face description', textarea(faceDescription, setFaceDescription, 'Korean features, almond eyes, softly-arched brows'))}
              {field('Body presentation', input(bodyPresentation, setBodyPresentation, 'slim / athletic'))}
              {field('Hair signature', input(hairSignature, setHairSignature, 'long flowing dark hair with soft waves'))}
              {field('Color palette', input(colorPalette, setColorPalette, '#FF6F61, #6A5ACD, #FFD700'), 'hex or color names, comma-separated')}
              {field('Art direction', textarea(artDirection, setArtDirection, 'neon Seoul rooftop, dreamy pastels'))}
              {field('Fashion style summary', textarea(fashionStyleSummary, setFashionStyleSummary, 'Seoul 4th-gen K-pop pastel-noir editorial'))}
            </div>
          </section>

          {/* Fashion DNA */}
          <section>
            <div className="text-[11px] uppercase tracking-wider text-violet-400 font-semibold mb-3">Fashion DNA</div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {field('Core garments', textarea(coreGarments, setCoreGarments, 'cropped knit cardigan, pleated micro-mini skirt, moto jacket (csv)'))}
              {field('Fabric inspirations', textarea(fabricInspirations, setFabricInspirations, 'washed denim, hanbok silk, translucent mesh (csv)'))}
              {field('Silhouette', input(silhouette, setSilhouette, 'Seoul 4th-gen layered, fitted top + volume bottom'))}
              {field('Accessories', textarea(accessories, setAccessories, 'layered silver chains, statement earrings (csv)'))}
              {field('Footwear', input(footwear, setFootwear, 'platform Mary Janes, chunky white sneakers (csv)'))}
              {field('Styling mood', input(stylingMood, setStylingMood, 'Seoul 4th-gen K-pop pastel-noir'))}
            </div>
          </section>

          {/* Lyrical + persona */}
          <section>
            <div className="text-[11px] uppercase tracking-wider text-violet-400 font-semibold mb-3">Lyrical & persona</div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {field('Recurring themes', textarea(recurringThemes, setRecurringThemes, 'delulu romance, manifestation, 3am confessions (csv)'))}
              {field('Vocab level', select(vocabLevel, setVocabLevel, [
                { value: 'simple', label: 'simple' }, { value: 'conversational', label: 'conversational' },
                { value: 'poetic', label: 'poetic' }, { value: 'abstract', label: 'abstract' },
              ]))}
              {field('Language', input(language, setLanguage, 'en, ko, es, en/ko'))}
              {field('Personality traits', textarea(personalityTraits, setPersonalityTraits, 'confident, flirty, internet-native (csv)'))}
              <div className="md:col-span-2">
                {field('Backstory', textarea(backstory, setBackstory, '2-3 sentence origin story', 3))}
              </div>
            </div>
          </section>

          {/* Portrait */}
          <section>
            <label className="flex items-center gap-2 text-xs text-zinc-400">
              <input
                type="checkbox"
                checked={generatePortrait}
                onChange={(e) => setGeneratePortrait(e.target.checked)}
                className="accent-violet-500"
              />
              Generate portrait via gpt-image-1 after create (~$0.17, ~15s)
            </label>
          </section>

          {error && (
            <div className="bg-rose-500/10 border border-rose-500/30 rounded p-2 text-xs text-rose-300 flex items-center gap-2">
              <AlertCircle size={14} /> {error}
            </div>
          )}

          {result && (
            <div className="bg-emerald-500/10 border border-emerald-500/30 rounded p-3 text-xs text-emerald-300 space-y-1">
              <div className="flex items-center gap-2"><CheckCircle2 size={14} /> Created {result.stage_name}</div>
              <div className="text-[10px] text-emerald-400/70 font-mono">artist_id: {result.artist_id}</div>
              {result.portrait && <div className="text-[10px]">portrait: {result.portrait.asset_id?.slice(0, 8)} ({Math.round((result.portrait.bytes || 0) / 1024)} KB)</div>}
              {result.portrait_error && <div className="text-[10px] text-amber-400">portrait failed: {result.portrait_error}</div>}
            </div>
          )}
        </div>

        <div className="flex items-center justify-end gap-2 p-4 border-t border-zinc-800 sticky bottom-0 bg-zinc-950">
          <button
            onClick={onClose}
            className="px-4 py-2 text-zinc-400 text-xs hover:text-zinc-200"
          >
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            disabled={create.isPending || !stageName.trim() || !primaryGenre.trim()}
            className="px-5 py-2 bg-violet-600 hover:bg-violet-500 disabled:bg-zinc-800 disabled:text-zinc-600 text-white text-sm font-medium rounded flex items-center gap-2"
          >
            {create.isPending ? <Loader2 size={14} className="animate-spin" /> : <Plus size={14} />}
            {create.isPending ? 'Creating…' : 'Create artist'}
          </button>
        </div>
      </div>
    </div>
  )
}


export default function Artists() {
  const [expandedId, setExpandedId] = useState(null)
  const [showNew, setShowNew] = useState(false)
  const [showManual, setShowManual] = useState(false)
  const { data, isLoading, isError, error } = useAIArtists('active')

  const artists = data?.data?.artists || []

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <div className="flex items-start justify-between mb-6">
        <div>
          <div className="flex items-center gap-3 mb-1">
            <Users size={24} className="text-violet-400" />
            <h1 className="text-2xl font-bold text-zinc-100">Artists</h1>
          </div>
          <p className="text-sm text-zinc-500">
            The AI roster. Each row is one artist with full DNA (voice, visual, lyrical, persona, social) plus their catalog.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {!showNew && (
            <button
              onClick={() => setShowNew(true)}
              className="flex items-center gap-1.5 px-3 py-2 bg-zinc-800 hover:bg-zinc-700 text-zinc-200 text-xs font-medium rounded-lg border border-zinc-700"
            >
              <Plus size={14} /> From description
            </button>
          )}
          <button
            onClick={() => setShowManual(true)}
            className="flex items-center gap-1.5 px-3 py-2 bg-violet-600 hover:bg-violet-500 text-white text-xs font-medium rounded-lg"
          >
            <Edit3 size={14} /> Add manually
          </button>
        </div>
      </div>

      {showNew && (
        <CreateFromDescriptionForm
          onCreated={() => setShowNew(false)}
          onCancel={() => setShowNew(false)}
        />
      )}

      {showManual && (
        <AddArtistModal
          onClose={() => setShowManual(false)}
          onCreated={() => setShowManual(false)}
        />
      )}

      {isLoading && (
        <div className="flex items-center justify-center py-20 text-zinc-500 gap-2">
          <Loader2 size={18} className="animate-spin" /> Loading roster...
        </div>
      )}

      {isError && (
        <div className="bg-rose-500/10 border border-rose-500/30 rounded-xl p-4 text-rose-300 text-sm">
          Failed to load artists: {error?.message}
        </div>
      )}

      {!isLoading && artists.length === 0 && (
        <div className="flex flex-col items-center justify-center py-20 text-center">
          <Users size={40} className="text-zinc-700 mb-3" />
          <div className="text-sm text-zinc-400 mb-1">No active artists yet</div>
          <div className="text-xs text-zinc-600 max-w-sm">
            POST /admin/artists to create one, or run the assignment engine via Settings → Pending Decisions.
          </div>
        </div>
      )}

      <div className="space-y-2">
        {artists.map(artist => (
          <ArtistCard
            key={artist.artist_id}
            artist={artist}
            expanded={expandedId === artist.artist_id}
            onToggle={() => setExpandedId(expandedId === artist.artist_id ? null : artist.artist_id)}
          />
        ))}
      </div>
    </div>
  )
}
