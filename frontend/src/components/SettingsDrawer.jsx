import { useState, useEffect, useRef } from 'react'
import { X, Key, Globe, AlertTriangle, CheckCircle2, Share2, Copy, Check, Download } from 'lucide-react'
import { useQueryClient } from '@tanstack/react-query'

// Generality principle: NO hardcoded production URL or admin key in the
// frontend bundle. The API base URL is read from the Vite build-time env
// var VITE_API_BASE_URL (baked into the bundle at build time), overridable
// by localStorage 'soundpulse_base_url' at runtime for the user's personal
// override. API key comes from the user — we never ship one.
const VITE_DEFAULT_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1'

// Encode/decode the cross-device config blob. Plain base64 of a JSON
// string — not a secret, just opaque enough that the URL doesn't shout
// the API key in plaintext when texted/emailed. Server-side keys are
// what actually gate access; this is a usability convenience.
function encodeConfig(apiKey, baseUrl) {
  const json = JSON.stringify({ k: apiKey || '', u: baseUrl || '' })
  // btoa needs to handle UTF-8 safely
  return btoa(unescape(encodeURIComponent(json)))
}
function decodeConfig(encoded) {
  try {
    const json = decodeURIComponent(escape(atob(encoded)))
    const obj = JSON.parse(json)
    if (typeof obj === 'object' && obj && (obj.k !== undefined || obj.u !== undefined)) {
      return { apiKey: obj.k || '', baseUrl: obj.u || '' }
    }
  } catch {}
  return null
}

export default function SettingsDrawer({ isOpen, onClose }) {
  const [apiKey, setApiKey] = useState('')
  const [baseUrl, setBaseUrl] = useState('')
  const [shareLink, setShareLink] = useState('')
  const [copied, setCopied] = useState(false)
  const [importPrompt, setImportPrompt] = useState(null)  // { apiKey, baseUrl } when ?config= is present
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
      setShareLink('')
      setCopied(false)
    }
  }, [isOpen])

  // Detect a ?config= query param on EVERY mount (not just when the drawer
  // opens) so a user who opens a share link goes straight to a prompt.
  useEffect(() => {
    try {
      const params = new URLSearchParams(window.location.search)
      const encoded = params.get('config')
      if (encoded) {
        const decoded = decodeConfig(encoded)
        if (decoded) setImportPrompt(decoded)
      }
    } catch {}
  }, [])

  useEffect(() => {
    function handleKeyDown(e) {
      if (e.key === 'Escape' && isOpen) onClose?.()
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [isOpen, onClose])

  function persistAndNotify(key, url) {
    localStorage.setItem('soundpulse_api_key', key || '')
    localStorage.setItem('soundpulse_base_url', url || '')
    // Tell the rest of the app (Layout's not-configured banner, any other
    // listener) to recheck. Plain Event since CustomEvent payload isn't
    // needed — listeners re-read localStorage themselves.
    try { window.dispatchEvent(new Event('soundpulse_config_changed')) } catch {}
    queryClient.invalidateQueries()
  }

  function handleSave() {
    persistAndNotify(apiKey, baseUrl)
    onClose?.()
  }

  function applyDefaults() {
    setBaseUrl(VITE_DEFAULT_BASE)
    // Deliberately do NOT prefill the API key — it must come from the user.
  }

  function handleGenerateShareLink() {
    const origin = window.location.origin
    const path = window.location.pathname
    const encoded = encodeConfig(apiKey, baseUrl)
    const link = `${origin}${path}?config=${encoded}`
    setShareLink(link)
    // Best-effort clipboard write. Falls through silently if denied —
    // the input is selectable for manual copy.
    if (navigator.clipboard?.writeText) {
      navigator.clipboard.writeText(link).then(
        () => { setCopied(true); setTimeout(() => setCopied(false), 2000) },
        () => {}
      )
    }
  }

  function handleAcceptImport() {
    if (!importPrompt) return
    setApiKey(importPrompt.apiKey)
    setBaseUrl(importPrompt.baseUrl)
    persistAndNotify(importPrompt.apiKey, importPrompt.baseUrl)
    setImportPrompt(null)
    // Strip the ?config= from the URL so a refresh doesn't re-prompt and
    // the API key doesn't sit in the address bar.
    try {
      const url = new URL(window.location.href)
      url.searchParams.delete('config')
      window.history.replaceState({}, '', url.toString())
    } catch {}
    onClose?.()
  }

  function handleDismissImport() {
    setImportPrompt(null)
    try {
      const url = new URL(window.location.href)
      url.searchParams.delete('config')
      window.history.replaceState({}, '', url.toString())
    } catch {}
  }

  function handleBackdropClick(e) {
    if (drawerRef.current && !drawerRef.current.contains(e.target)) onClose?.()
  }

  const savedUrl = localStorage.getItem('soundpulse_base_url') || ''
  const isConfigured =
    !!localStorage.getItem('soundpulse_api_key') &&
    savedUrl.startsWith('http')

  // Keep the drawer mounted when an import prompt is pending so the user
  // can decide. The import prompt itself is a top-of-drawer modal-card.
  const shouldRender = isOpen || importPrompt

  if (!shouldRender) return null

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
          {/* Import prompt — shown when this device opened a ?config= share link */}
          {importPrompt && (
            <div className="px-4 py-4 bg-violet-500/10 border border-violet-500/40 rounded-lg space-y-3">
              <div className="flex items-start gap-2.5">
                <Download className="w-5 h-5 text-violet-300 flex-shrink-0 mt-0.5" />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-semibold text-violet-200">Import settings from another device?</p>
                  <p className="text-xs text-violet-300/80 mt-1 leading-relaxed">
                    URL: <span className="font-mono break-all">{importPrompt.baseUrl || '(empty)'}</span>
                  </p>
                  <p className="text-xs text-violet-300/80 leading-relaxed">
                    API key: <span className="font-mono">{importPrompt.apiKey ? `${importPrompt.apiKey.slice(0, 12)}…` : '(empty)'}</span>
                  </p>
                </div>
              </div>
              <div className="flex gap-2 justify-end">
                <button
                  onClick={handleDismissImport}
                  className="px-3 py-1.5 text-xs text-zinc-400 hover:text-zinc-200"
                >
                  Dismiss
                </button>
                <button
                  onClick={handleAcceptImport}
                  className="px-3 py-1.5 text-xs font-medium bg-violet-600 hover:bg-violet-500 text-white rounded"
                >
                  Apply &amp; reload data
                </button>
              </div>
            </div>
          )}

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
                  onClick={applyDefaults}
                  className="mt-2 text-xs text-amber-300 underline hover:text-amber-200"
                >
                  Use build-time default URL →
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
              onClick={applyDefaults}
              className="w-full text-xs text-zinc-500 hover:text-zinc-300 underline text-left"
            >
              Reset to build-time default URL
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
              Build-time default: {VITE_DEFAULT_BASE}
            </p>
          </div>

          {/* Share to another device — generates a one-tap import link */}
          <div className="pt-3 border-t border-zinc-800">
            <label className="flex items-center gap-2 text-sm font-medium text-zinc-300 mb-2">
              <Share2 className="w-3.5 h-3.5 text-zinc-500" />
              Share to another device
            </label>
            <p className="text-xs text-zinc-500 mb-2 leading-relaxed">
              Each browser stores its own API key + URL. Generate a one-tap
              import link, text or email it to yourself, open on the new
              device, and tap Apply.
            </p>
            <button
              onClick={handleGenerateShareLink}
              disabled={!apiKey || !baseUrl}
              className="w-full flex items-center justify-center gap-2 px-3 py-2 bg-zinc-800 hover:bg-zinc-700 disabled:bg-zinc-900 disabled:text-zinc-600 border border-zinc-700 text-zinc-200 text-xs font-medium rounded transition-colors"
            >
              {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
              {copied ? 'Link copied to clipboard' : 'Generate &amp; copy share link'}
            </button>
            {shareLink && (
              <textarea
                readOnly
                value={shareLink}
                rows={3}
                onClick={(e) => e.target.select()}
                className="w-full mt-2 px-2 py-2 bg-zinc-950 border border-zinc-800 rounded text-[11px] text-zinc-300 font-mono break-all resize-none"
              />
            )}
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
