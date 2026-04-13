import { useState } from 'react'
import {
  Users, Loader2, ChevronDown, ChevronUp, Music2, CheckCircle2,
  Mic, Palette, BookOpen, Hash, Plus, X,
} from 'lucide-react'
import { useQueryClient } from '@tanstack/react-query'
import {
  useAIArtists, useSongs, useCreateArtistFromDescription,
} from '../hooks/useSoundPulse'

function DNABlock({ icon: Icon, title, data, color = 'violet' }) {
  if (!data || Object.keys(data).length === 0) return null
  const colorCls = {
    violet:  'border-violet-500/30 bg-violet-500/5 text-violet-200',
    cyan:    'border-cyan-500/30 bg-cyan-500/5 text-cyan-200',
    amber:   'border-amber-500/30 bg-amber-500/5 text-amber-200',
    emerald: 'border-emerald-500/30 bg-emerald-500/5 text-emerald-200',
    rose:    'border-rose-500/30 bg-rose-500/5 text-rose-200',
  }[color]
  return (
    <div className={`rounded border ${colorCls} p-3`}>
      <div className="flex items-center gap-1.5 text-[10px] uppercase tracking-wider font-semibold mb-2 opacity-80">
        <Icon size={11} /> {title}
      </div>
      <pre className="text-[10px] text-zinc-300 whitespace-pre-wrap font-mono leading-relaxed max-h-48 overflow-y-auto">
        {JSON.stringify(data, null, 2)}
      </pre>
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
  const approvedBadge = artist.ceo_approved ? (
    <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded border text-[9px] uppercase tracking-wider bg-emerald-500/10 border-emerald-500/30 text-emerald-300">
      <CheckCircle2 size={8} /> CEO Approved
    </span>
  ) : (
    <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded border text-[9px] uppercase tracking-wider bg-amber-500/10 border-amber-500/30 text-amber-300">
      pending approval
    </span>
  )

  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900 overflow-hidden">
      <button
        onClick={onToggle}
        className="w-full flex items-center gap-3 px-4 py-3 hover:bg-zinc-900/60 transition-colors text-left"
      >
        <div className="w-9 h-9 rounded-full bg-gradient-to-br from-violet-500/30 to-cyan-500/30 flex items-center justify-center text-zinc-200 font-bold flex-shrink-0">
          {artist.stage_name?.[0] || '?'}
        </div>
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

          {/* DNA JSONs */}
          <div className="grid grid-cols-2 gap-2">
            <DNABlock icon={Mic}      title="Voice DNA"   data={artist.voice_dna}   color="violet" />
            <DNABlock icon={BookOpen} title="Lyrical DNA" data={artist.lyrical_dna} color="cyan" />
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
  const [description, setDescription] = useState('')
  const [genre, setGenre] = useState('')
  const [autoApprove, setAutoApprove] = useState(false)
  const create = useCreateArtistFromDescription()
  const qc = useQueryClient()

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!description || !genre) return
    try {
      await create.mutateAsync({
        body: {
          description,
          target_genre: genre,
          auto_approve: autoApprove,
        },
      })
      qc.invalidateQueries({ queryKey: ['admin', 'ai-artists'] })
      onCreated?.()
    } catch (_) { /* surfaced via create.error */ }
  }

  return (
    <form onSubmit={handleSubmit} className="rounded-xl border border-violet-500/40 bg-violet-500/5 p-4 space-y-3 mb-4">
      <div className="flex items-center justify-between">
        <div className="text-sm font-semibold text-zinc-100">Create artist from description</div>
        <button type="button" onClick={onCancel} className="text-zinc-500 hover:text-zinc-200">
          <X size={14} />
        </button>
      </div>
      <div>
        <label className="text-[10px] text-zinc-500 block mb-1">Natural-language description</label>
        <textarea
          value={description}
          onChange={e => setDescription(e.target.value)}
          placeholder="e.g. melancholy bedroom-pop girl from Portland, writes about longing and rainy streets, plays bass and writes in her journal, Phoebe Bridgers energy but more dreamy"
          rows={3}
          className="w-full bg-zinc-900 border border-zinc-700 text-zinc-200 text-xs rounded px-2 py-1.5 resize-none"
          required
        />
      </div>
      <div className="grid grid-cols-2 gap-2">
        <div>
          <label className="text-[10px] text-zinc-500 block mb-1">Target genre</label>
          <input
            type="text"
            value={genre}
            onChange={e => setGenre(e.target.value)}
            placeholder="pop.bedroom-pop"
            className="w-full bg-zinc-900 border border-zinc-700 text-zinc-200 text-xs rounded px-2 py-1.5"
            required
          />
        </div>
        <label className="flex items-end gap-1.5 text-[10px] text-zinc-400 cursor-pointer pb-1.5">
          <input
            type="checkbox"
            checked={autoApprove}
            onChange={e => setAutoApprove(e.target.checked)}
            className="accent-violet-500"
          />
          Auto-approve (skip CEO gate)
        </label>
      </div>
      <button
        type="submit"
        disabled={!description || !genre || create.isPending}
        className="w-full flex items-center justify-center gap-1.5 px-3 py-2 bg-violet-600 hover:bg-violet-500 disabled:opacity-40 text-white text-xs font-medium rounded"
      >
        {create.isPending ? <Loader2 size={12} className="animate-spin" /> : <Plus size={12} />}
        {create.isPending ? 'Blending persona via LLM...' : 'Create artist'}
      </button>
      {create.error && (
        <div className="text-[10px] text-rose-300">
          {String(create.error?.response?.data?.detail || create.error?.message)}
        </div>
      )}
    </form>
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
