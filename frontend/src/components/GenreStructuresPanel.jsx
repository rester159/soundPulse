/**
 * Genre Structures panel (#20).
 *
 * Lifted out of Settings → "Genre Structures" subtab when the new
 * top-level "Genres" page was introduced. Pure UI for the
 * `genre_structures` table (per-genre [Section: N bars] templates that
 * the orchestrator prepends to every Suno prompt).
 *
 * The component is identical to the prior subtab implementation —
 * extracted so both the new Genres page and (transitionally) any other
 * caller can mount it without duplicating ~200 lines.
 */
import { useState } from 'react'
import { Loader2, Plus, X, AlertCircle, Save } from 'lucide-react'
import { useQueryClient } from '@tanstack/react-query'
import {
  useGenreStructures, useUpdateGenreStructure, useDeleteGenreStructure,
} from '../hooks/useSoundPulse'
import GenreStructureEditor, { structureChain } from './GenreStructureEditor'

export default function GenreStructuresPanel() {
  const { data, isLoading, refetch } = useGenreStructures()
  const update = useUpdateGenreStructure()
  const remove = useDeleteGenreStructure()
  const qc = useQueryClient()
  const [editing, setEditing] = useState(null)
  const [savedFlash, setSavedFlash] = useState('')

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20 text-zinc-500">
        <Loader2 size={20} className="animate-spin mr-2" /> Loading genre structures...
      </div>
    )
  }

  const items = data?.data?.items || data?.items || []

  const handleSave = async () => {
    if (!editing) return
    await update.mutateAsync({
      primaryGenre: editing.primary_genre,
      structure: editing.structure,
      notes: editing.notes,
      updatedBy: 'genres_ui',
    })
    setSavedFlash(editing.primary_genre)
    qc.invalidateQueries({ queryKey: ['admin', 'genre-structures'] })
    refetch()
    setEditing(null)
    setTimeout(() => setSavedFlash(''), 2000)
  }

  const handleDelete = async (primaryGenre) => {
    const confirmMsg = `Delete genre_structure for ${primaryGenre}? Any artist whose primary_genre matches will fall back to pop.`
    if (!confirm(confirmMsg)) return
    await remove.mutateAsync({ primaryGenre })
    qc.invalidateQueries({ queryKey: ['admin', 'genre-structures'] })
    refetch()
  }

  const handleNew = () => {
    setEditing({
      primary_genre: '',
      structure: [
        { name: 'Intro', bars: 8, vocals: false },
        { name: 'Verse', bars: 16, vocals: true },
        { name: 'Chorus', bars: 8, vocals: true },
        { name: 'Outro', bars: 4, vocals: false },
      ],
      notes: '',
      isNew: true,
    })
  }

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-lg font-bold text-zinc-100 mb-1">Genre Structures</h2>
          <p className="text-xs text-zinc-500 max-w-2xl">
            Per-genre song-form skeletons prepended to every Suno prompt as a
            <code className="text-zinc-400 mx-1">[Section: N bars]</code> block.
            Editing a row changes the structure injected for every song generated
            under that genre. Per-artist overrides (Artists page) take precedence
            when set.
          </p>
        </div>
        <button
          onClick={handleNew}
          className="flex items-center gap-1.5 px-3 py-2 bg-violet-600 hover:bg-violet-700 text-white text-xs font-medium rounded-lg"
        >
          <Plus size={14} /> New genre
        </button>
      </div>

      <div className="border border-zinc-800 rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-zinc-900 text-[10px] uppercase tracking-wider text-zinc-500">
            <tr>
              <th className="text-left px-3 py-2">Primary genre</th>
              <th className="text-left px-3 py-2">Section chain</th>
              <th className="text-right px-3 py-2 w-20">Sections</th>
              <th className="text-right px-3 py-2 w-20">Bars</th>
              <th className="text-right px-3 py-2 w-32">Actions</th>
            </tr>
          </thead>
          <tbody>
            {items.map((row) => {
              const totalBars = (row.structure || []).reduce((s, x) => s + (x.bars || 0), 0)
              const isFlashed = savedFlash === row.primary_genre
              return (
                <tr
                  key={row.primary_genre}
                  className={`border-t border-zinc-800 ${isFlashed ? 'bg-emerald-500/10' : 'hover:bg-zinc-900/50'}`}
                >
                  <td className="px-3 py-2 font-mono text-violet-300">{row.primary_genre}</td>
                  <td className="px-3 py-2 text-xs text-zinc-400 truncate max-w-md" title={structureChain(row.structure)}>
                    {structureChain(row.structure)}
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums text-zinc-400">{(row.structure || []).length}</td>
                  <td className="px-3 py-2 text-right tabular-nums text-zinc-400">{totalBars}</td>
                  <td className="px-3 py-2 text-right">
                    <button
                      onClick={() => setEditing({
                        primary_genre: row.primary_genre,
                        structure: row.structure || [],
                        notes: row.notes || '',
                        isNew: false,
                      })}
                      className="text-xs text-violet-300 hover:text-violet-200 mr-2"
                    >
                      Edit
                    </button>
                    <button
                      onClick={() => handleDelete(row.primary_genre)}
                      className="text-xs text-zinc-500 hover:text-rose-300"
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
        {items.length === 0 && (
          <div className="text-center py-8 text-zinc-500 text-sm">
            No genre structures seeded. Run alembic migration 033, or click New genre above.
          </div>
        )}
      </div>

      {editing && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70" onClick={() => setEditing(null)}>
          <div
            className="bg-zinc-950 border border-zinc-800 rounded-xl p-6 max-w-3xl w-full max-h-[85vh] overflow-y-auto"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-bold text-zinc-100">
                {editing.isNew ? 'New genre structure' : `Edit ${editing.primary_genre}`}
              </h3>
              <button onClick={() => setEditing(null)} className="text-zinc-500 hover:text-zinc-200">
                <X size={20} />
              </button>
            </div>

            <div className="space-y-4">
              {editing.isNew && (
                <div>
                  <label className="text-xs text-zinc-500 block mb-1">
                    Primary genre key (canonical taxonomy ID, e.g. <code>pop.k-pop</code>)
                  </label>
                  <input
                    type="text"
                    value={editing.primary_genre}
                    onChange={(e) => setEditing({ ...editing, primary_genre: e.target.value })}
                    className="w-full bg-zinc-900 border border-zinc-800 rounded px-3 py-2 text-sm text-zinc-100 font-mono"
                  />
                </div>
              )}

              <div>
                <label className="text-xs text-zinc-500 block mb-1">Notes (1-line rationale)</label>
                <input
                  type="text"
                  value={editing.notes || ''}
                  onChange={(e) => setEditing({ ...editing, notes: e.target.value })}
                  className="w-full bg-zinc-900 border border-zinc-800 rounded px-3 py-2 text-sm text-zinc-300"
                />
              </div>

              <div>
                <label className="text-xs text-zinc-500 block mb-2">Sections</label>
                <GenreStructureEditor
                  value={editing.structure}
                  onChange={(structure) => setEditing({ ...editing, structure })}
                  disabled={update.isPending}
                />
              </div>

              {update.isError && (
                <div className="flex items-center gap-2 text-rose-300 text-xs bg-rose-500/10 border border-rose-500/30 rounded px-3 py-2">
                  <AlertCircle size={14} />
                  Save failed: {update.error?.response?.data?.detail || update.error?.message || 'unknown error'}
                </div>
              )}

              <div className="flex gap-2 justify-end pt-2 border-t border-zinc-800">
                <button
                  onClick={() => setEditing(null)}
                  disabled={update.isPending}
                  className="px-4 py-2 text-sm text-zinc-400 hover:text-zinc-200 disabled:opacity-50"
                >
                  Cancel
                </button>
                <button
                  onClick={handleSave}
                  disabled={update.isPending || !editing.primary_genre || (editing.structure || []).length === 0}
                  className="flex items-center gap-2 px-4 py-2 bg-violet-600 hover:bg-violet-700 disabled:opacity-50 text-white rounded-lg text-sm font-medium"
                >
                  {update.isPending ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
                  Save
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
