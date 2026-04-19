/**
 * Reorderable + folderable left sidebar nav.
 *
 * The user can:
 *   - Reorder tabs up/down in edit mode
 *   - Create folders to group related tabs
 *   - Move tabs into / out of folders
 *   - Rename folders, delete folders (deleting just unfolds them)
 *
 * Layout is persisted to localStorage (`soundpulse_nav_layout`) — no
 * backend involved. New nav items added in code that aren't yet in the
 * stored layout get auto-appended to the end on next render so users
 * never lose track of newly-shipped pages.
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
 * it's a generated UUID-ish string. Children lists are themselves flat;
 * folders cannot nest folders (one level only — keeps reordering simple).
 */
import { useEffect, useMemo, useState } from 'react'
import { NavLink } from 'react-router-dom'
import {
  ChevronDown, ChevronUp, ChevronRight, Folder, FolderPlus,
  Pencil, Trash2, Check, X,
} from 'lucide-react'

const STORAGE_KEY = 'soundpulse_nav_layout'

function loadLayout(navItems) {
  // Read from localStorage if present + valid; else default = each item
  // top-level in the canonical NAV_ITEMS order.
  let stored = null
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) stored = JSON.parse(raw)
  } catch {}
  const knownIds = new Set(navItems.map((i) => i.to))

  const layout = Array.isArray(stored) ? stored.filter(Boolean) : []

  // Drop any nodes that point to routes the codebase no longer ships
  // (avoids dead nav entries when a tab is removed).
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
  // Append any item that's in NAV_ITEMS but not yet in the stored layout
  // — handles newly-shipped routes.
  for (const item of navItems) {
    if (!seen.has(item.to)) {
      cleaned.push({ type: 'item', id: item.to })
      seen.add(item.to)
    }
  }
  return cleaned
}

function saveLayout(layout) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(layout))
  } catch {}
}

// Walk the layout flat (top-level + folder children) and return an
// ordered list of {locator, item} where locator describes where the
// item lives so move/delete operations know what to act on.
function flatten(layout) {
  const out = []
  layout.forEach((node, idx) => {
    if (node.type === 'item') {
      out.push({ kind: 'item', id: node.id, parent: 'root', topIdx: idx })
    } else if (node.type === 'folder') {
      out.push({ kind: 'folder', id: node.id, name: node.name, collapsed: node.collapsed, topIdx: idx, childCount: (node.children || []).length })
      ;(node.children || []).forEach((c, ci) => {
        out.push({ kind: 'item', id: c.id, parent: node.id, topIdx: idx, childIdx: ci })
      })
    }
  })
  return out
}

function moveItemUp(layout, itemId) {
  const next = JSON.parse(JSON.stringify(layout))
  for (let i = 0; i < next.length; i++) {
    const node = next[i]
    if (node.type === 'item' && node.id === itemId) {
      if (i > 0) {
        ;[next[i - 1], next[i]] = [next[i], next[i - 1]]
      }
      return next
    }
    if (node.type === 'folder') {
      const ci = (node.children || []).findIndex((c) => c.id === itemId)
      if (ci !== -1) {
        if (ci > 0) {
          ;[node.children[ci - 1], node.children[ci]] = [node.children[ci], node.children[ci - 1]]
        } else {
          // Promote out of folder, just before the folder
          node.children.splice(ci, 1)
          next.splice(i, 0, { type: 'item', id: itemId })
        }
        return next
      }
    }
  }
  return next
}

function moveItemDown(layout, itemId) {
  const next = JSON.parse(JSON.stringify(layout))
  for (let i = 0; i < next.length; i++) {
    const node = next[i]
    if (node.type === 'item' && node.id === itemId) {
      if (i < next.length - 1) {
        ;[next[i + 1], next[i]] = [next[i], next[i + 1]]
      }
      return next
    }
    if (node.type === 'folder') {
      const ci = (node.children || []).findIndex((c) => c.id === itemId)
      if (ci !== -1) {
        if (ci < (node.children.length - 1)) {
          ;[node.children[ci + 1], node.children[ci]] = [node.children[ci], node.children[ci + 1]]
        } else {
          // Promote out, just after the folder
          node.children.splice(ci, 1)
          next.splice(i + 1, 0, { type: 'item', id: itemId })
        }
        return next
      }
    }
  }
  return next
}

function moveFolderUp(layout, folderId) {
  const next = [...layout]
  const idx = next.findIndex((n) => n.type === 'folder' && n.id === folderId)
  if (idx > 0) [next[idx - 1], next[idx]] = [next[idx], next[idx - 1]]
  return next
}
function moveFolderDown(layout, folderId) {
  const next = [...layout]
  const idx = next.findIndex((n) => n.type === 'folder' && n.id === folderId)
  if (idx !== -1 && idx < next.length - 1) [next[idx + 1], next[idx]] = [next[idx], next[idx + 1]]
  return next
}

function moveItemToFolder(layout, itemId, folderId) {
  // Remove from current location, push into folder.children
  const next = JSON.parse(JSON.stringify(layout))
  // First, locate + remove
  let plucked = null
  for (let i = 0; i < next.length; i++) {
    const node = next[i]
    if (node.type === 'item' && node.id === itemId) {
      plucked = next.splice(i, 1)[0]
      break
    }
    if (node.type === 'folder') {
      const ci = (node.children || []).findIndex((c) => c.id === itemId)
      if (ci !== -1) {
        plucked = node.children.splice(ci, 1)[0]
        break
      }
    }
  }
  if (!plucked) return layout
  // Insert
  if (folderId === 'root') {
    next.push(plucked)
  } else {
    const folder = next.find((n) => n.type === 'folder' && n.id === folderId)
    if (folder) {
      folder.children = folder.children || []
      folder.children.push(plucked)
    }
  }
  return next
}

function addFolder(layout, name = 'New Folder') {
  return [...layout, {
    type: 'folder',
    id: `folder_${Math.random().toString(36).slice(2, 10)}`,
    name,
    collapsed: false,
    children: [],
  }]
}

function deleteFolder(layout, folderId) {
  const next = []
  for (const node of layout) {
    if (node.type === 'folder' && node.id === folderId) {
      // Promote children back to top level
      ;(node.children || []).forEach((c) => next.push(c))
    } else {
      next.push(node)
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
  const [editMode, setEditMode] = useState(false)
  const [renamingFolderId, setRenamingFolderId] = useState(null)
  const [renameDraft, setRenameDraft] = useState('')

  useEffect(() => { saveLayout(layout) }, [layout])

  // If NAV_ITEMS gains a route after load, sync it in.
  useEffect(() => {
    setLayout((prev) => {
      const known = new Set(navItems.map((i) => i.to))
      const seen = new Set()
      prev.forEach((n) => {
        if (n.type === 'item') seen.add(n.id)
        else if (n.type === 'folder') (n.children || []).forEach((c) => seen.add(c.id))
      })
      const missing = navItems.filter((i) => !seen.has(i.to)).map((i) => ({ type: 'item', id: i.to }))
      if (missing.length === 0) {
        // Also drop dead routes to keep the saved layout clean
        const hasDead = prev.some((n) => n.type === 'item' && !known.has(n.id))
          || prev.some((n) => n.type === 'folder' && (n.children || []).some((c) => !known.has(c.id)))
        if (!hasDead) return prev
        return loadLayout(navItems)
      }
      return [...prev, ...missing]
    })
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [navItems])

  const itemsById = useMemo(() => {
    const map = new Map()
    navItems.forEach((i) => map.set(i.to, i))
    return map
  }, [navItems])

  const folders = useMemo(
    () => layout.filter((n) => n.type === 'folder'),
    [layout]
  )

  const renderItem = (node, parent) => {
    const meta = itemsById.get(node.id)
    if (!meta) return null
    const Icon = meta.icon
    return (
      <div key={node.id} className="flex items-center gap-1 group">
        {editMode && (
          <div className="flex flex-col -mr-1">
            <button
              onClick={() => setLayout(moveItemUp(layout, node.id))}
              className="p-0.5 text-zinc-600 hover:text-zinc-300"
              title="Move up"
            ><ChevronUp size={10} /></button>
            <button
              onClick={() => setLayout(moveItemDown(layout, node.id))}
              className="p-0.5 text-zinc-600 hover:text-zinc-300"
              title="Move down"
            ><ChevronDown size={10} /></button>
          </div>
        )}
        <NavLink
          to={meta.to}
          end={meta.to === '/'}
          onClick={(e) => {
            // Suppress navigation while editing — prevents accidental
            // route changes when the user is reorganizing.
            if (editMode) { e.preventDefault(); return }
            onItemClick?.()
          }}
          className={({ isActive }) =>
            `flex-1 flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
              isActive && !editMode
                ? 'bg-violet-500/10 text-violet-400'
                : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/50'
            } ${parent ? 'pl-2' : ''}`
          }
        >
          <Icon className="w-4 h-4 flex-shrink-0" />
          <span className="truncate">{meta.label}</span>
        </NavLink>
        {editMode && (
          <select
            value={parent || 'root'}
            onChange={(e) => setLayout(moveItemToFolder(layout, node.id, e.target.value))}
            title="Move into…"
            className="text-[10px] bg-zinc-900 border border-zinc-800 rounded px-1 py-0.5 text-zinc-400 max-w-16 truncate"
          >
            <option value="root">— top —</option>
            {folders.map((f) => (
              <option key={f.id} value={f.id}>{f.name}</option>
            ))}
          </select>
        )}
      </div>
    )
  }

  return (
    <>
      {/* Edit-mode header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-zinc-800">
        <span className="text-[10px] uppercase tracking-wider text-zinc-500">Navigation</span>
        <div className="flex items-center gap-1">
          {editMode && (
            <button
              onClick={() => setLayout(addFolder(layout))}
              className="flex items-center gap-1 px-1.5 py-0.5 text-[10px] text-violet-300 hover:text-violet-200 border border-violet-500/30 rounded"
              title="Add folder"
            >
              <FolderPlus size={10} /> Folder
            </button>
          )}
          <button
            onClick={() => setEditMode((v) => !v)}
            className={`px-1.5 py-0.5 text-[10px] rounded border ${
              editMode
                ? 'bg-violet-600/30 text-violet-100 border-violet-500/50'
                : 'text-zinc-500 hover:text-zinc-300 border-zinc-800 hover:border-zinc-700'
            }`}
            title={editMode ? 'Done' : 'Edit nav'}
          >
            {editMode ? 'Done' : 'Edit'}
          </button>
        </div>
      </div>

      <nav className="flex-1 flex flex-col gap-0.5 px-2 py-3 overflow-y-auto">
        {layout.map((node, idx) => {
          if (node.type === 'item') {
            return renderItem(node, null)
          }
          // Folder
          const f = node
          const isRenaming = renamingFolderId === f.id
          return (
            <div key={f.id} className="mt-1">
              <div className="flex items-center gap-1 px-2">
                <button
                  onClick={() => setLayout(toggleFolderCollapsed(layout, f.id))}
                  className="p-0.5 text-zinc-500 hover:text-zinc-300"
                  title={f.collapsed ? 'Expand' : 'Collapse'}
                >
                  {f.collapsed ? <ChevronRight size={11} /> : <ChevronDown size={11} />}
                </button>
                <Folder size={12} className="text-zinc-500" />
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
                  <span className="flex-1 text-[11px] uppercase tracking-wider text-zinc-400 font-semibold truncate">
                    {f.name}
                  </span>
                )}
                {editMode && !isRenaming && (
                  <div className="flex items-center gap-0.5">
                    <button
                      onClick={() => setLayout(moveFolderUp(layout, f.id))}
                      className="p-0.5 text-zinc-600 hover:text-zinc-300" title="Move folder up"
                    ><ChevronUp size={10} /></button>
                    <button
                      onClick={() => setLayout(moveFolderDown(layout, f.id))}
                      className="p-0.5 text-zinc-600 hover:text-zinc-300" title="Move folder down"
                    ><ChevronDown size={10} /></button>
                    <button
                      onClick={() => { setRenamingFolderId(f.id); setRenameDraft(f.name) }}
                      className="p-0.5 text-zinc-600 hover:text-violet-300" title="Rename folder"
                    ><Pencil size={10} /></button>
                    <button
                      onClick={() => {
                        if (confirm(`Delete folder "${f.name}"? Tabs inside will move back to the top level.`)) {
                          setLayout(deleteFolder(layout, f.id))
                        }
                      }}
                      className="p-0.5 text-zinc-600 hover:text-rose-400" title="Delete folder (tabs inside come out)"
                    ><Trash2 size={10} /></button>
                  </div>
                )}
              </div>
              {!f.collapsed && (
                <div className="ml-3 mt-0.5 space-y-0.5 border-l border-zinc-800/60 pl-1">
                  {(f.children || []).map((child) => renderItem(child, f.id))}
                  {(f.children || []).length === 0 && editMode && (
                    <div className="text-[10px] text-zinc-600 italic px-2 py-1">
                      Empty — use the dropdown next to a tab to move it here.
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
