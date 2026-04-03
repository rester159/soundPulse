import { useState } from 'react'
import { ChevronRight, ChevronDown, Folder, FolderOpen, Tag } from 'lucide-react'

function GenreNode({ node, depth = 0, selectedId, onSelect }) {
  const [expanded, setExpanded] = useState(false)
  const hasChildren = node.children && node.children.length > 0
  const isSelected = selectedId === (node.id || node.name)

  function handleToggle(e) {
    e.stopPropagation()
    if (hasChildren) {
      setExpanded((prev) => !prev)
    }
  }

  function handleSelect(e) {
    e.stopPropagation()
    onSelect?.(node)
    if (hasChildren && !expanded) {
      setExpanded(true)
    }
  }

  return (
    <div>
      <button
        onClick={handleSelect}
        className={`group flex items-center gap-2 w-full text-left px-2 py-1.5 rounded-md text-sm transition-colors duration-150 ${
          isSelected
            ? 'bg-violet-500/15 text-violet-400'
            : 'text-zinc-300 hover:bg-zinc-800/60 hover:text-zinc-100'
        }`}
        style={{ paddingLeft: `${depth * 16 + 8}px` }}
      >
        {/* Expand/collapse toggle */}
        {hasChildren ? (
          <span
            onClick={handleToggle}
            className="shrink-0 text-zinc-500 hover:text-zinc-300 transition-colors"
          >
            {expanded ? (
              <ChevronDown className="w-3.5 h-3.5" />
            ) : (
              <ChevronRight className="w-3.5 h-3.5" />
            )}
          </span>
        ) : (
          <span className="w-3.5 shrink-0" />
        )}

        {/* Icon */}
        {hasChildren ? (
          expanded ? (
            <FolderOpen className="w-3.5 h-3.5 text-violet-400/60 shrink-0" />
          ) : (
            <Folder className="w-3.5 h-3.5 text-zinc-500 shrink-0" />
          )
        ) : (
          <Tag className="w-3 h-3 text-zinc-600 shrink-0" />
        )}

        {/* Label */}
        <span className="truncate">{node.name || node.label || node.id}</span>

        {/* Count badge */}
        {node.count !== undefined && (
          <span className="ml-auto text-[10px] font-mono text-zinc-600">
            {node.count}
          </span>
        )}
      </button>

      {/* Children */}
      {hasChildren && expanded && (
        <div>
          {node.children.map((child) => (
            <GenreNode
              key={child.id || child.name}
              node={child}
              depth={depth + 1}
              selectedId={selectedId}
              onSelect={onSelect}
            />
          ))}
        </div>
      )}
    </div>
  )
}

export default function GenreTree({
  genres = [],
  selectedId,
  onSelect,
  isLoading = false,
}) {
  if (isLoading) {
    return (
      <div className="space-y-1.5 p-2">
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="flex items-center gap-2 px-2 py-1.5">
            <div className="h-3.5 w-3.5 bg-zinc-800 rounded skeleton" />
            <div
              className="h-4 bg-zinc-800 rounded skeleton"
              style={{ width: `${60 + Math.random() * 60}px` }}
            />
          </div>
        ))}
      </div>
    )
  }

  if (genres.length === 0) {
    return (
      <div className="px-3 py-6 text-center text-xs text-zinc-500">
        No genres available
      </div>
    )
  }

  return (
    <div className="space-y-0.5 p-1">
      {genres.map((genre) => (
        <GenreNode
          key={genre.id || genre.name}
          node={genre}
          depth={0}
          selectedId={selectedId}
          onSelect={onSelect}
        />
      ))}
    </div>
  )
}
