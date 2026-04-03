import { useState, useEffect, useRef } from 'react'
import { X, Key, Globe } from 'lucide-react'

export default function SettingsDrawer({ isOpen, onClose }) {
  const [apiKey, setApiKey] = useState('')
  const [baseUrl, setBaseUrl] = useState('/api/v1')
  const drawerRef = useRef(null)

  // Load from localStorage when opening
  useEffect(() => {
    if (isOpen) {
      setApiKey(localStorage.getItem('soundpulse_api_key') || '')
      setBaseUrl(localStorage.getItem('soundpulse_base_url') || '/api/v1')
    }
  }, [isOpen])

  // Close on Escape
  useEffect(() => {
    function handleKeyDown(e) {
      if (e.key === 'Escape' && isOpen) {
        onClose?.()
      }
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [isOpen, onClose])

  function handleSave() {
    localStorage.setItem('soundpulse_api_key', apiKey)
    localStorage.setItem('soundpulse_base_url', baseUrl)
    onClose?.()
  }

  function handleBackdropClick(e) {
    if (drawerRef.current && !drawerRef.current.contains(e.target)) {
      onClose?.()
    }
  }

  if (!isOpen) return null

  return (
    <div
      className="fixed inset-0 z-50 flex justify-end"
      onClick={handleBackdropClick}
    >
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" />

      {/* Drawer panel */}
      <div
        ref={drawerRef}
        className="relative w-full max-w-sm bg-zinc-900 border-l border-zinc-700 shadow-2xl flex flex-col animate-slide-in"
        style={{
          animation: 'slideInRight 200ms ease-out forwards',
        }}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-zinc-800">
          <h2 className="text-base font-semibold text-zinc-100">Settings</h2>
          <button
            onClick={onClose}
            className="text-zinc-400 hover:text-zinc-200 transition-colors duration-150"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto px-6 py-5 space-y-5">
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
              placeholder="Enter your API key"
              className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm text-zinc-100 placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-violet-500/50 focus:border-violet-500 transition-all duration-150"
            />
          </div>

          {/* Base URL */}
          <div>
            <label className="flex items-center gap-2 text-sm font-medium text-zinc-300 mb-2">
              <Globe className="w-3.5 h-3.5 text-zinc-500" />
              Base URL
            </label>
            <input
              type="text"
              value={baseUrl}
              onChange={(e) => setBaseUrl(e.target.value)}
              placeholder="/api/v1"
              className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm text-zinc-100 placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-violet-500/50 focus:border-violet-500 transition-all duration-150"
            />
            <p className="mt-1.5 text-xs text-zinc-500">
              Default: /api/v1
            </p>
          </div>
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-zinc-800 flex justify-end gap-3">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm font-medium text-zinc-400 hover:text-zinc-200 transition-colors duration-150"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            className="px-4 py-2 text-sm font-medium bg-violet-600 hover:bg-violet-500 text-white rounded-lg transition-colors duration-150"
          >
            Save
          </button>
        </div>
      </div>

      <style>{`
        @keyframes slideInRight {
          from {
            transform: translateX(100%);
          }
          to {
            transform: translateX(0);
          }
        }
      `}</style>
    </div>
  )
}
