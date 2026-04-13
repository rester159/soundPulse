import { useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import {
  BarChart3, Search, Terminal, FlaskConical, Music, Settings as SettingsIcon, AudioLines,
  GitBranch, Database, MessageSquare, ChevronRight, Disc3, Users, Package, Sliders,
} from 'lucide-react'
import AssistantPanel from './AssistantPanel'
import SettingsDrawer from './SettingsDrawer'
import { useAssistantVisibility } from '../contexts/AssistantVisibilityContext'
import { useVersion } from '../hooks/useSoundPulse'

const NAV_ITEMS = [
  { to: '/',                label: 'Dashboard',       icon: BarChart3 },
  { to: '/explore',         label: 'Explore',         icon: Search },
  { to: '/song-lab',        label: 'Song Lab',        icon: Music },
  { to: '/songs',           label: 'Songs',           icon: Disc3 },
  { to: '/artists',         label: 'Artists',         icon: Users },
  { to: '/releases',        label: 'Releases',        icon: Package },
  { to: '/instrumentals',   label: 'Instrumentals',   icon: Sliders },
  { to: '/model-validation',label: 'Model Validation',icon: FlaskConical },
  { to: '/data-flow',       label: 'Data Pipeline',   icon: GitBranch },
  { to: '/db-stats',        label: 'DB Stats',        icon: Database },
  { to: '/api-tester',      label: 'API Tester',      icon: Terminal },
  { to: '/settings',        label: 'Settings',        icon: SettingsIcon },
]

function formatDeployTime(iso) {
  if (!iso) return ''
  try {
    const d = new Date(iso)
    const now = new Date()
    const diffMs = now - d
    const diffMin = Math.floor(diffMs / 60_000)
    const diffHr  = Math.floor(diffMin / 60)
    const diffDay = Math.floor(diffHr / 24)
    // Short relative format that tells you "stale vs fresh" at a glance
    if (diffMin < 1) return 'just now'
    if (diffMin < 60) return `${diffMin}m ago`
    if (diffHr  < 24) return `${diffHr}h ago`
    return `${diffDay}d ago`
  } catch {
    return ''
  }
}

function VersionBadge() {
  // Fetches /api/v1/version and displays short commit + deploy age
  const { data, isLoading, isError } = useVersion()
  const v = data?.data || {}
  const commit = v.commit || (isLoading ? '…' : 'dev')
  const deployed = formatDeployTime(v.deployed_at)
  const env = v.environment || 'local'
  const absoluteTime = v.deployed_at
    ? new Date(v.deployed_at).toLocaleString()
    : 'unknown'

  const color =
    isError ? 'text-rose-400 border-rose-500/30 bg-rose-500/5'
    : env === 'production' ? 'text-violet-300 border-violet-500/30 bg-violet-500/5'
    : 'text-zinc-400 border-zinc-700/60 bg-zinc-900'

  return (
    <div
      className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border text-[11px] font-mono ${color}`}
      title={`Deployed ${absoluteTime}\nEnvironment: ${env}\nCommit: ${v.commit_full || 'dev'}`}
    >
      <span className="text-[10px] uppercase tracking-wider opacity-70">{env}</span>
      <span className="opacity-40">·</span>
      <span>{commit}</span>
      <span className="opacity-40">·</span>
      <span className="opacity-70">{deployed || 'unknown'}</span>
    </div>
  )
}

export default function Layout() {
  const [settingsOpen, setSettingsOpen] = useState(false)
  const { visible: assistantVisible, show: showAssistant } = useAssistantVisibility()

  return (
    <div className="flex h-screen overflow-hidden bg-zinc-950">
      {/* ── Left nav ── */}
      <aside className="w-52 flex-shrink-0 flex flex-col border-r border-zinc-800 bg-zinc-950">
        {/* Logo */}
        <div className="flex items-center gap-2.5 px-4 py-5 border-b border-zinc-800">
          <AudioLines className="w-6 h-6 text-violet-400" />
          <span className="text-base font-semibold text-zinc-100 tracking-tight">SoundPulse</span>
        </div>

        {/* Nav links */}
        <nav className="flex-1 flex flex-col gap-0.5 px-2 py-3">
          {NAV_ITEMS.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              className={({ isActive }) =>
                `flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-violet-500/10 text-violet-400'
                    : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/50'
                }`
              }
            >
              <Icon className="w-4 h-4 flex-shrink-0" />
              {label}
            </NavLink>
          ))}
        </nav>

        {/* Settings */}
        <div className="px-2 py-3 border-t border-zinc-800">
          <button
            onClick={() => setSettingsOpen(true)}
            className="flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-sm font-medium text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/50 transition-colors w-full"
          >
            <SettingsIcon className="w-4 h-4 flex-shrink-0" />
            Settings
          </button>
        </div>
      </aside>

      {/* ── Main content + top bar ── */}
      <main className="flex-1 min-w-0 overflow-y-auto bg-zinc-950">
        {/* Top bar with version badge on the right */}
        <div className="sticky top-0 z-10 flex items-center justify-end gap-3 px-6 py-3 border-b border-zinc-800/60 bg-zinc-950/80 backdrop-blur">
          <VersionBadge />
        </div>
        <div className="p-6">
          <Outlet />
        </div>
      </main>

      {/* ── Hideable assistant panel (PRD §21.1) ── */}
      {assistantVisible && <AssistantPanel />}

      {/* Floating re-open button when the assistant is hidden */}
      {!assistantVisible && (
        <button
          onClick={showAssistant}
          title="Show Assistant (Cmd/Ctrl + .)"
          className="fixed right-3 bottom-6 z-20 flex items-center gap-1.5 px-3 py-2.5 bg-violet-600/20 hover:bg-violet-600/30 border border-violet-500/40 text-violet-300 rounded-l-lg shadow-lg backdrop-blur transition-colors"
        >
          <ChevronRight size={14} className="rotate-180" />
          <MessageSquare size={14} />
        </button>
      )}

      {/* Settings drawer */}
      <SettingsDrawer isOpen={settingsOpen} onClose={() => setSettingsOpen(false)} />
    </div>
  )
}
