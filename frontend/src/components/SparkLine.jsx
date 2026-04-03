export default function SparkLine({
  data = [],
  color,
  width = 120,
  height = 32,
}) {
  if (!data || data.length < 2) {
    return (
      <svg
        width={width}
        height={height}
        viewBox={`0 0 ${width} ${height}`}
        className="inline-block"
      >
        <line
          x1={0}
          y1={height / 2}
          x2={width}
          y2={height / 2}
          stroke="#3f3f46"
          strokeWidth={1.5}
          strokeDasharray="4 3"
        />
      </svg>
    )
  }

  const isUptrend = data[data.length - 1] > data[0]
  const strokeColor = color || (isUptrend ? '#10b981' : '#f43f5e')

  const min = Math.min(...data)
  const max = Math.max(...data)
  const range = max - min || 1

  const padding = 2
  const chartWidth = width - padding * 2
  const chartHeight = height - padding * 2

  const points = data.map((value, i) => ({
    x: padding + (i / (data.length - 1)) * chartWidth,
    y: padding + chartHeight - ((value - min) / range) * chartHeight,
  }))

  // Build smooth bezier curve path
  let d = `M ${points[0].x},${points[0].y}`
  for (let i = 0; i < points.length - 1; i++) {
    const curr = points[i]
    const next = points[i + 1]
    const cpx = (curr.x + next.x) / 2
    d += ` C ${cpx},${curr.y} ${cpx},${next.y} ${next.x},${next.y}`
  }

  // Build gradient fill path
  const fillD =
    d +
    ` L ${points[points.length - 1].x},${height} L ${points[0].x},${height} Z`

  const gradientId = `spark-grad-${Math.random().toString(36).slice(2, 8)}`

  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      className="inline-block"
    >
      <defs>
        <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={strokeColor} stopOpacity={0.25} />
          <stop offset="100%" stopColor={strokeColor} stopOpacity={0} />
        </linearGradient>
      </defs>
      <path d={fillD} fill={`url(#${gradientId})`} />
      <path
        d={d}
        fill="none"
        stroke={strokeColor}
        strokeWidth={1.5}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      {/* Endpoint dot */}
      <circle
        cx={points[points.length - 1].x}
        cy={points[points.length - 1].y}
        r={2}
        fill={strokeColor}
      />
    </svg>
  )
}
