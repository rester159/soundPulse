/**
 * Searchable multi-select picker over the genre taxonomy (959 entries).
 *
 * Used in the Blueprints manual editor to let the operator pick
 * primary genre + adjacent genres from the canonical list, instead of
 * having to remember dotted-id strings. Click a chip to remove. Type
 * to filter. Keyboard arrows + Enter to add.
 */
import { useMemo, useState, useRef, useEffect } from 'react'
import { X, Search, ChevronDown } from 'lucide-react'
import { useGenres } from '../hooks/useSoundPulse'

export default function GenreMultiPicker({
  value = [],
  onChange,
  placeholder = 'Search genres…',
  disabled = false,
  maxSuggestions = 50,
}) {
  const { data, isLoading } = useGenres({ flat: true })
  const allGenres = useMemo(() => {
    const list = data?.data?.data?.genres || data?.data?.genres || []
    // Sort by depth then id so roots come first, then subgenres alpha.
    return [...list].sort((a, b) => {
      if ((a.depth || 0) !== (b.depth || 0)) return (a.depth || 0) - (b.depth || 0)
      return (a.id || '').localeCompare(b.id || '')
    })
  }, [data])

  const [query, setQuery] = useState('')
  const [open, setOpen] = useState(false)
  const containerRef = useRef(null)

  // Close on outside click
  useEffect(() => {
    const onDoc = (e) => {
      if (containerRef.current && !containerRef.current.contains(e.target)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [])

  const selectedSet = useMemo(() => new Set(value || []), [value])

  const matches = useMemo(() => {
    if (!query.trim()) {
      // No query → show top of unselected list
      return allGenres.filter((g) => !selectedSet.has(g.id)).slice(0, maxSuggestions)
    }
    const q = query.trim().toLowerCase()
    return allGenres
      .filter((g) => !selectedSet.has(g.id))
      .filter((g) => g.id.toLowerCase().includes(q) || (g.name || '').toLowerCase().includes(q))
      .slice(0, maxSuggestions)
  }, [allGenres, query, selectedSet, maxSuggestions])

  const add = (id) => {
    if (selectedSet.has(id)) return
    onChange([...(value || []), id])
    setQuery('')
  }
  const remove = (id) => {
    onChange((value || []).filter((x) => x !== id))
  }
  const addCustom = () => {
    const trimmed = query.trim()
    if (!trimmed) return
    if (selectedSet.has(trimmed)) return
    onChange([...(value || []), trimmed])
    setQuery('')
  }

  return (
    <div ref={containerRef} className="relative">
      {/* Selected chips + input row */}
      <div
        className={`flex flex-wrap items-center gap-1.5 px-2 py-1.5 bg-zinc-950 border border-zinc-800 rounded text-sm min-h-[38px] ${
          disabled ? 'opacity-50 cursor-not-allowed' : 'focus-within:border-violet-500'
        }`}
        onClick={() => !disabled && setOpen(true)}
      >
        {(value || []).map((id, idx) => (
          <span
            key={id}
            className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[11px] font-mono ${
              idx === 0
                ? 'bg-violet-500/20 border border-violet-500/40 text-violet-200'
                : 'bg-zinc-800 border border-zinc-700 text-zinc-300'
            }`}
            title={idx === 0 ? 'Primary' : 'Additional'}
          >
            {id}
            <button
              type="button"
              onClick={(e) => { e.stopPropagation(); remove(id) }}
              className="hover:text-rose-300"
              disabled={disabled}
            >
              <X size={10} />
            </button>
          </span>
        ))}
        <input
          type="text"
          value={query}
          onChange={(e) => { setQuery(e.target.value); setOpen(true) }}
          onFocus={() => setOpen(true)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') { e.preventDefault(); if (matches[0]) add(matches[0].id); else if (query.trim()) addCustom() }
            if (e.key === 'Escape') setOpen(false)
            if (e.key === 'Backspace' && !query && (value || []).length > 0) {
              remove(value[value.length - 1])
            }
          }}
          placeholder={(value || []).length === 0 ? placeholder : ''}
          disabled={disabled}
          className="flex-1 min-w-[100px] bg-transparent outline-none text-zinc-100 placeholder-zinc-600 text-sm"
        />
        <ChevronDown
          size={14}
          className={`text-zinc-500 flex-shrink-0 transition-transform ${open ? 'rotate-180' : ''}`}
        />
      </div>

      {/* Dropdown suggestions */}
      {open && !disabled && (
        <div className="absolute z-20 mt-1 w-full max-h-72 overflow-y-auto bg-zinc-950 border border-zinc-800 rounded-lg shadow-2xl">
          {isLoading && (
            <div className="px-3 py-2 text-xs text-zinc-500">Loading genres…</div>
          )}
          {!isLoading && matches.length === 0 && query.trim() && (
            <button
              type="button"
              onClick={addCustom}
              className="w-full text-left px-3 py-2 text-xs text-violet-300 hover:bg-violet-500/10"
            >
              <Search size={11} className="inline mr-1" />
              Add custom genre <code className="font-mono">{query.trim()}</code>
            </button>
          )}
          {!isLoading && matches.length === 0 && !query.trim() && (
            <div className="px-3 py-2 text-xs text-zinc-500">All genres selected</div>
          )}
          {matches.map((g) => (
            <button
              key={g.id}
              type="button"
              onMouseDown={(e) => e.preventDefault()}
              onClick={() => add(g.id)}
              className="w-full text-left px-3 py-1.5 text-sm text-zinc-200 hover:bg-violet-500/10 hover:text-violet-200 flex items-center gap-2"
            >
              <span
                className="text-[10px] tabular-nums text-zinc-600 w-4"
                title={`depth ${g.depth || 0}`}
              >
                {g.depth || 0}
              </span>
              <code className="font-mono text-xs">{g.id}</code>
              {g.name && g.name.toLowerCase() !== g.id.toLowerCase() && (
                <span className="text-zinc-500 text-xs ml-auto">{g.name}</span>
              )}
            </button>
          ))}
        </div>
      )}
      {(value || []).length > 0 && (
        <div className="text-[10px] text-zinc-600 mt-1">
          {value.length === 1
            ? 'Single genre selected.'
            : (
              <>
                <span className="text-violet-400">First</span> stored as primary;
                {' '}rest as adjacent.
              </>
            )}
        </div>
      )}
    </div>
  )
}
