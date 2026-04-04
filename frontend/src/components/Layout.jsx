import { useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import { BarChart3, Search, Terminal, FlaskConical, Music, Settings, AudioLines } from 'lucide-react'
import AssistantPanel from './AssistantPanel'
import SettingsDrawer from './SettingsDrawer'

const NAV_ITEMS = [
  { to: '/',                label: 'Dashboard',       icon: BarChart3 },
  { to: '/explore',         label: 'Explore',         icon: Search },
  { to: '/song-lab',        label: 'Song Lab',        icon: Music },
  { to: '/model-validation',label: 'Model Validation',icon: FlaskConical },
  { to: '/api-tester',      label: 'API Tester',      icon: Terminal },
]

export default function Layout() {
  const [settingsOpen, setSettingsOpen] = useState(false)

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
            <Settings className="w-4 h-4 flex-shrink-0" />
            Settings
          </button>
        </div>
      </aside>

      {/* ── Main content ── */}
      <main className="flex-1 min-w-0 overflow-y-auto bg-zinc-950">
        <div className="p-6">
          <Outlet />
        </div>
      </main>

      {/* ── Persistent assistant panel ── */}
      <AssistantPanel />

      {/* Settings drawer */}
      <SettingsDrawer isOpen={settingsOpen} onClose={() => setSettingsOpen(false)} />
    </div>
  )
}
