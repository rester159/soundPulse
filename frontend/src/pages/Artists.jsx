import { useState } from 'react'
import {
  Users, Loader2, ChevronDown, ChevronUp, Music2, CheckCircle2,
  Mic, Palette, BookOpen, Hash, Plus, X, RefreshCw, Camera,
} from 'lucide-react'
import { useQueryClient } from '@tanstack/react-query'
import {
  useAIArtists, useSongs, useCreateArtistFromDescription,
  useRegenerateArtistPortrait, useArtistReferenceSheet,
  useGenerateReferenceSheet, usePreviewPersona,
  useCreateArtistFromPersona, getBaseUrl,
} from '../hooks/useSoundPulse'

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

export default function Artists() {
  const [expandedId, setExpandedId] = useState(null)
  const [showNew, setShowNew] = useState(false)
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
        {!showNew && (
          <button
            onClick={() => setShowNew(true)}
            className="flex items-center gap-1.5 px-3 py-2 bg-violet-600 hover:bg-violet-500 text-white text-xs font-medium rounded-lg"
          >
            <Plus size={14} /> New artist
          </button>
        )}
      </div>

      {showNew && (
        <CreateFromDescriptionForm
          onCreated={() => setShowNew(false)}
          onCancel={() => setShowNew(false)}
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
