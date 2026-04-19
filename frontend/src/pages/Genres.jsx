/**
 * Genres top-level page (#20, #23).
 *
 * Two subtabs:
 *   - Taxonomy: full 950-row tree, indented by depth, with inline-edit
 *     of the 7 numeric dimensions + key_mood + edge_profile + era. Saves
 *     write to genre_traits with is_system_default=false so subsequent
 *     migration seeds don't clobber the override.
 *   - Structures: per-genre [Section: N bars] templates (lifted from
 *     Settings → Genre Structures into this top-level surface).
 *
 * Resolver semantics: a genre with no override inherits dimensions from
 * the closest ancestor that has them (walks the dotted chain in
 * `genre_traits_service.resolve_genre_traits`). The grid surfaces this
 * by showing inherited values in muted text and a small "(inherited)"
 * marker — actual override happens when the user edits.
 */
import { useMemo, useState } from 'react'
import {
  Loader2, ListTree, Music2, Search, Save, X, AlertCircle,
  CheckCircle2, ChevronRight, ChevronDown,
} from 'lucide-react'
import { useGenresTaxonomy, usePatchGenreTaxonomy } from '../hooks/useSoundPulse'
import GenreStructuresPanel from '../components/GenreStructuresPanel'

const DIMENSIONS = [
  { key: 'edginess',              label: 'Edge' },
  { key: 'meme_density',          label: 'Meme' },
  { key: 'earworm_demand',        label: 'Earworm' },
  { key: 'sonic_experimentation', label: 'SonicExp' },
  { key: 'lyrical_complexity',    label: 'LyrCplx' },
  { key: 'vocal_processing',      label: 'VocProc' },
]

const EDGE_OPTIONS = ['clean_edge', 'flirty_edge', 'savage_edge']
const KEY_MOOD_OPTIONS = ['major_default', 'minor_default', 'mixed']

function GenresTaxonomyPanel() {
  const { data, isLoading, isError, error } = useGenresTaxonomy()
  const patch = usePatchGenreTaxonomy()
  const [filter, setFilter] = useState('')
  const [collapsed, setCollapsed] = useState(() => new Set())  // root_categories collapsed
  const [editing, setEditing] = useState(null)
  const [savedFlash, setSavedFlash] = useState('')
  const [saveError, setSaveError] = useState(null)

  const rows = data?.data?.genres || data?.genres || []

  // Index: parent_id → children, for indented tree rendering.
  const childrenByParent = useMemo(() => {
    const map = new Map()
    for (const g of rows) {
      const p = g.parent_id || '__root__'
      if (!map.has(p)) map.set(p, [])
      map.get(p).push(g)
    }
    for (const arr of map.values()) {
      arr.sort((a, b) => (a.name || a.genre_id || '').localeCompare(b.name || b.genre_id || ''))
    }
    return map
  }, [rows])

  // Flatten the tree in display order — each row carries its own depth
  // for left-padding. We honor `filter` here so users can search across
  // the full 950 without manually expanding everything.
  const flattened = useMemo(() => {
    const out = []
    const f = filter.trim().toLowerCase()
    const matchesFilter = (g) => !f
      || (g.genre_id || '').toLowerCase().includes(f)
      || (g.name || '').toLowerCase().includes(f)

    const visit = (parentKey, depth) => {
      const kids = childrenByParent.get(parentKey) || []
      for (const g of kids) {
        // If filtering, include only matching rows + their ancestors
        // automatically (collected by walking down). To keep this fast
        // we just include any row whose subtree contains a match.
        const subtreeMatches = matchesFilter(g) || subtreeHasMatch(g.genre_id)
        if (!subtreeMatches) continue
        out.push({ ...g, _depth: depth })
        // Skip children if collapsed (only roots are collapsible for now)
        if (depth === 0 && collapsed.has(g.genre_id)) continue
        visit(g.genre_id, depth + 1)
      }
    }
    const subtreeHasMatch = (id) => {
      const kids = childrenByParent.get(id) || []
      for (const k of kids) {
        if (matchesFilter(k)) return true
        if (subtreeHasMatch(k.genre_id)) return true
      }
      return false
    }
    visit('__root__', 0)
    return out
  }, [childrenByParent, filter, collapsed])

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20 text-zinc-500">
        <Loader2 size={20} className="animate-spin mr-2" /> Loading taxonomy…
      </div>
    )
  }
  if (isError) {
    return (
      <div className="bg-rose-500/10 border border-rose-500/30 rounded p-3 text-xs text-rose-300">
        Failed to load taxonomy: {error?.message || 'unknown error'}
      </div>
    )
  }

  const toggleRoot = (id) => {
    setCollapsed((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const handleSave = async (genreId, body) => {
    setSaveError(null)
    try {
      await patch.mutateAsync({ genreId, body })
      setSavedFlash(genreId)
      setEditing(null)
      setTimeout(() => setSavedFlash(''), 1500)
    } catch (e) {
      setSaveError(e?.response?.data?.detail || e?.message || 'save failed')
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h2 className="text-lg font-bold text-zinc-100 mb-1">Taxonomy</h2>
          <p className="text-xs text-zinc-500 max-w-2xl">
            Full 959-genre taxonomy. The 7 numeric dimensions (0–100) drive
            edge rules, meme density, earworm pressure, and pop-culture filtering
            in the smart-prompt LLM. Genres without an override inherit from
            their closest ancestor — editing here writes a row and demotes
            <code className="text-zinc-400 mx-1">is_system_default</code> so
            subsequent migration seeds don't clobber.
          </p>
        </div>
        <div className="relative">
          <Search size={12} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-zinc-500" />
          <input
            type="text"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder="Search 959 genres…"
            className="pl-8 pr-3 py-1.5 bg-zinc-900 border border-zinc-800 rounded text-xs text-zinc-100 w-60"
          />
        </div>
      </div>

      {savedFlash && (
        <div className="flex items-center gap-2 text-emerald-300 text-xs bg-emerald-500/10 border border-emerald-500/30 rounded px-3 py-1.5">
          <CheckCircle2 size={12} /> Saved override for <code className="font-mono">{savedFlash}</code>
        </div>
      )}
      {saveError && (
        <div className="flex items-center gap-2 text-rose-300 text-xs bg-rose-500/10 border border-rose-500/30 rounded px-3 py-1.5">
          <AlertCircle size={12} /> {saveError}
        </div>
      )}

      <div className="border border-zinc-800 rounded-lg overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-xs min-w-[1100px]">
            <thead className="bg-zinc-900 text-[10px] uppercase tracking-wider text-zinc-500">
              <tr>
                <th className="text-left px-3 py-2 sticky left-0 bg-zinc-900 z-10">Genre</th>
                {DIMENSIONS.map((d) => (
                  <th key={d.key} className="text-right px-2 py-2 w-16">{d.label}</th>
                ))}
                <th className="text-left px-2 py-2 w-28">Tempo</th>
                <th className="text-left px-2 py-2 w-32">Edge profile</th>
                <th className="text-left px-2 py-2 w-28">Key mood</th>
                <th className="text-left px-2 py-2 w-24">Era</th>
                <th className="text-right px-3 py-2 w-20">Actions</th>
              </tr>
            </thead>
            <tbody>
              {flattened.map((g) => {
                const isOverride = !!g.has_override
                const isFlashed = savedFlash === g.genre_id
                const indent = `${g._depth * 16}px`
                const isCollapsibleRoot = g._depth === 0 && (childrenByParent.get(g.genre_id)?.length || 0) > 0
                return (
                  <tr
                    key={g.genre_id}
                    className={`border-t border-zinc-800 ${isFlashed ? 'bg-emerald-500/10' : 'hover:bg-zinc-900/40'}`}
                  >
                    <td className="px-3 py-1.5 sticky left-0 bg-zinc-950 z-10" style={{ paddingLeft: `calc(0.75rem + ${indent})` }}>
                      <div className="flex items-center gap-1">
                        {isCollapsibleRoot && (
                          <button
                            onClick={() => toggleRoot(g.genre_id)}
                            className="text-zinc-500 hover:text-zinc-300"
                          >
                            {collapsed.has(g.genre_id)
                              ? <ChevronRight size={11} />
                              : <ChevronDown size={11} />}
                          </button>
                        )}
                        <code className={`font-mono ${isOverride ? 'text-violet-300' : 'text-zinc-300'}`}>
                          {g.genre_id}
                        </code>
                        {isOverride && (
                          <span
                            title="Has CEO override"
                            className="text-[8px] uppercase tracking-wider text-violet-400 bg-violet-500/10 border border-violet-500/30 rounded px-1"
                          >
                            override
                          </span>
                        )}
                      </div>
                      {g.name && g.name !== g.genre_id && (
                        <div className="text-[10px] text-zinc-600">{g.name}</div>
                      )}
                    </td>
                    {DIMENSIONS.map((d) => (
                      <td key={d.key} className="px-2 py-1.5 text-right tabular-nums">
                        {g[d.key] != null ? (
                          <span className={isOverride ? 'text-zinc-200' : 'text-zinc-500 italic'}>
                            {g[d.key]}
                          </span>
                        ) : (
                          <span className="text-zinc-700">—</span>
                        )}
                      </td>
                    ))}
                    <td className="px-2 py-1.5 text-zinc-500">
                      {Array.isArray(g.tempo_range_bpm) && g.tempo_range_bpm.length === 2
                        ? `${g.tempo_range_bpm[0]}–${g.tempo_range_bpm[1]}`
                        : <span className="text-zinc-700">—</span>}
                    </td>
                    <td className="px-2 py-1.5 text-zinc-500 truncate">{g.default_edge_profile || <span className="text-zinc-700">—</span>}</td>
                    <td className="px-2 py-1.5 text-zinc-500 truncate">{g.key_mood || <span className="text-zinc-700">—</span>}</td>
                    <td className="px-2 py-1.5 text-zinc-500 truncate">{g.vocabulary_era || <span className="text-zinc-700">—</span>}</td>
                    <td className="px-3 py-1.5 text-right">
                      <button
                        onClick={() => setEditing(g)}
                        className="text-[11px] text-violet-300 hover:text-violet-200"
                      >
                        Edit
                      </button>
                    </td>
                  </tr>
                )
              })}
              {flattened.length === 0 && (
                <tr>
                  <td colSpan={DIMENSIONS.length + 5} className="text-center py-8 text-zinc-500 text-sm">
                    No genres match the filter.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {editing && (
        <EditTraitsModal
          row={editing}
          onClose={() => setEditing(null)}
          onSave={(body) => handleSave(editing.genre_id, body)}
          saving={patch.isPending}
        />
      )}
    </div>
  )
}

function EditTraitsModal({ row, onClose, onSave, saving }) {
  // Form state mirrors the row's overridable fields. Numeric fields
  // accept '' so the user can clear → falls back to inherited value
  // (we send null in that case).
  const [form, setForm] = useState({
    edginess: row.edginess ?? '',
    meme_density: row.meme_density ?? '',
    earworm_demand: row.earworm_demand ?? '',
    sonic_experimentation: row.sonic_experimentation ?? '',
    lyrical_complexity: row.lyrical_complexity ?? '',
    vocal_processing: row.vocal_processing ?? '',
    tempo_low: Array.isArray(row.tempo_range_bpm) ? row.tempo_range_bpm[0] ?? '' : '',
    tempo_high: Array.isArray(row.tempo_range_bpm) ? row.tempo_range_bpm[1] ?? '' : '',
    default_edge_profile: row.default_edge_profile || '',
    key_mood: row.key_mood || '',
    vocabulary_era: row.vocabulary_era || '',
    notes: row.notes || '',
  })

  const intField = (key, label) => (
    <label className="block">
      <div className="text-[10px] uppercase tracking-wider text-zinc-500 mb-1">{label} (0–100)</div>
      <input
        type="number"
        min="0"
        max="100"
        value={form[key]}
        onChange={(e) => setForm({ ...form, [key]: e.target.value })}
        className="w-full px-2 py-1.5 bg-zinc-950 border border-zinc-800 rounded text-sm text-zinc-100"
      />
    </label>
  )

  const handleSubmit = () => {
    const body = {}
    for (const k of ['edginess', 'meme_density', 'earworm_demand',
      'sonic_experimentation', 'lyrical_complexity', 'vocal_processing']) {
      if (form[k] === '' || form[k] == null) continue
      const n = parseInt(form[k], 10)
      if (!Number.isNaN(n)) body[k] = n
    }
    if (form.tempo_low !== '' && form.tempo_high !== '') {
      body.tempo_range_bpm = [parseInt(form.tempo_low, 10), parseInt(form.tempo_high, 10)]
    }
    if (form.default_edge_profile) body.default_edge_profile = form.default_edge_profile
    if (form.key_mood) body.key_mood = form.key_mood
    if (form.vocabulary_era.trim()) body.vocabulary_era = form.vocabulary_era.trim()
    if (form.notes.trim()) body.notes = form.notes.trim()
    onSave(body)
  }

  return (
    <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4 overflow-y-auto" onClick={onClose}>
      <div
        className="bg-zinc-950 border border-zinc-800 rounded-xl max-w-2xl w-full my-4"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-5 py-3 border-b border-zinc-800">
          <div>
            <h3 className="text-sm font-semibold text-zinc-100">Edit dimensions</h3>
            <code className="text-xs font-mono text-violet-300">{row.genre_id}</code>
            {row.name && <span className="text-[11px] text-zinc-500 ml-2">{row.name}</span>}
          </div>
          <button onClick={onClose} className="text-zinc-500 hover:text-zinc-200"><X size={16} /></button>
        </div>

        <div className="p-5 space-y-4 max-h-[70vh] overflow-y-auto">
          <p className="text-[11px] text-zinc-500 leading-relaxed">
            Saving creates an override row in <code className="text-zinc-400">genre_traits</code>.
            Blank fields keep the inherited values from the closest ancestor.
          </p>

          <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
            {intField('edginess', 'Edginess')}
            {intField('meme_density', 'Meme density')}
            {intField('earworm_demand', 'Earworm')}
            {intField('sonic_experimentation', 'Sonic exp')}
            {intField('lyrical_complexity', 'Lyric cplx')}
            {intField('vocal_processing', 'Vocal proc')}
          </div>

          <div className="grid grid-cols-2 gap-3">
            <label className="block">
              <div className="text-[10px] uppercase tracking-wider text-zinc-500 mb-1">Tempo low (BPM)</div>
              <input
                type="number"
                value={form.tempo_low}
                onChange={(e) => setForm({ ...form, tempo_low: e.target.value })}
                className="w-full px-2 py-1.5 bg-zinc-950 border border-zinc-800 rounded text-sm text-zinc-100"
              />
            </label>
            <label className="block">
              <div className="text-[10px] uppercase tracking-wider text-zinc-500 mb-1">Tempo high (BPM)</div>
              <input
                type="number"
                value={form.tempo_high}
                onChange={(e) => setForm({ ...form, tempo_high: e.target.value })}
                className="w-full px-2 py-1.5 bg-zinc-950 border border-zinc-800 rounded text-sm text-zinc-100"
              />
            </label>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
            <label className="block">
              <div className="text-[10px] uppercase tracking-wider text-zinc-500 mb-1">Default edge</div>
              <select
                value={form.default_edge_profile}
                onChange={(e) => setForm({ ...form, default_edge_profile: e.target.value })}
                className="w-full px-2 py-1.5 bg-zinc-950 border border-zinc-800 rounded text-sm text-zinc-100"
              >
                <option value="">(inherit)</option>
                {EDGE_OPTIONS.map((o) => <option key={o} value={o}>{o}</option>)}
              </select>
            </label>
            <label className="block">
              <div className="text-[10px] uppercase tracking-wider text-zinc-500 mb-1">Key mood</div>
              <select
                value={form.key_mood}
                onChange={(e) => setForm({ ...form, key_mood: e.target.value })}
                className="w-full px-2 py-1.5 bg-zinc-950 border border-zinc-800 rounded text-sm text-zinc-100"
              >
                <option value="">(inherit)</option>
                {KEY_MOOD_OPTIONS.map((o) => <option key={o} value={o}>{o}</option>)}
              </select>
            </label>
            <label className="block">
              <div className="text-[10px] uppercase tracking-wider text-zinc-500 mb-1">Vocabulary era</div>
              <input
                type="text"
                value={form.vocabulary_era}
                onChange={(e) => setForm({ ...form, vocabulary_era: e.target.value })}
                placeholder="gen_z / millennial / outlaw_classic / timeless"
                className="w-full px-2 py-1.5 bg-zinc-950 border border-zinc-800 rounded text-sm text-zinc-100"
              />
            </label>
          </div>

          <label className="block">
            <div className="text-[10px] uppercase tracking-wider text-zinc-500 mb-1">Notes</div>
            <textarea
              rows={3}
              value={form.notes}
              onChange={(e) => setForm({ ...form, notes: e.target.value })}
              placeholder="One-line rationale for this override (optional)"
              className="w-full px-2 py-1.5 bg-zinc-950 border border-zinc-800 rounded text-sm text-zinc-100"
            />
          </label>
        </div>

        <div className="flex justify-end gap-2 p-4 border-t border-zinc-800">
          <button onClick={onClose} className="px-3 py-1.5 text-xs text-zinc-400 hover:text-zinc-200">Cancel</button>
          <button
            onClick={handleSubmit}
            disabled={saving}
            className="flex items-center gap-1.5 px-4 py-1.5 bg-violet-600 hover:bg-violet-500 disabled:opacity-50 text-white text-xs font-medium rounded"
          >
            {saving ? <Loader2 size={12} className="animate-spin" /> : <Save size={12} />}
            Save override
          </button>
        </div>
      </div>
    </div>
  )
}

const SUBTABS = [
  { id: 'taxonomy',   label: 'Taxonomy',   icon: ListTree },
  { id: 'structures', label: 'Structures', icon: Music2 },
]

export default function Genres() {
  const [tab, setTab] = useState('taxonomy')

  return (
    <div className="p-4 md:p-6 max-w-7xl mx-auto">
      <div className="flex items-center gap-3 mb-4">
        <ListTree size={24} className="text-violet-400" />
        <h1 className="text-2xl font-bold text-zinc-100">Genres</h1>
      </div>

      <div className="flex gap-2 border-b border-zinc-800 mb-5">
        {SUBTABS.map((s) => {
          const Icon = s.icon
          const active = tab === s.id
          return (
            <button
              key={s.id}
              onClick={() => setTab(s.id)}
              className={`flex items-center gap-2 px-4 py-2 text-xs font-medium border-b-2 -mb-px transition-colors ${
                active
                  ? 'text-violet-300 border-violet-500'
                  : 'text-zinc-400 border-transparent hover:text-zinc-200'
              }`}
            >
              <Icon size={12} /> {s.label}
            </button>
          )
        })}
      </div>

      {tab === 'taxonomy' && <GenresTaxonomyPanel />}
      {tab === 'structures' && <GenreStructuresPanel />}
    </div>
  )
}
