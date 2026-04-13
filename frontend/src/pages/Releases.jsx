import { useState } from 'react'
import {
  Package, Loader2, ChevronDown, ChevronUp, Plus, X, Calendar,
  Disc3, Crown, Trash2, AlertCircle, CheckCircle2,
} from 'lucide-react'
import { useQueryClient } from '@tanstack/react-query'
import {
  useReleases, useRelease, useCreateRelease, useAddTrackToRelease,
  useRemoveTrackFromRelease, useAIArtists, useSongs,
} from '../hooks/useSoundPulse'

const STATUS_COLORS = {
  planning:           'bg-zinc-700/30 text-zinc-300 border-zinc-600/40',
  submitted:          'bg-amber-500/15 text-amber-300 border-amber-500/30',
  live:               'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
  takedown_requested: 'bg-rose-500/15 text-rose-300 border-rose-500/30',
  taken_down:         'bg-zinc-800 text-zinc-500 border-zinc-700',
}

function StatusPill({ status }) {
  const cls = STATUS_COLORS[status] || 'bg-zinc-800 text-zinc-400 border-zinc-700'
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded border text-[10px] font-semibold uppercase tracking-wider ${cls}`}>
      {status?.replace(/_/g, ' ')}
    </span>
  )
}

function AddTrackForm({ releaseId, releaseArtistId, onDone }) {
  const [songId, setSongId] = useState('')
  const [trackNumber, setTrackNumber] = useState(1)
  const [isLead, setIsLead] = useState(false)
  const addTrack = useAddTrackToRelease()
  const qc = useQueryClient()

  // Only show songs in bindable status, bound to the release's artist
  const { data: songsData } = useSongs({ status: 'qa_passed' })
  const eligible = (songsData?.data?.songs || []).filter(
    s => s.primary_artist_id === releaseArtistId && !s.release_id
  )

  const handleAdd = async (e) => {
    e.preventDefault()
    if (!songId) return
    try {
      await addTrack.mutateAsync({
        releaseId,
        body: { song_id: songId, track_number: trackNumber, is_lead_single: isLead },
      })
      qc.invalidateQueries({ queryKey: ['admin', 'releases'] })
      qc.invalidateQueries({ queryKey: ['admin', 'songs'] })
      onDone?.()
    } catch (_) { /* surface via addTrack.error */ }
  }

  return (
    <form onSubmit={handleAdd} className="bg-zinc-950 border border-zinc-800 rounded p-3 space-y-2">
      <div className="text-[10px] uppercase tracking-wider text-zinc-500">Add a qa_passed track</div>
      {eligible.length === 0 ? (
        <div className="flex items-start gap-2 text-[11px] text-amber-300 bg-amber-500/10 border border-amber-500/30 rounded p-2">
          <AlertCircle size={12} className="flex-shrink-0 mt-0.5" />
          <div>
            No qa_passed, unbound songs under this release's artist. Mark a song qa_passed via the Songs page or run the auto-QA sweep.
          </div>
        </div>
      ) : (
        <>
          <select
            value={songId}
            onChange={e => setSongId(e.target.value)}
            className="w-full bg-zinc-900 border border-zinc-700 text-zinc-200 text-xs rounded px-2 py-1.5"
          >
            <option value="">— pick a song —</option>
            {eligible.map(s => (
              <option key={s.song_id} value={s.song_id}>
                {s.title} ({s.song_id.slice(0, 8)})
              </option>
            ))}
          </select>
          <div className="flex items-center gap-2">
            <label className="text-[10px] text-zinc-500">Track #</label>
            <input
              type="number"
              min="1"
              value={trackNumber}
              onChange={e => setTrackNumber(parseInt(e.target.value, 10) || 1)}
              className="w-16 bg-zinc-900 border border-zinc-700 text-zinc-200 text-xs rounded px-2 py-1.5 tabular-nums"
            />
            <label className="flex items-center gap-1.5 text-[10px] text-zinc-400 ml-auto cursor-pointer">
              <input
                type="checkbox"
                checked={isLead}
                onChange={e => setIsLead(e.target.checked)}
                className="accent-violet-500"
              />
              Lead single
            </label>
          </div>
          <button
            type="submit"
            disabled={!songId || addTrack.isPending}
            className="w-full flex items-center justify-center gap-1.5 px-3 py-1.5 bg-violet-600 hover:bg-violet-500 disabled:opacity-40 text-white text-xs font-medium rounded"
          >
            {addTrack.isPending ? <Loader2 size={12} className="animate-spin" /> : <Plus size={12} />}
            Add to release
          </button>
        </>
      )}
      {addTrack.error && (
        <div className="text-[10px] text-rose-300">
          {String(addTrack.error?.response?.data?.detail || addTrack.error?.message)}
        </div>
      )}
    </form>
  )
}

function ReleaseDetail({ releaseId }) {
  const [showAddTrack, setShowAddTrack] = useState(false)
  const { data, isLoading } = useRelease(releaseId)
  const removeTrack = useRemoveTrackFromRelease()
  const qc = useQueryClient()

  const release = data?.data
  if (isLoading) {
    return <div className="py-4 text-zinc-500 text-xs flex items-center gap-2"><Loader2 size={12} className="animate-spin" /> Loading release detail...</div>
  }
  if (!release) return null

  const handleRemove = async (songId) => {
    await removeTrack.mutateAsync({ releaseId, songId })
    qc.invalidateQueries({ queryKey: ['admin', 'releases'] })
    qc.invalidateQueries({ queryKey: ['admin', 'songs'] })
  }

  return (
    <div className="space-y-3 bg-zinc-950/40 p-4 border-t border-zinc-800">
      {/* Meta grid */}
      <div className="grid grid-cols-4 gap-2 text-[10px]">
        <MetaBox label="Type"         value={release.release_type} />
        <MetaBox label="Release Date" value={release.release_date || '—'} />
        <MetaBox label="Distributor"  value={release.distributor || '—'} />
        <MetaBox label="UPC"          value={release.upc || '—'} />
      </div>

      {/* Tracks list */}
      <div className="space-y-1">
        <div className="text-[10px] uppercase tracking-wider text-zinc-500 flex items-center gap-1">
          <Disc3 size={10} /> Tracks ({release.track_count})
        </div>
        {release.tracks.length === 0 && (
          <div className="text-[10px] text-zinc-600 italic py-2">No tracks yet.</div>
        )}
        {release.tracks.map(t => (
          <div key={t.song_id} className="flex items-center justify-between bg-zinc-950 border border-zinc-800 rounded px-2 py-1.5 text-[11px]">
            <div className="flex items-center gap-2 min-w-0 flex-1">
              <span className="text-zinc-600 tabular-nums font-mono text-[10px] flex-shrink-0">#{t.track_number}</span>
              {t.is_lead_single && <Crown size={11} className="text-amber-400 flex-shrink-0" title="Lead single" />}
              <span className="text-zinc-200 truncate">{t.title}</span>
              {t.isrc && <span className="text-zinc-500 font-mono text-[9px] flex-shrink-0">{t.isrc}</span>}
            </div>
            <div className="flex items-center gap-2 flex-shrink-0">
              <span className="text-[9px] text-zinc-500 uppercase">{t.status?.replace(/_/g, ' ')}</span>
              <button
                onClick={() => handleRemove(t.song_id)}
                title="Unbind"
                className="p-1 hover:bg-rose-600/20 rounded text-zinc-500 hover:text-rose-300 transition-colors"
              >
                <Trash2 size={11} />
              </button>
            </div>
          </div>
        ))}
      </div>

      {/* Add track button / form */}
      {release.status === 'planning' && (
        !showAddTrack ? (
          <button
            onClick={() => setShowAddTrack(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 text-xs rounded transition-colors"
          >
            <Plus size={12} /> Add track
          </button>
        ) : (
          <AddTrackForm
            releaseId={releaseId}
            releaseArtistId={release.artist_id}
            onDone={() => setShowAddTrack(false)}
          />
        )
      )}
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

function ReleaseCard({ release, expanded, onToggle }) {
  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900 overflow-hidden">
      <button
        onClick={onToggle}
        className="w-full flex items-center gap-3 px-4 py-3 hover:bg-zinc-900/60 transition-colors text-left"
      >
        <Package size={16} className="text-zinc-600 flex-shrink-0" />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-sm font-bold text-zinc-100 truncate">{release.title}</span>
            <StatusPill status={release.status} />
          </div>
          <div className="text-[10px] text-zinc-500 truncate">
            {release.artist_name || release.artist_id.slice(0, 8)} · {release.release_type}
            {release.release_date && ` · ${release.release_date}`}
          </div>
        </div>
        <div className="flex-shrink-0 text-right">
          <div className="text-xs font-semibold text-zinc-200 tabular-nums">{release.track_count} {release.track_count === 1 ? 'track' : 'tracks'}</div>
        </div>
        {expanded ? <ChevronUp size={14} className="text-zinc-500" /> : <ChevronDown size={14} className="text-zinc-500" />}
      </button>
      {expanded && <ReleaseDetail releaseId={release.id} />}
    </div>
  )
}

function CreateReleaseForm({ onCreated, onCancel }) {
  const { data: artistsData } = useAIArtists('active')
  const artists = artistsData?.data?.artists || []
  const createRelease = useCreateRelease()
  const qc = useQueryClient()

  const [form, setForm] = useState({
    artist_id: '',
    title: '',
    release_type: 'single',
    release_date: '',
    distributor: '',
  })

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!form.artist_id || !form.title) return
    try {
      await createRelease.mutateAsync({
        body: {
          artist_id: form.artist_id,
          title: form.title,
          release_type: form.release_type,
          release_date: form.release_date || null,
          distributor: form.distributor || null,
        },
      })
      qc.invalidateQueries({ queryKey: ['admin', 'releases'] })
      onCreated?.()
    } catch (_) { /* error surfaced via mutation */ }
  }

  return (
    <form onSubmit={handleSubmit} className="rounded-xl border border-violet-500/40 bg-violet-500/5 p-4 space-y-3 mb-4">
      <div className="flex items-center justify-between">
        <div className="text-sm font-semibold text-zinc-100">New release</div>
        <button type="button" onClick={onCancel} className="text-zinc-500 hover:text-zinc-200">
          <X size={14} />
        </button>
      </div>
      <div className="grid grid-cols-2 gap-2">
        <div>
          <label className="text-[10px] text-zinc-500 block mb-1">Artist</label>
          <select
            value={form.artist_id}
            onChange={e => setForm(f => ({ ...f, artist_id: e.target.value }))}
            className="w-full bg-zinc-900 border border-zinc-700 text-zinc-200 text-xs rounded px-2 py-1.5"
            required
          >
            <option value="">— pick —</option>
            {artists.map(a => (
              <option key={a.artist_id} value={a.artist_id}>{a.stage_name} ({a.primary_genre})</option>
            ))}
          </select>
        </div>
        <div>
          <label className="text-[10px] text-zinc-500 block mb-1">Type</label>
          <select
            value={form.release_type}
            onChange={e => setForm(f => ({ ...f, release_type: e.target.value }))}
            className="w-full bg-zinc-900 border border-zinc-700 text-zinc-200 text-xs rounded px-2 py-1.5"
          >
            <option value="single">single</option>
            <option value="EP">EP</option>
            <option value="album">album</option>
            <option value="compilation">compilation</option>
          </select>
        </div>
      </div>
      <div>
        <label className="text-[10px] text-zinc-500 block mb-1">Title</label>
        <input
          type="text"
          value={form.title}
          onChange={e => setForm(f => ({ ...f, title: e.target.value }))}
          placeholder="e.g. Midnight Suite"
          className="w-full bg-zinc-900 border border-zinc-700 text-zinc-200 text-xs rounded px-2 py-1.5"
          required
        />
      </div>
      <div className="grid grid-cols-2 gap-2">
        <div>
          <label className="text-[10px] text-zinc-500 block mb-1">Release date (optional)</label>
          <input
            type="date"
            value={form.release_date}
            onChange={e => setForm(f => ({ ...f, release_date: e.target.value }))}
            className="w-full bg-zinc-900 border border-zinc-700 text-zinc-200 text-xs rounded px-2 py-1.5"
          />
        </div>
        <div>
          <label className="text-[10px] text-zinc-500 block mb-1">Distributor (optional)</label>
          <select
            value={form.distributor}
            onChange={e => setForm(f => ({ ...f, distributor: e.target.value }))}
            className="w-full bg-zinc-900 border border-zinc-700 text-zinc-200 text-xs rounded px-2 py-1.5"
          >
            <option value="">—</option>
            <option value="labelgrid">LabelGrid</option>
            <option value="revelator">Revelator</option>
            <option value="sonosuite">SonoSuite</option>
          </select>
        </div>
      </div>
      <button
        type="submit"
        disabled={!form.artist_id || !form.title || createRelease.isPending}
        className="w-full flex items-center justify-center gap-1.5 px-3 py-2 bg-violet-600 hover:bg-violet-500 disabled:opacity-40 text-white text-xs font-medium rounded"
      >
        {createRelease.isPending ? <Loader2 size={12} className="animate-spin" /> : <CheckCircle2 size={12} />}
        Create release
      </button>
      {createRelease.error && (
        <div className="text-[10px] text-rose-300">
          {String(createRelease.error?.response?.data?.detail || createRelease.error?.message)}
        </div>
      )}
    </form>
  )
}

export default function Releases() {
  const [expandedId, setExpandedId] = useState(null)
  const [showNew, setShowNew] = useState(false)
  const { data, isLoading, isError, error } = useReleases()

  const releases = data?.data?.releases || []

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <div className="flex items-start justify-between mb-6">
        <div>
          <div className="flex items-center gap-3 mb-1">
            <Package size={24} className="text-violet-400" />
            <h1 className="text-2xl font-bold text-zinc-100">Releases</h1>
          </div>
          <p className="text-sm text-zinc-500">
            Single / EP / album containers. Bind qa_passed songs to create release_track_record rows before distribution.
          </p>
        </div>
        {!showNew && (
          <button
            onClick={() => setShowNew(true)}
            className="flex items-center gap-1.5 px-3 py-2 bg-violet-600 hover:bg-violet-500 text-white text-xs font-medium rounded-lg"
          >
            <Plus size={14} /> New release
          </button>
        )}
      </div>

      {showNew && <CreateReleaseForm onCreated={() => setShowNew(false)} onCancel={() => setShowNew(false)} />}

      {isLoading && (
        <div className="flex items-center justify-center py-20 text-zinc-500 gap-2">
          <Loader2 size={18} className="animate-spin" /> Loading releases...
        </div>
      )}

      {isError && (
        <div className="bg-rose-500/10 border border-rose-500/30 rounded-xl p-4 text-rose-300 text-sm">
          Failed to load releases: {error?.message}
        </div>
      )}

      {!isLoading && releases.length === 0 && !showNew && (
        <div className="flex flex-col items-center justify-center py-20 text-center">
          <Package size={40} className="text-zinc-700 mb-3" />
          <div className="text-sm text-zinc-400 mb-1">No releases yet</div>
          <div className="text-xs text-zinc-600 max-w-sm">
            Create one above, then add qa_passed songs as tracks.
          </div>
        </div>
      )}

      <div className="space-y-2">
        {releases.map(release => (
          <ReleaseCard
            key={release.id}
            release={release}
            expanded={expandedId === release.id}
            onToggle={() => setExpandedId(expandedId === release.id ? null : release.id)}
          />
        ))}
      </div>
    </div>
  )
}
