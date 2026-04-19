import { useState, useEffect } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import {
  BarChart3, Search, Terminal, FlaskConical, Music, Settings as SettingsIcon, AudioLines,
  GitBranch, Database, MessageSquare, ChevronRight, Disc3, Users, Package, Sliders, Send,
  Menu, X, AlertTriangle, Sparkles, Briefcase,
} from 'lucide-react'
import AssistantPanel from './AssistantPanel'
import SettingsDrawer from './SettingsDrawer'
import { useAssistantVisibility } from '../contexts/AssistantVisibilityContext'
import { useVersion } from '../hooks/useSoundPulse'

// Reactive read of localStorage config status. Re-checks on the
// soundpulse_config_changed event the SettingsDrawer fires after save
// so the banner disappears the instant the user fills the fields.
function useConfigStatus() {
  const compute = () => ({
    hasKey: !!localStorage.getItem('soundpulse_api_key'),
    hasUrl:
      !!(localStorage.getItem('soundpulse_base_url') ||
         import.meta.env.VITE_API_BASE_URL),
  })
  const [status, setStatus] = useState(compute)
  useEffect(() => {
    const recheck = () => setStatus(compute())
    window.addEventListener('storage', recheck)
    window.addEventListener('soundpulse_config_changed', recheck)
    return () => {
      window.removeEventListener('storage', recheck)
      window.removeEventListener('soundpulse_config_changed', recheck)
    }
  }, [])
  return { ...status, isConfigured: status.hasKey && status.hasUrl }
}

const NAV_ITEMS = [
  { to: '/',                label: 'Dashboard',       icon: BarChart3 },
  { to: '/explore',         label: 'Explore',         icon: Search },
  { to: '/song-lab',        label: 'Song Lab',        icon: Music },
  { to: '/blueprints',      label: 'Blueprints',      icon: Sparkles },
  { to: '/songs',           label: 'Songs',           icon: Disc3 },
  { to: '/artists',         label: 'Artists',         icon: Users },
  { to: '/releases',        label: 'Releases',        icon: Package },
  { to: '/rights',          label: 'Rights',          icon: Briefcase },
  { to: '/instrumentals',   label: 'Instrumentals',   icon: Sliders },
  { to: '/submissions',     label: 'Submissions',     icon: Send },
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
  const [navOpen, setNavOpen] = useState(false)  // mobile sidebar drawer state
  const { visible: assistantVisible, show: showAssistant } = useAssistantVisibility()
  const { isConfigured, hasKey, hasUrl } = useConfigStatus()

  // Close the mobile nav whenever a route is clicked.
  const closeNav = () => setNavOpen(false)

  const navContent = (
    <>
      {/* Logo */}
      <div className="flex items-center gap-2.5 px-4 py-5 border-b border-zinc-800">
        <AudioLines className="w-6 h-6 text-violet-400" />
        <span className="text-base font-semibold text-zinc-100 tracking-tight">SoundPulse</span>
      </div>

      {/* Nav links */}
      <nav className="flex-1 flex flex-col gap-0.5 px-2 py-3 overflow-y-auto">
        {NAV_ITEMS.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            onClick={closeNav}
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
          onClick={() => { setSettingsOpen(true); closeNav() }}
          className="flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-sm font-medium text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/50 transition-colors w-full"
        >
          <SettingsIcon className="w-4 h-4 flex-shrink-0" />
          Settings
        </button>
      </div>
    </>
  )

  return (
    <div className="flex h-screen overflow-hidden bg-zinc-950">
      {/* ── Desktop sidebar (always visible md+, hidden on mobile) ── */}
      <aside className="hidden md:flex w-52 flex-shrink-0 flex-col border-r border-zinc-800 bg-zinc-950">
        {navContent}
      </aside>

      {/* ── Mobile slide-in drawer ── */}
      {navOpen && (
        <div className="md:hidden fixed inset-0 z-40 flex" onClick={closeNav}>
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
          <aside
            className="relative w-64 max-w-[80%] flex flex-col border-r border-zinc-800 bg-zinc-950 shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            {navContent}
          </aside>
        </div>
      )}

      {/* ── Main content + top bar ── */}
      <main className="flex-1 min-w-0 overflow-y-auto bg-zinc-950">
        {/* Top bar — hamburger on mobile, version badge on the right */}
        <div className="sticky top-0 z-10 flex items-center justify-between gap-3 px-4 md:px-6 py-3 border-b border-zinc-800/60 bg-zinc-950/80 backdrop-blur">
          <button
            onClick={() => setNavOpen(true)}
            className="md:hidden p-1.5 rounded-lg text-zinc-300 hover:text-violet-300 hover:bg-violet-500/10"
            title="Menu"
          >
            <Menu className="w-5 h-5" />
          </button>
          <div className="md:hidden flex items-center gap-1.5 text-zinc-200 font-semibold">
            <AudioLines className="w-4 h-4 text-violet-400" />
            <span className="text-sm">SoundPulse</span>
          </div>
          <VersionBadge />
        </div>

        {/* Persistent "not configured" banner — shown across every page when
            API key or URL is missing. Mobile users hitting the app for the
            first time see this immediately and know to open Settings. */}
        {!isConfigured && (
          <div className="px-4 md:px-6 pt-3">
            <button
              onClick={() => setSettingsOpen(true)}
              className="w-full flex items-start gap-3 px-4 py-3 bg-amber-500/10 border border-amber-500/40 rounded-lg text-left hover:bg-amber-500/15 transition-colors"
            >
              <AlertTriangle className="w-5 h-5 text-amber-400 flex-shrink-0 mt-0.5" />
              <div className="flex-1 min-w-0">
                <div className="text-sm font-semibold text-amber-200">
                  API not configured on this device — tap to open Settings
                </div>
                <div className="text-xs text-amber-300/80 mt-0.5">
                  {!hasKey && !hasUrl && 'Missing API key and base URL.'}
                  {!hasKey && hasUrl && 'Missing API key.'}
                  {hasKey && !hasUrl && 'Missing API base URL.'}
                  {' '}Each browser stores its own settings — if you set this on
                  desktop, you need to set it again here. Use the "Share to
                  another device" button on your desktop Settings to copy a
                  one-tap import link.
                </div>
              </div>
            </button>
          </div>
        )}

        <div className="p-4 md:p-6">
          <Outlet />
        </div>
      </main>

      {/* ── Hideable assistant panel — hidden by default on mobile ── */}
      {assistantVisible && (
        <div className="hidden md:block">
          <AssistantPanel />
        </div>
      )}

      {/* Floating re-open button when the assistant is hidden — desktop only */}
      {!assistantVisible && (
        <button
          onClick={showAssistant}
          title="Show Assistant (Cmd/Ctrl + .)"
          className="hidden md:flex fixed right-3 bottom-6 z-20 items-center gap-1.5 px-3 py-2.5 bg-violet-600/20 hover:bg-violet-600/30 border border-violet-500/40 text-violet-300 rounded-l-lg shadow-lg backdrop-blur transition-colors"
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
