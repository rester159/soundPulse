import { useState, useCallback, useEffect } from 'react'
import { Play, History, Terminal, Loader2 } from 'lucide-react'
import { ENDPOINTS } from '../utils/endpoints'
import { useApiRequest, generateCurl } from '../hooks/useSoundPulse'
import { formatDuration } from '../utils/formatters'
import RequestBuilder from '../components/RequestBuilder'
import ResponseViewer from '../components/ResponseViewer'

const METHOD_COLORS = {
  GET: 'bg-emerald-500/15 text-emerald-400',
  POST: 'bg-violet-500/15 text-violet-400',
  PUT: 'bg-amber-500/15 text-amber-400',
  DELETE: 'bg-rose-500/15 text-rose-400',
}

function MethodBadge({ method, size = 'sm' }) {
  const colors = METHOD_COLORS[method] || 'bg-zinc-700 text-zinc-300'
  const sizeClasses = size === 'xs' ? 'px-1.5 py-0.5 text-[10px]' : 'px-2 py-0.5 text-xs'
  return (
    <span className={`inline-flex items-center rounded font-bold font-mono ${colors} ${sizeClasses}`}>
      {method}
    </span>
  )
}

function StatusBadge({ status }) {
  if (!status && status !== 0) return null
  let colors = 'bg-zinc-700 text-zinc-300'
  if (status >= 200 && status < 300) colors = 'bg-emerald-500/15 text-emerald-400'
  else if (status >= 400 && status < 500) colors = 'bg-amber-500/15 text-amber-400'
  else if (status >= 500) colors = 'bg-rose-500/15 text-rose-400'
  return (
    <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold font-mono ${colors}`}>
      {status}
    </span>
  )
}

function EndpointLabel({ endpoint }) {
  return (
    <span className="flex items-center gap-2">
      <MethodBadge method={endpoint.method} />
      <span className="font-mono text-sm text-zinc-200">{endpoint.path}</span>
    </span>
  )
}

export default function ApiPlayground() {
  const [selectedIndex, setSelectedIndex] = useState(0)
  const [paramValues, setParamValues] = useState({})
  const [response, setResponse] = useState(null)
  const [curl, setCurl] = useState(null)
  const [history, setHistory] = useState([])

  const endpoint = ENDPOINTS[selectedIndex]
  const mutation = useApiRequest()

  const handleSend = useCallback(async () => {
    if (!endpoint) return

    // Build path with substituted path params
    let resolvedPath = endpoint.path
    const queryParams = {}

    for (const [key, value] of Object.entries(paramValues)) {
      if (value === '' || value === undefined || value === null) continue
      if (endpoint.path.includes(`{${key}}`)) {
        resolvedPath = resolvedPath.replace(`{${key}}`, encodeURIComponent(value))
      } else {
        queryParams[key] = value
      }
    }

    // Generate cURL before sending
    const curlStr = generateCurl(endpoint.method, endpoint.path, paramValues)
    setCurl(curlStr)

    try {
      const result = await mutation.mutateAsync({
        method: endpoint.method,
        path: resolvedPath,
        params: endpoint.method === 'GET' ? queryParams : undefined,
        body: endpoint.method !== 'GET' ? queryParams : undefined,
      })

      setResponse(result)

      // Add to history (newest first, max 20)
      setHistory((prev) => {
        const entry = {
          id: Date.now(),
          method: endpoint.method,
          path: resolvedPath,
          params: { ...paramValues },
          status: result.status,
          duration: result.duration,
          endpointIndex: selectedIndex,
          timestamp: new Date().toISOString(),
        }
        return [entry, ...prev].slice(0, 20)
      })
    } catch (err) {
      setResponse({
        status: 0,
        data: { error: err.message },
        duration: 0,
        error: err.message,
      })
    }
  }, [endpoint, paramValues, mutation, selectedIndex])

  // Ctrl+Enter keyboard shortcut
  useEffect(() => {
    function handleKeyDown(e) {
      if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
        e.preventDefault()
        handleSend()
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [handleSend])

  function handleSelectEndpoint(index) {
    setSelectedIndex(index)
    setResponse(null)
    setCurl(null)
  }

  function handleHistoryClick(entry) {
    setSelectedIndex(entry.endpointIndex)
    setParamValues(entry.params)
  }

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex items-center gap-3">
        <div className="w-9 h-9 rounded-lg bg-violet-500/10 flex items-center justify-center">
          <Terminal className="w-4.5 h-4.5 text-violet-400" />
        </div>
        <div>
          <h1 className="text-xl font-semibold text-zinc-100">API Tester</h1>
          <p className="text-xs text-zinc-500 mt-0.5">Interactive API playground</p>
        </div>
      </div>

      {/* Endpoint selector + Send */}
      <div className="flex items-stretch gap-3">
        <div className="flex-1 relative">
          <select
            value={selectedIndex}
            onChange={(e) => handleSelectEndpoint(Number(e.target.value))}
            className="w-full h-full px-4 py-3 bg-zinc-900 border border-zinc-800 rounded-lg text-sm text-zinc-100 font-mono focus:outline-none focus:ring-2 focus:ring-violet-500/50 focus:border-violet-500 transition-all duration-150 ease-out appearance-none cursor-pointer"
          >
            {ENDPOINTS.map((ep, i) => (
              <option key={`${ep.method}-${ep.path}`} value={i}>
                {ep.method} {ep.path} — {ep.description}
              </option>
            ))}
          </select>
        </div>

        <button
          onClick={handleSend}
          disabled={mutation.isPending}
          className="flex items-center gap-2 px-5 py-3 bg-violet-600 hover:bg-violet-500 disabled:bg-violet-600/50 disabled:cursor-not-allowed text-white text-sm font-medium rounded-lg transition-all duration-150 ease-out"
        >
          {mutation.isPending ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Play className="w-4 h-4" />
          )}
          Send
        </button>
      </div>

      {/* Endpoint description */}
      <div className="flex items-center gap-2 px-1">
        <MethodBadge method={endpoint.method} />
        <span className="font-mono text-sm text-zinc-300">{endpoint.path}</span>
        <span className="text-zinc-600 mx-1">&mdash;</span>
        <span className="text-sm text-zinc-400">{endpoint.description}</span>
        <span className="ml-auto text-[11px] text-zinc-600 font-mono">Ctrl+Enter to send</span>
      </div>

      {/* Main panels: Request + Response */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Left: Request Builder */}
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
          <h2 className="text-sm font-semibold text-zinc-300 mb-4">Parameters</h2>
          <RequestBuilder
            endpoint={endpoint}
            values={paramValues}
            onChange={setParamValues}
          />

          {/* Body editor for POST/PUT */}
          {endpoint.body && (
            <div className="mt-5 pt-5 border-t border-zinc-800">
              <h3 className="text-xs font-medium text-zinc-400 mb-2">Request Body (JSON)</h3>
              <textarea
                value={paramValues._body || ''}
                onChange={(e) => setParamValues({ ...paramValues, _body: e.target.value })}
                placeholder='{"items": [...]}'
                rows={6}
                className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm text-zinc-100 placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-violet-500/50 focus:border-violet-500 transition-all duration-150 ease-out font-mono resize-y"
              />
            </div>
          )}
        </div>

        {/* Right: Response Viewer */}
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
          <h2 className="text-sm font-semibold text-zinc-300 mb-4">Response</h2>
          <ResponseViewer response={response} curl={curl} />
        </div>
      </div>

      {/* History panel */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-xl">
        <div className="flex items-center gap-2 px-5 py-3.5 border-b border-zinc-800">
          <History className="w-4 h-4 text-zinc-500" />
          <h2 className="text-sm font-semibold text-zinc-300">Request History</h2>
          <span className="text-xs text-zinc-600 font-mono ml-auto">
            {history.length} / 20
          </span>
        </div>

        {history.length === 0 ? (
          <div className="px-5 py-8 text-center text-sm text-zinc-600">
            No requests yet. Send a request to see it here.
          </div>
        ) : (
          <div className="divide-y divide-zinc-800/50 max-h-72 overflow-y-auto">
            {history.map((entry) => (
              <button
                key={entry.id}
                onClick={() => handleHistoryClick(entry)}
                className="flex items-center gap-3 w-full px-5 py-2.5 text-left hover:bg-zinc-800/40 transition-colors duration-150 ease-out group"
              >
                <MethodBadge method={entry.method} size="xs" />
                <span className="font-mono text-xs text-zinc-400 group-hover:text-zinc-200 transition-colors duration-150 ease-out truncate flex-1">
                  {entry.path}
                </span>
                <StatusBadge status={entry.status} />
                <span className="text-[11px] text-zinc-600 font-mono w-16 text-right flex-shrink-0">
                  {formatDuration(entry.duration)}
                </span>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
