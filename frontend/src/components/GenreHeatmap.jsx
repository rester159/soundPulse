function momentumToColor(momentum) {
  // Scale from cool (blue/cyan) to hot (rose/red)
  // momentum expected 0-100
  const value = Math.min(100, Math.max(0, momentum ?? 50))

  if (value >= 80) return { bg: 'bg-rose-500/20', border: 'border-rose-500/30', text: 'text-rose-400', dot: 'bg-rose-400' }
  if (value >= 65) return { bg: 'bg-orange-500/15', border: 'border-orange-500/25', text: 'text-orange-400', dot: 'bg-orange-400' }
  if (value >= 50) return { bg: 'bg-amber-500/15', border: 'border-amber-500/20', text: 'text-amber-400', dot: 'bg-amber-400' }
  if (value >= 35) return { bg: 'bg-emerald-500/10', border: 'border-emerald-500/20', text: 'text-emerald-400', dot: 'bg-emerald-400' }
  if (value >= 20) return { bg: 'bg-cyan-500/10', border: 'border-cyan-500/20', text: 'text-cyan-400', dot: 'bg-cyan-400' }
  return { bg: 'bg-blue-500/10', border: 'border-blue-500/15', text: 'text-blue-400', dot: 'bg-blue-400' }
}

function SkeletonCell() {
  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-4">
      <div className="h-4 w-20 bg-zinc-800 rounded skeleton mb-2" />
      <div className="h-5 w-10 bg-zinc-800 rounded skeleton" />
    </div>
  )
}

export default function GenreHeatmap({ genres = [], isLoading = false, onGenreClick }) {
  if (isLoading) {
    return (
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
        {Array.from({ length: 12 }).map((_, i) => (
          <SkeletonCell key={i} />
        ))}
      </div>
    )
  }

  if (genres.length === 0) {
    return (
      <div className="text-center text-sm text-zinc-500 py-8">
        No genre data available
      </div>
    )
  }

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
      {genres.map((genre) => {
        const momentum = genre.momentum ?? genre.score ?? 50
        const colors = momentumToColor(momentum)

        return (
          <button
            key={genre.id || genre.name}
            onClick={() => onGenreClick?.(genre)}
            className={`rounded-lg border ${colors.border} ${colors.bg} p-4 text-left transition-all duration-150 ease-out hover:scale-[1.02] hover:shadow-lg cursor-pointer`}
          >
            <div className="flex items-center gap-2 mb-1.5">
              <span className={`w-1.5 h-1.5 rounded-full ${colors.dot}`} />
              <span className="text-sm font-medium text-zinc-200 truncate">
                {genre.name || genre.label || genre.id}
              </span>
            </div>
            <div className={`font-mono text-lg font-semibold ${colors.text}`}>
              {Number(momentum).toFixed(0)}
            </div>
            <div className="text-[10px] text-zinc-500 mt-0.5">momentum</div>
          </button>
        )
      })}
    </div>
  )
}
