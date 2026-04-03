import { useEffect, useState } from 'react'

function getStatus(updatedAt) {
  if (!updatedAt) return { label: 'Unknown', color: 'bg-zinc-500', textColor: 'text-zinc-400' }

  const now = Date.now()
  const diffMs = now - new Date(updatedAt).getTime()
  const diffMin = Math.floor(diffMs / 60_000)
  const diffHr = Math.floor(diffMs / 3_600_000)

  if (diffMin < 5) {
    const label = diffMin < 1 ? 'Updated just now' : `Updated ${diffMin}m ago`
    return { label, color: 'bg-emerald-400', textColor: 'text-emerald-400' }
  }

  if (diffMin < 60) {
    return {
      label: `Updated ${diffMin}m ago`,
      color: 'bg-amber-400',
      textColor: 'text-amber-400',
    }
  }

  return {
    label: `Stale (${diffHr}h ago)`,
    color: 'bg-rose-400',
    textColor: 'text-rose-400',
  }
}

export default function FreshnessIndicator({ updatedAt }) {
  const [status, setStatus] = useState(() => getStatus(updatedAt))

  // Recalculate every 30s
  useEffect(() => {
    setStatus(getStatus(updatedAt))
    const interval = setInterval(() => {
      setStatus(getStatus(updatedAt))
    }, 30_000)
    return () => clearInterval(interval)
  }, [updatedAt])

  return (
    <div className="inline-flex items-center gap-1.5">
      <span className={`w-1.5 h-1.5 rounded-full ${status.color}`} />
      <span className={`text-xs ${status.textColor}`}>{status.label}</span>
    </div>
  )
}
