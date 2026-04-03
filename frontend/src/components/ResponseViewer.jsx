import { useState } from 'react'
import { Copy, Check, ChevronDown, ChevronUp, AlertCircle } from 'lucide-react'
import { formatDuration, getStatusColor } from '../utils/formatters'

const COLLAPSE_THRESHOLD = 40

function syntaxHighlight(json) {
  if (typeof json !== 'string') {
    json = JSON.stringify(json, null, 2)
  }

  return json.replace(
    /("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false)\b|-?\d+(?:\.\d*)?(?:[eE][+-]?\d+)?|\bnull\b)/g,
    (match) => {
      let cls = 'text-cyan-400'
      if (/^"/.test(match)) {
        if (/:$/.test(match)) {
          cls = 'text-violet-400'
        } else {
          cls = 'text-green-400'
        }
      } else if (/true|false/.test(match)) {
        cls = 'text-yellow-400'
      } else if (/null/.test(match)) {
        cls = 'text-zinc-500'
      }
      return `<span class="${cls}">${match}</span>`
    }
  )
}

function StatusBadge({ status }) {
  if (!status && status !== 0) return null

  let colorClasses = 'bg-zinc-700 text-zinc-300'
  if (status >= 200 && status < 300) {
    colorClasses = 'bg-emerald-500/15 text-emerald-400'
  } else if (status >= 400 && status < 500) {
    colorClasses = 'bg-amber-500/15 text-amber-400'
  } else if (status >= 500) {
    colorClasses = 'bg-rose-500/15 text-rose-400'
  }

  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-md text-xs font-semibold font-mono ${colorClasses}`}>
      {status}
    </span>
  )
}

function CopyButton({ text, label }) {
  const [copied, setCopied] = useState(false)

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // Fallback
      const textarea = document.createElement('textarea')
      textarea.value = text
      document.body.appendChild(textarea)
      textarea.select()
      document.execCommand('copy')
      document.body.removeChild(textarea)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  return (
    <button
      onClick={handleCopy}
      className="inline-flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-medium text-zinc-400 hover:text-zinc-200 bg-zinc-800 hover:bg-zinc-700 border border-zinc-700 rounded-md transition-all duration-150 ease-out"
    >
      {copied ? (
        <>
          <Check className="w-3 h-3 text-emerald-400" />
          <span className="text-emerald-400">Copied</span>
        </>
      ) : (
        <>
          <Copy className="w-3 h-3" />
          {label}
        </>
      )}
    </button>
  )
}

export default function ResponseViewer({ response, curl }) {
  const [expanded, setExpanded] = useState(true)

  if (!response) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-zinc-500">
        <div className="w-12 h-12 rounded-xl bg-zinc-800/50 flex items-center justify-center mb-3">
          <AlertCircle className="w-5 h-5" />
        </div>
        <p className="text-sm">Send a request to see the response</p>
      </div>
    )
  }

  const jsonString = JSON.stringify(response.data, null, 2)
  const lineCount = jsonString.split('\n').length
  const isLarge = lineCount > COLLAPSE_THRESHOLD

  return (
    <div className="space-y-3">
      {/* Header row: status + duration + copy buttons */}
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-3">
          <StatusBadge status={response.status} />
          {response.duration !== undefined && (
            <span className="text-xs text-zinc-500 font-mono">
              {formatDuration(response.duration)}
            </span>
          )}
        </div>

        <div className="flex items-center gap-2">
          <CopyButton text={jsonString} label="JSON" />
          {curl && <CopyButton text={curl} label="cURL" />}
        </div>
      </div>

      {/* Error message */}
      {response.error && (
        <div className="flex items-start gap-2 px-3 py-2.5 bg-rose-500/10 border border-rose-500/20 rounded-lg">
          <AlertCircle className="w-4 h-4 text-rose-400 flex-shrink-0 mt-0.5" />
          <p className="text-sm text-rose-300">{response.error}</p>
        </div>
      )}

      {/* JSON body */}
      <div className="relative bg-zinc-900 border border-zinc-800 rounded-lg overflow-hidden">
        {isLarge && (
          <button
            onClick={() => setExpanded(!expanded)}
            className="flex items-center gap-1.5 w-full px-4 py-2 text-xs font-medium text-zinc-400 hover:text-zinc-200 bg-zinc-800/50 border-b border-zinc-800 transition-colors duration-150 ease-out"
          >
            {expanded ? (
              <>
                <ChevronUp className="w-3.5 h-3.5" />
                Collapse ({lineCount} lines)
              </>
            ) : (
              <>
                <ChevronDown className="w-3.5 h-3.5" />
                Expand ({lineCount} lines)
              </>
            )}
          </button>
        )}

        <div
          className={`overflow-auto ${!expanded && isLarge ? 'max-h-0 p-0' : 'p-4'}`}
          style={!expanded && isLarge ? { maxHeight: 0, padding: 0 } : { maxHeight: '60vh' }}
        >
          <pre
            className="text-xs font-mono leading-relaxed whitespace-pre"
            dangerouslySetInnerHTML={{ __html: syntaxHighlight(jsonString) }}
          />
        </div>
      </div>
    </div>
  )
}
