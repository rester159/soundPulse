import { useState, useRef, useEffect, useCallback } from 'react'
import { Search, X } from 'lucide-react'
import { useSearch } from '../hooks/useSoundPulse'
import { formatScore } from '../utils/formatters'

const TYPE_COLORS = {
  track: { bg: 'bg-violet-500/15', text: 'text-violet-400' },
  artist: { bg: 'bg-emerald-500/15', text: 'text-emerald-400' },
  album: { bg: 'bg-amber-500/15', text: 'text-amber-400' },
}

export default function SearchBar({ onSelect, placeholder = 'Search tracks, artists...' }) {
  const [inputValue, setInputValue] = useState('')
  const [debouncedQuery, setDebouncedQuery] = useState('')
  const [isOpen, setIsOpen] = useState(false)
  const containerRef = useRef(null)
  const inputRef = useRef(null)
  const debounceTimer = useRef(null)

  const { data: searchResult, isLoading } = useSearch(debouncedQuery)
  const results = searchResult?.data?.data || searchResult?.data || []

  // Debounce input
  const handleInputChange = useCallback((e) => {
    const value = e.target.value
    setInputValue(value)

    if (debounceTimer.current) {
      clearTimeout(debounceTimer.current)
    }

    debounceTimer.current = setTimeout(() => {
      setDebouncedQuery(value.trim())
    }, 300)
  }, [])

  // Cleanup debounce timer
  useEffect(() => {
    return () => {
      if (debounceTimer.current) {
        clearTimeout(debounceTimer.current)
      }
    }
  }, [])

  // Open dropdown when we have results
  useEffect(() => {
    if (results.length > 0 && inputValue.length >= 2) {
      setIsOpen(true)
    }
  }, [results, inputValue])

  // Close on outside click
  useEffect(() => {
    function handleClickOutside(e) {
      if (containerRef.current && !containerRef.current.contains(e.target)) {
        setIsOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  // Keyboard handling
  function handleKeyDown(e) {
    if (e.key === 'Escape') {
      setIsOpen(false)
      inputRef.current?.blur()
    }
  }

  function handleResultClick(item) {
    onSelect?.(item)
    setIsOpen(false)
    setInputValue('')
    setDebouncedQuery('')
  }

  function handleClear() {
    setInputValue('')
    setDebouncedQuery('')
    setIsOpen(false)
    inputRef.current?.focus()
  }

  return (
    <div ref={containerRef} className="relative w-full max-w-xl">
      {/* Input */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500" />
        <input
          ref={inputRef}
          type="text"
          value={inputValue}
          onChange={handleInputChange}
          onFocus={() => {
            if (results.length > 0 && inputValue.length >= 2) {
              setIsOpen(true)
            }
          }}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          className="w-full pl-10 pr-9 py-2.5 bg-zinc-900 border border-zinc-800 rounded-lg text-sm text-zinc-100 placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-violet-500/40 focus:border-violet-500/50 transition-all duration-150"
        />
        {inputValue && (
          <button
            onClick={handleClear}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-zinc-500 hover:text-zinc-300 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        )}
      </div>

      {/* Dropdown results */}
      {isOpen && (inputValue.length >= 2) && (
        <div className="absolute z-50 top-full mt-1.5 w-full bg-zinc-900 border border-zinc-700 rounded-lg shadow-2xl overflow-hidden">
          {isLoading && (
            <div className="px-4 py-3 text-sm text-zinc-500">Searching...</div>
          )}

          {!isLoading && results.length === 0 && debouncedQuery.length >= 2 && (
            <div className="px-4 py-3 text-sm text-zinc-500">
              No results for "{debouncedQuery}"
            </div>
          )}

          {!isLoading &&
            results.length > 0 &&
            results.slice(0, 8).map((item, i) => {
              const entity = item.entity || item
              const scores = item.scores || {}
              const compositeScore = scores.composite ?? entity.composite_score ?? null
              const type = entity.type || entity.entity_type || 'track'
              const typeColors = TYPE_COLORS[type] || TYPE_COLORS.track

              return (
                <button
                  key={entity.id || entity.name || i}
                  onClick={() => handleResultClick(item)}
                  className="flex items-center gap-3 w-full px-4 py-2.5 text-left hover:bg-zinc-800/60 transition-colors duration-100 cursor-pointer"
                >
                  <div className="flex-1 min-w-0">
                    <div className="text-sm text-zinc-100 truncate">
                      {entity.name || entity.title || 'Unknown'}
                    </div>
                    {entity.artist && (
                      <div className="text-xs text-zinc-500 truncate">
                        {entity.artist}
                      </div>
                    )}
                  </div>

                  <span
                    className={`text-[10px] font-mono font-medium px-1.5 py-0.5 rounded ${typeColors.bg} ${typeColors.text}`}
                  >
                    {type}
                  </span>

                  {compositeScore !== null && (
                    <span className="font-mono text-xs text-zinc-400">
                      {formatScore(compositeScore)}
                    </span>
                  )}
                </button>
              )
            })}
        </div>
      )}
    </div>
  )
}
