/**
 * Reusable structure editor for {name, bars, vocals}[] (task #109 Phase 4).
 *
 * Used in two places:
 *   - Settings → Genre Structures subtab (one editor per genre row)
 *   - Artists page → "Song Structure" section (per-artist override template)
 *
 * Pure controlled component: parent owns state, passes value + onChange.
 * Validation matches the API/service contract: every section needs a
 * non-empty name, bars > 0, vocals bool. Reorder via up/down arrows.
 */
import { ArrowDown, ArrowUp, Plus, Trash2 } from 'lucide-react'

export default function GenreStructureEditor({ value, onChange, disabled = false }) {
  const sections = Array.isArray(value) ? value : []

  const update = (idx, patch) => {
    const next = sections.map((s, i) => (i === idx ? { ...s, ...patch } : s))
    onChange(next)
  }

  const remove = (idx) => onChange(sections.filter((_, i) => i !== idx))

  const move = (idx, dir) => {
    const target = idx + dir
    if (target < 0 || target >= sections.length) return
    const next = [...sections]
    ;[next[idx], next[target]] = [next[target], next[idx]]
    onChange(next)
  }

  const add = () => {
    onChange([
      ...sections,
      { name: 'Section', bars: 8, vocals: true },
    ])
  }

  // Compute total bars + section count for the live summary.
  const totalBars = sections.reduce((sum, s) => sum + (parseInt(s.bars, 10) || 0), 0)

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <div className="text-xs text-zinc-500">
          {sections.length} section{sections.length === 1 ? '' : 's'} · {totalBars} bars total
        </div>
        <button
          type="button"
          onClick={add}
          disabled={disabled}
          className="flex items-center gap-1 px-2 py-1 text-xs text-violet-300 hover:text-violet-200 disabled:opacity-40"
        >
          <Plus size={12} /> Add section
        </button>
      </div>

      {sections.length === 0 && (
        <div className="text-xs text-zinc-600 italic py-3 text-center border border-dashed border-zinc-800 rounded">
          No sections — click "Add section" to start
        </div>
      )}

      <div className="space-y-1.5">
        {sections.map((s, idx) => (
          <div
            key={idx}
            className="grid grid-cols-[auto_1fr_80px_auto_auto] gap-2 items-center bg-zinc-900 border border-zinc-800 rounded px-2 py-1.5"
          >
            <span className="text-[10px] text-zinc-600 tabular-nums w-5 text-right">
              {idx + 1}.
            </span>
            <input
              type="text"
              value={s.name || ''}
              onChange={(e) => update(idx, { name: e.target.value })}
              disabled={disabled}
              placeholder="Section name"
              className="bg-zinc-950 border border-zinc-800 rounded px-2 py-1 text-sm text-zinc-100 disabled:opacity-50"
            />
            <input
              type="number"
              min="1"
              value={s.bars ?? ''}
              onChange={(e) => update(idx, { bars: parseInt(e.target.value, 10) || 1 })}
              disabled={disabled}
              className="bg-zinc-950 border border-zinc-800 rounded px-2 py-1 text-sm text-zinc-100 tabular-nums disabled:opacity-50"
              title="Bars"
            />
            <label className="flex items-center gap-1 text-xs text-zinc-400 px-2 select-none cursor-pointer">
              <input
                type="checkbox"
                checked={Boolean(s.vocals)}
                onChange={(e) => update(idx, { vocals: e.target.checked })}
                disabled={disabled}
              />
              vocals
            </label>
            <div className="flex items-center gap-0.5">
              <button
                type="button"
                onClick={() => move(idx, -1)}
                disabled={disabled || idx === 0}
                className="p-1 text-zinc-500 hover:text-zinc-200 disabled:opacity-30"
                title="Move up"
              >
                <ArrowUp size={12} />
              </button>
              <button
                type="button"
                onClick={() => move(idx, 1)}
                disabled={disabled || idx === sections.length - 1}
                className="p-1 text-zinc-500 hover:text-zinc-200 disabled:opacity-30"
                title="Move down"
              >
                <ArrowDown size={12} />
              </button>
              <button
                type="button"
                onClick={() => remove(idx)}
                disabled={disabled}
                className="p-1 text-zinc-500 hover:text-rose-300 disabled:opacity-30"
                title="Remove"
              >
                <Trash2 size={12} />
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

/**
 * Read-only one-line summary of a structure for table cells:
 *   Intro 8 → Verse 16 → Chorus 8 → ...
 */
export function structureChain(sections) {
  if (!Array.isArray(sections) || sections.length === 0) return '(empty)'
  return sections.map((s) => `${s.name} ${s.bars}`).join(' → ')
}
