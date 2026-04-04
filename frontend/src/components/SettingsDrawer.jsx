import { useState, useEffect, useRef } from 'react'
import { X, Key, Globe, AlertTriangle, CheckCircle2 } from 'lucide-react'
import { useQueryClient } from '@tanstack/react-query'

const PROD_API = 'https://soundpulse-production-5266.up.railway.app/api/v1'
const PROD_KEY = 'sp_admin_0000000000000000000000000000dead'

export default function SettingsDrawer({ isOpen, onClose }) {
  const [apiKey, setApiKey] = useState('')
  const [baseUrl, setBaseUrl] = useState('')
  const drawerRef = useRef(null)
  const queryClient = useQueryClient()

  useEffect(() => {
    if (isOpen) {
      setApiKey(localStorage.getItem('soundpulse_api_key') || '')
      setBaseUrl(
        localStorage.getItem('soundpulse_base_url') ||
        import.meta.env.VITE_API_BASE_URL ||
        '/api/v1'
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
    localStorage.setItem('soundpulse_api_key', apiKey)
    localStorage.setItem('soundpulse_base_url', baseUrl)
    // Invalidate all queries so they refetch with the new URL + key immediately
    queryClient.invalidateQueries()
    onClose?.()
  }

  function applyProdDefaults() {
    setBaseUrl(PROD_API)
    setApiKey(PROD_KEY)
  }

  function handleBackdropClick(e) {
    if (drawerRef.current && !drawerRef.current.contains(e.target)) onClose?.()
  }

  const savedUrl = localStorage.getItem('soundpulse_base_url') || ''
  const isConfigured =
    !!localStorage.getItem('soundpulse_api_key') &&
    savedUrl.startsWith('http')

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
          {!isConfigured ? (
            <div className="flex items-start gap-3 px-4 py-3 bg-amber-900/20 border border-amber-700/40 rounded-lg">
              <AlertTriangle className="w-4 h-4 text-amber-400 flex-shrink-0 mt-0.5" />
              <div>
                <p className="text-xs font-medium text-amber-300">Not configured</p>
                <p className="text-xs text-amber-400/80 mt-0.5 leading-relaxed">
                  Set your API URL and key to load data.
                </p>
                <button
                  onClick={applyProdDefaults}
                  className="mt-2 text-xs text-amber-300 underline hover:text-amber-200"
                >
                  Use production defaults →
                </button>
              </div>
            </div>
          ) : (
            <div className="flex items-center gap-2 px-4 py-3 bg-emerald-900/20 border border-emerald-700/40 rounded-lg">
              <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0" />
              <p className="text-xs text-emerald-300">Connected — change settings below if data is missing.</p>
            </div>
          )}

          {/* Quick-fill button */}
          {isConfigured && (
            <button
              onClick={applyProdDefaults}
              className="w-full text-xs text-zinc-500 hover:text-zinc-300 underline text-left"
            >
              Reset to production defaults
            </button>
          )}

          {/* API Key */}
          <div>
            <label className="flex items-center gap-2 text-sm font-medium text-zinc-300 mb-2">
              <Key className="w-3.5 h-3.5 text-zinc-500" />
              API Key
            </label>
            <input
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder="sp_admin_..."
              className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm text-zinc-100 placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-violet-500/50 focus:border-violet-500 transition-all"
            />
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
              placeholder="https://your-api.railway.app/api/v1"
              className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm text-zinc-100 placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-violet-500/50 focus:border-violet-500 transition-all"
            />
            <p className="mt-1.5 text-xs text-zinc-500 break-all">
              Production: {PROD_API}
            </p>
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
