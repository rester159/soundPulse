import { TrendingUp, TrendingDown } from 'lucide-react'

function confidenceColor(confidence) {
  if (confidence >= 0.7) return { text: 'text-violet-400', bg: 'bg-violet-500' }
  if (confidence >= 0.4) return { text: 'text-amber-400', bg: 'bg-amber-500' }
  return { text: 'text-zinc-400', bg: 'bg-zinc-500' }
}

function confidenceLabel(confidence) {
  if (confidence >= 0.7) return 'High'
  if (confidence >= 0.4) return 'Medium'
  return 'Low'
}

export default function PredictionCard({ prediction, onClick }) {
  if (!prediction) return null

  const entity = prediction.entity || prediction
  const predictedChange = prediction.predicted_change ?? prediction.change ?? 0
  const confidence = prediction.confidence ?? 0
  const topSignal =
    prediction.top_signal || prediction.contributing_signal || null
  const isPositive = predictedChange >= 0
  const colors = confidenceColor(confidence)

  return (
    <button
      onClick={() => onClick?.(prediction)}
      className="group w-full text-left rounded-lg border border-zinc-800 bg-zinc-900 p-4 hover:border-violet-500/40 hover:shadow-[0_0_16px_rgba(139,92,246,0.08)] transition-all duration-150 ease-out cursor-pointer"
    >
      {/* Top row: name + change */}
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="min-w-0">
          <div className="text-sm font-medium text-zinc-100 truncate">
            {entity.name || entity.title || 'Unknown'}
          </div>
          {entity.artist?.name && (
            <div className="text-xs text-zinc-500 truncate mt-0.5">
              {entity.artist.name}
            </div>
          )}
        </div>
        <div
          className={`flex items-center gap-1 shrink-0 font-mono text-sm font-semibold ${isPositive ? 'text-emerald-400' : 'text-rose-400'}`}
        >
          {isPositive ? (
            <TrendingUp className="w-3.5 h-3.5" />
          ) : (
            <TrendingDown className="w-3.5 h-3.5" />
          )}
          {isPositive ? '+' : ''}
          {Number(predictedChange).toFixed(1)}%
        </div>
      </div>

      {/* Confidence bar */}
      <div className="mb-2">
        <div className="flex items-center justify-between mb-1">
          <span className="text-xs text-zinc-500">Confidence</span>
          <span className={`text-xs font-medium ${colors.text}`}>
            {confidenceLabel(confidence)} ({(confidence * 100).toFixed(0)}%)
          </span>
        </div>
        <div className="w-full h-2 bg-zinc-800 rounded-full overflow-hidden">
          <div
            className="h-full rounded-full transition-all duration-500 ease-out"
            style={{
              width: `${Math.min(100, Math.max(0, confidence * 100))}%`,
              background:
                confidence >= 0.7
                  ? 'linear-gradient(90deg, #52525b, #8b5cf6)'
                  : confidence >= 0.4
                    ? 'linear-gradient(90deg, #52525b, #f59e0b)'
                    : 'linear-gradient(90deg, #52525b, #71717a)',
            }}
          />
        </div>
      </div>

      {/* Top signal badge */}
      {topSignal && (
        <div className="mt-3">
          <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-mono font-medium bg-zinc-800 text-zinc-300 border border-zinc-700">
            {topSignal}
          </span>
        </div>
      )}
    </button>
  )
}
