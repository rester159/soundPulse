export function formatNumber(n) {
  if (n === null || n === undefined) return '-'
  if (typeof n !== 'number') n = Number(n)
  if (isNaN(n)) return '-'

  if (Math.abs(n) >= 1_000_000) {
    return (n / 1_000_000).toFixed(1).replace(/\.0$/, '') + 'M'
  }
  if (Math.abs(n) >= 1_000) {
    return (n / 1_000).toFixed(1).replace(/\.0$/, '') + 'K'
  }
  return n.toString()
}

export function formatDate(iso) {
  if (!iso) return '-'
  const date = new Date(iso)
  const now = new Date()
  const diffMs = now - date
  const diffSec = Math.floor(diffMs / 1000)
  const diffMin = Math.floor(diffSec / 60)
  const diffHour = Math.floor(diffMin / 60)
  const diffDay = Math.floor(diffHour / 24)

  if (diffSec < 60) return `${diffSec}s ago`
  if (diffMin < 60) return `${diffMin}m ago`
  if (diffHour < 24) return `${diffHour}h ago`
  if (diffDay < 30) return `${diffDay}d ago`

  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

export function formatDuration(ms) {
  if (ms === null || ms === undefined) return '-'
  if (ms < 1000) return `${Math.round(ms)}ms`
  return `${(ms / 1000).toFixed(1)}s`
}

export function formatScore(score, delta) {
  if (score === null || score === undefined) return '-'
  const formatted = Number(score).toFixed(1)
  if (delta !== undefined && delta !== null) {
    const arrow = delta > 0 ? '\u2191' : delta < 0 ? '\u2193' : ''
    return `${formatted} ${arrow}`
  }
  return formatted
}

export function getStatusColor(code) {
  if (code >= 200 && code < 300) return 'text-green-400'
  if (code >= 400 && code < 500) return 'text-yellow-400'
  if (code >= 500) return 'text-red-400'
  return 'text-zinc-400'
}
