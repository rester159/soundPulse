import { useState, useEffect, useRef } from 'react'
import { X, Globe, AlertTriangle, CheckCircle2 } from 'lucide-react'
import { useQueryClient } from '@tanstack/react-query'

// Open-access mode: the site no longer requires an API key. The only
// per-device setting is the API base URL — and even that has a build-time
// default baked into the bundle, so a fresh device works immediately.
const VITE_DEFAULT_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1'

export default function SettingsDrawer({ isOpen, onClose }) {
  const [baseUrl, setBaseUrl] = useState('')
  const drawerRef = useRef(null)
  const queryClient = useQueryClient()

  useEffect(() => {
    if (isOpen) {
      setBaseUrl(
        localStorage.getItem('soundpulse_base_url') || VITE_DEFAULT_BASE
      )
    }
  }, [isOpen])

  useEffect(() => {
    function handleKeyDown(e) {
      if (e.key === 'Escape' && isOpen) onClose?.()
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [isOpen, onClose])

  function handleSave() {
    localStorage.setItem('soundpulse_base_url', baseUrl || '')
    // Tell the rest of the app (Layout's not-configured banner, version
    // badge, etc.) to recheck. Listeners re-read localStorage themselves.
    try { window.dispatchEvent(new Event('soundpulse_config_changed')) } catch {}
    queryClient.invalidateQueries()
    onClose?.()
  }

  function applyDefault() {
    setBaseUrl(VITE_DEFAULT_BASE)
  }

  function handleBackdropClick(e) {
    if (drawerRef.current && !drawerRef.current.contains(e.target)) onClose?.()
  }

  const effectiveUrl =
    localStorage.getItem('soundpulse_base_url') || VITE_DEFAULT_BASE
  const isConfigured = effectiveUrl.startsWith('http') || effectiveUrl === '/api/v1'

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 flex justify-end" onClick={handleBackdropClick}>
      <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" />

      <div
        ref={drawerRef}
        className="relative w-full max-w-sm bg-zinc-900 border-l border-zinc-700 shadow-2xl flex flex-col"
        style={{ animation: 'slideInRight 180ms ease-out forwards' }}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-zinc-800">
          <h2 className="text-base font-semibold text-zinc-100">Settings</h2>
          <button onClick={onClose} className="text-zinc-400 hover:text-zinc-200 transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-5 space-y-5">
          {/* Status banner */}
          {isConfigured ? (
            <div className="flex items-center gap-2 px-4 py-3 bg-emerald-900/20 border border-emerald-700/40 rounded-lg">
              <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0" />
              <p className="text-xs text-emerald-300">Connected to {effectiveUrl}</p>
            </div>
          ) : (
            <div className="flex items-start gap-3 px-4 py-3 bg-amber-900/20 border border-amber-700/40 rounded-lg">
              <AlertTriangle className="w-4 h-4 text-amber-400 flex-shrink-0 mt-0.5" />
              <div>
                <p className="text-xs font-medium text-amber-300">No API URL set</p>
                <p className="text-xs text-amber-400/80 mt-0.5 leading-relaxed">
                  The site runs in open-access mode (no key required) but it still
                  needs to know where the API lives.
                </p>
              </div>
            </div>
          )}

          {/* Open-access notice */}
          <div className="px-4 py-3 bg-violet-500/5 border border-violet-500/20 rounded-lg">
            <p className="text-[11px] text-violet-200/80 leading-relaxed">
              <span className="font-semibold text-violet-300">Open access:</span>{' '}
              this site no longer requires an API key. Anyone with the URL can
              use it. The API base URL below is the only per-device setting.
            </p>
          </div>

          {/* Base URL */}
          <div>
            <label className="flex items-center gap-2 text-sm font-medium text-zinc-300 mb-2">
              <Globe className="w-3.5 h-3.5 text-zinc-500" />
              API Base URL
            </label>
            <input
              type="text"
              value={baseUrl}
              onChange={(e) => setBaseUrl(e.target.value)}
              placeholder="https://your-api.up.railway.app/api/v1"
              className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm text-zinc-100 placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-violet-500/50 focus:border-violet-500 transition-all"
            />
            <div className="flex items-center justify-between mt-1.5">
              <p className="text-xs text-zinc-500 break-all">
                Build-time default: <span className="font-mono">{VITE_DEFAULT_BASE}</span>
              </p>
              <button
                onClick={applyDefault}
                className="text-xs text-zinc-500 hover:text-zinc-300 underline whitespace-nowrap ml-2"
              >
                Reset
              </button>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-zinc-800 flex justify-end gap-3">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm font-medium text-zinc-400 hover:text-zinc-200 transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            className="px-4 py-2 text-sm font-medium bg-violet-600 hover:bg-violet-500 text-white rounded-lg transition-colors"
          >
            Save &amp; Reload Data
          </button>
        </div>
      </div>

      <style>{`
        @keyframes slideInRight {
          from { transform: translateX(100%); }
          to   { transform: translateX(0); }
        }
      `}</style>
    </div>
  )
}
