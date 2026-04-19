/**
 * Drag-and-drop reorderable, folderable sidebar nav.
 *
 * UX:
 *   - Drag any tab to a new spot, or onto a folder header to drop it inside.
 *   - Drag any folder to reorder among other folders / top-level tabs.
 *   - Click "+ Folder" to create a new folder at the bottom.
 *   - Click a folder's name to rename inline (Enter / blur to save, Esc to cancel).
 *   - Click the trash on a folder to delete it (children unfold to top level).
 *   - Click the chevron on a folder to collapse / expand.
 *
 * Layout persists to localStorage `soundpulse_nav_layout`. Newly-shipped
 * routes auto-append at the end so the user never loses track of new
 * pages; routes removed in code are dropped on next load.
 *
 * Implementation notes — HTML5 native DnD (no external library):
 *   - Each draggable row carries dataTransfer with a JSON descriptor
 *     `{ kind: 'item' | 'folder', id }`.
 *   - Each drop target accepts a drop and asks the layout helpers to
 *     splice the source into the target's position.
 *   - Folder headers also act as containers — dropping a tab onto a
 *     folder header puts it inside that folder.
 *   - We block recursive folder-into-folder (folders can only nest one
 *     level by design — see "Structure" below).
 *
 * Structure of the stored layout (a flat list of nodes):
 *   [
 *     { type: 'item',   id: '/dashboard' },
 *     { type: 'folder', id: 'folder_171...', name: 'Creation', collapsed: false,
 *       children: [
 *         { type: 'item', id: '/song-lab' },
 *         { type: 'item', id: '/blueprints' },
 *       ]
 *     },
 *     { type: 'item', id: '/songs' },
 *   ]
 *
 * `id` for items is the route path (matches NavLink `to`). For folders
 * it's a generated string. Folders cannot nest other folders.
 */
import { useEffect, useMemo, useRef, useState } from 'react'
import { NavLink } from 'react-router-dom'
import {
  ChevronDown, ChevronRight, Folder, FolderPlus, Trash2,
} from 'lucide-react'

const STORAGE_KEY = 'soundpulse_nav_layout'
const DRAG_MIME = 'application/x-soundpulse-nav'

function loadLayout(navItems) {
  let stored = null
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) stored = JSON.parse(raw)
  } catch {}
  const knownIds = new Set(navItems.map((i) => i.to))
  const layout = Array.isArray(stored) ? stored.filter(Boolean) : []
  const seen = new Set()
  const cleaned = []
  for (const node of layout) {
    if (node.type === 'item') {
      if (!knownIds.has(node.id) || seen.has(node.id)) continue
      seen.add(node.id)
      cleaned.push({ type: 'item', id: node.id })
    } else if (node.type === 'folder') {
      const kids = (node.children || []).filter((c) =>
        c?.type === 'item' && knownIds.has(c.id) && !seen.has(c.id)
      )
      kids.forEach((c) => seen.add(c.id))
      cleaned.push({
        type: 'folder',
        id: node.id || `folder_${Math.random().toString(36).slice(2, 10)}`,
        name: node.name || 'Folder',
        collapsed: !!node.collapsed,
        children: kids,
      })
    }
  }
  for (const item of navItems) {
    if (!seen.has(item.to)) {
      cleaned.push({ type: 'item', id: item.to })
      seen.add(item.to)
    }
  }
  return cleaned
}

function saveLayout(layout) {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(layout)) } catch {}
}

// Locate a node by id, anywhere in the tree. Returns
// { source: 'root' | folderId, index } or null if not found.
function locate(layout, id) {
  for (let i = 0; i < layout.length; i++) {
    const n = layout[i]
    if (n.id === id) return { source: 'root', index: i, node: n }
    if (n.type === 'folder') {
      const ci = (n.children || []).findIndex((c) => c.id === id)
      if (ci !== -1) return { source: n.id, index: ci, node: n.children[ci] }
    }
  }
  return null
}

// Pluck a node out of its current location, returning [newLayout, plucked].
function pluck(layout, id) {
  const next = JSON.parse(JSON.stringify(layout))
  for (let i = 0; i < next.length; i++) {
    const n = next[i]
    if (n.id === id) {
      const [taken] = next.splice(i, 1)
      return [next, taken]
    }
    if (n.type === 'folder') {
      const ci = (n.children || []).findIndex((c) => c.id === id)
      if (ci !== -1) {
        const [taken] = n.children.splice(ci, 1)
        return [next, taken]
      }
    }
  }
  return [layout, null]
}

// Drop `sourceId` either before/after `targetId` at the top level, or
// at the end of `targetFolderId`'s children list.
//   placement: 'before' | 'after' | 'inside'
function performDrop(layout, sourceId, targetId, placement) {
  if (sourceId === targetId) return layout
  const [stripped, taken] = pluck(layout, sourceId)
  if (!taken) return layout

  // Local helper — never lose `taken`. Any path that fails to find the
  // intended landing spot pushes it to the top of the layout instead of
  // dropping it on the floor.
  const safeFallback = () => { stripped.unshift(taken); return stripped }

  if (placement === 'inside') {
    if (taken.type === 'folder') return layout
    const folder = stripped.find((n) => n.type === 'folder' && n.id === targetId)
    if (!folder) return safeFallback()
    folder.children = folder.children || []
    folder.children.push(taken)
    return stripped
  }

  const tIdx = stripped.findIndex((n) => n.id === targetId)
  if (tIdx === -1) {
    for (const n of stripped) {
      if (n.type !== 'folder') continue
      const ci = (n.children || []).findIndex((c) => c.id === targetId)
      if (ci !== -1) {
        if (taken.type === 'folder') {
          const parentIdx = stripped.findIndex((x) => x.id === n.id)
          stripped.splice(parentIdx + (placement === 'after' ? 1 : 0), 0, taken)
          return stripped
        }
        const insertAt = placement === 'after' ? ci + 1 : ci
        n.children.splice(insertAt, 0, taken)
        return stripped
      }
    }
    return safeFallback()
  }
  const insertAt = placement === 'after' ? tIdx + 1 : tIdx
  stripped.splice(insertAt, 0, taken)
  return stripped
}

function addFolder(layout, name = 'New Folder') {
  return [...layout, {
    type: 'folder',
    id: `folder_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 6)}`,
    name,
    collapsed: false,
    children: [],
  }]
}

function deleteFolder(layout, folderId) {
  const next = []
  for (const n of layout) {
    if (n.type === 'folder' && n.id === folderId) {
      ;(n.children || []).forEach((c) => next.push(c))
    } else {
      next.push(n)
    }
  }
  return next
}

function renameFolder(layout, folderId, newName) {
  return layout.map((n) =>
    n.type === 'folder' && n.id === folderId ? { ...n, name: newName } : n
  )
}

function toggleFolderCollapsed(layout, folderId) {
  return layout.map((n) =>
    n.type === 'folder' && n.id === folderId ? { ...n, collapsed: !n.collapsed } : n
  )
}

export default function SideNav({ navItems, onItemClick }) {
  const [layout, setLayout] = useState(() => loadLayout(navItems))
  const [renamingFolderId, setRenamingFolderId] = useState(null)
  const [renameDraft, setRenameDraft] = useState('')
  // Drop-target hover state — id of the row being hovered + placement.
  const [dropHint, setDropHint] = useState(null)  // { id, placement }
  const dragSourceId = useRef(null)

  useEffect(() => { saveLayout(layout) }, [layout])

  // Sync newly-shipped routes / drop dead ones.
  useEffect(() => {
    setLayout((prev) => {
      const known = new Set(navItems.map((i) => i.to))
      const seen = new Set()
      prev.forEach((n) => {
        if (n.type === 'item') seen.add(n.id)
        else if (n.type === 'folder') (n.children || []).forEach((c) => seen.add(c.id))
      })
      const missing = navItems.filter((i) => !seen.has(i.to)).map((i) => ({ type: 'item', id: i.to }))
      const hasDead = prev.some((n) => n.type === 'item' && !known.has(n.id))
        || prev.some((n) => n.type === 'folder' && (n.children || []).some((c) => !known.has(c.id)))
      if (missing.length === 0 && !hasDead) return prev
      return loadLayout(navItems)
    })
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [navItems])

  const itemsById = useMemo(() => {
    const map = new Map()
    navItems.forEach((i) => map.set(i.to, i))
    return map
  }, [navItems])

  // ── DnD handlers ───────────────────────────────────────────────────────
  const handleDragStart = (id) => (e) => {
    dragSourceId.current = id
    try {
      e.dataTransfer.setData(DRAG_MIME, id)
      e.dataTransfer.effectAllowed = 'move'
    } catch {}
  }
  const handleDragEnd = () => {
    dragSourceId.current = null
    setDropHint(null)
  }
  // Compute placement (before/after) based on cursor's vertical position
  // within the row. Inside is only valid for folder targets.
  const computePlacement = (e, allowInside) => {
    const rect = e.currentTarget.getBoundingClientRect()
    const y = e.clientY - rect.top
    const h = rect.height
    if (allowInside && y > h * 0.25 && y < h * 0.75) return 'inside'
    return y < h / 2 ? 'before' : 'after'
  }
  const handleDragOver = (id, allowInside) => (e) => {
    e.preventDefault()
    e.dataTransfer.dropEffect = 'move'
    const placement = computePlacement(e, allowInside)
    if (!dropHint || dropHint.id !== id || dropHint.placement !== placement) {
      setDropHint({ id, placement })
    }
  }
  const handleDragLeave = (id) => () => {
    if (dropHint?.id === id) setDropHint(null)
  }
  const handleDrop = (id, allowInside) => (e) => {
    e.preventDefault()
    const sourceId = dragSourceId.current || (() => {
      try { return e.dataTransfer.getData(DRAG_MIME) } catch { return null }
    })()
    const placement = computePlacement(e, allowInside)
    if (sourceId && sourceId !== id) {
      setLayout((prev) => performDrop(prev, sourceId, id, placement))
    }
    setDropHint(null)
    dragSourceId.current = null
  }

  // Visual hint border for drop targets.
  const hintClass = (id) => {
    if (dropHint?.id !== id) return ''
    if (dropHint.placement === 'before') return 'border-t-2 border-t-violet-400'
    if (dropHint.placement === 'after') return 'border-b-2 border-b-violet-400'
    return 'ring-2 ring-violet-400/70'  // inside
  }

  const renderItem = (node, parent) => {
    const meta = itemsById.get(node.id)
    if (!meta) return null
    const Icon = meta.icon
    return (
      <div
        key={node.id}
        draggable
        onDragStart={handleDragStart(node.id)}
        onDragEnd={handleDragEnd}
        onDragOver={handleDragOver(node.id, false)}
        onDragLeave={handleDragLeave(node.id)}
        onDrop={handleDrop(node.id, false)}
        className={`rounded-lg ${hintClass(node.id)}`}
      >
        <NavLink
          to={meta.to}
          end={meta.to === '/'}
          onClick={() => onItemClick?.()}
          className={({ isActive }) =>
            `flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm font-medium transition-colors cursor-grab active:cursor-grabbing ${
              isActive
                ? 'bg-violet-500/10 text-violet-400'
                : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/50'
            } ${parent ? 'pl-2' : ''}`
          }
        >
          <Icon className="w-4 h-4 flex-shrink-0" />
          <span className="truncate">{meta.label}</span>
        </NavLink>
      </div>
    )
  }

  return (
    <>
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-zinc-800">
        <span className="text-[10px] uppercase tracking-wider text-zinc-500">Navigation</span>
        <div className="flex items-center gap-1">
          <button
            onClick={() => {
              if (confirm('Reset nav to default order? Your folders will be removed and every tab returns to the top level.')) {
                try { localStorage.removeItem(STORAGE_KEY) } catch {}
                setLayout(loadLayout(navItems))
              }
            }}
            className="text-[10px] text-zinc-500 hover:text-zinc-300 px-1.5 py-0.5 border border-zinc-800 rounded"
            title="Reset nav layout (recovers any tabs lost in folders)"
          >
            Reset
          </button>
          <button
            onClick={() => setLayout(addFolder(layout))}
            className="flex items-center gap-1 px-1.5 py-0.5 text-[10px] text-violet-300 hover:text-violet-200 border border-violet-500/30 rounded"
            title="Add folder"
          >
            <FolderPlus size={10} /> Folder
          </button>
        </div>
      </div>

      <nav className="flex-1 flex flex-col gap-0.5 px-2 py-3 overflow-y-auto">
        {layout.map((node) => {
          if (node.type === 'item') return renderItem(node, null)
          // Folder
          const f = node
          const isRenaming = renamingFolderId === f.id
          return (
            <div
              key={f.id}
              draggable={!isRenaming}
              onDragStart={handleDragStart(f.id)}
              onDragEnd={handleDragEnd}
              className="mt-1"
            >
              <div
                onDragOver={handleDragOver(f.id, true)}
                onDragLeave={handleDragLeave(f.id)}
                onDrop={handleDrop(f.id, true)}
                className={`flex items-center gap-1 px-2 py-1 rounded ${hintClass(f.id)}`}
              >
                <button
                  onClick={() => setLayout(toggleFolderCollapsed(layout, f.id))}
                  className="p-0.5 text-zinc-500 hover:text-zinc-300"
                  title={f.collapsed ? 'Expand' : 'Collapse'}
                >
                  {f.collapsed ? <ChevronRight size={11} /> : <ChevronDown size={11} />}
                </button>
                <Folder size={12} className="text-zinc-500 cursor-grab" />
                {isRenaming ? (
                  <input
                    autoFocus
                    value={renameDraft}
                    onChange={(e) => setRenameDraft(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') {
                        setLayout(renameFolder(layout, f.id, renameDraft.trim() || f.name))
                        setRenamingFolderId(null)
                      } else if (e.key === 'Escape') {
                        setRenamingFolderId(null)
                      }
                    }}
                    onBlur={() => {
                      setLayout(renameFolder(layout, f.id, renameDraft.trim() || f.name))
                      setRenamingFolderId(null)
                    }}
                    className="flex-1 px-1 py-0.5 bg-zinc-900 border border-zinc-700 rounded text-xs text-zinc-100"
                  />
                ) : (
                  <button
                    onClick={() => { setRenamingFolderId(f.id); setRenameDraft(f.name) }}
                    title="Click to rename"
                    className="flex-1 text-left text-[11px] uppercase tracking-wider text-zinc-400 font-semibold truncate hover:text-zinc-200 cursor-text"
                  >
                    {f.name}
                  </button>
                )}
                <button
                  onClick={() => {
                    if (confirm(`Delete folder "${f.name}"? Tabs inside will move back to the top level.`)) {
                      setLayout(deleteFolder(layout, f.id))
                    }
                  }}
                  className="p-0.5 text-zinc-600 hover:text-rose-400 opacity-0 group-hover:opacity-100"
                  title="Delete folder (tabs inside come out)"
                  style={{ opacity: 1 }}
                ><Trash2 size={10} /></button>
              </div>
              {!f.collapsed && (
                <div className="ml-3 mt-0.5 space-y-0.5 border-l border-zinc-800/60 pl-1">
                  {(f.children || []).map((child) => renderItem(child, f.id))}
                  {(f.children || []).length === 0 && (
                    <div
                      onDragOver={handleDragOver(f.id, true)}
                      onDrop={handleDrop(f.id, true)}
                      className={`text-[10px] text-zinc-600 italic px-2 py-1 rounded ${dropHint?.id === f.id && dropHint.placement === 'inside' ? 'ring-2 ring-violet-400/70' : ''}`}
                    >
                      Drop a tab here…
                    </div>
                  )}
                </div>
              )}
            </div>
          )
        })}
      </nav>
    </>
  )
}
