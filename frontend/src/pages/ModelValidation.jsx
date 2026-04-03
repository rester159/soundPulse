import { useState } from 'react'
import { FlaskConical, TrendingDown, Target, Percent, Activity, Play, RefreshCw } from 'lucide-react'
import {
  LineChart, Line, BarChart, Bar, ComposedChart, Area,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer
} from 'recharts'
import { useBacktestResults, useBacktestGenres, useRunBacktest } from '../hooks/useSoundPulse'

function MetricCard({ label, value, icon: Icon, color, subtitle }) {
  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-4">
      <div className="flex items-center gap-2 mb-1">
        <Icon size={16} className={color} />
        <span className="text-sm text-zinc-400">{label}</span>
      </div>
      <div className="text-2xl font-bold text-zinc-100">
        {value != null ? value : '—'}
      </div>
      {subtitle && <div className="text-xs text-zinc-500 mt-1">{subtitle}</div>}
    </div>
  )
}

export default function ModelValidation() {
  const [entityType, setEntityType] = useState(null)
  const [genre, setGenre] = useState('')
  const [horizon, setHorizon] = useState('7d')

  const params = { horizon, ...(entityType && { entity_type: entityType }), ...(genre && { genre }) }
  const { data: results, isLoading, refetch } = useBacktestResults(params)
  const { data: genreData } = useBacktestGenres(params)
  const runBacktest = useRunBacktest()

  const timeline = results?.data?.timeline || []
  const summary = results?.data?.summary || {}
  const genres = genreData?.data || []

  const handleRunBacktest = () => {
    runBacktest.mutate({
      body: { months: 24, horizon, entity_type: entityType, genre: genre || null }
    }, { onSuccess: () => setTimeout(refetch, 5000) })
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <FlaskConical size={28} className="text-violet-400" />
          <div>
            <h1 className="text-2xl font-bold text-zinc-100">Model Validation</h1>
            <p className="text-sm text-zinc-500">Prediction accuracy vs. historical reality</p>
          </div>
        </div>
        <button
          onClick={handleRunBacktest}
          disabled={runBacktest.isPending}
          className="flex items-center gap-2 px-4 py-2 bg-violet-600 hover:bg-violet-500 disabled:opacity-50 rounded-lg text-sm font-medium transition-colors"
        >
          <RefreshCw size={14} className={runBacktest.isPending ? 'animate-spin' : ''} />
          {runBacktest.isPending ? 'Running...' : 'Run Backtest'}
        </button>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-3 flex-wrap">
        <div className="flex rounded-lg border border-zinc-700 overflow-hidden">
          {[null, 'track', 'artist'].map(t => (
            <button
              key={t || 'all'}
              onClick={() => setEntityType(t)}
              className={`px-3 py-1.5 text-sm transition-colors ${
                entityType === t ? 'bg-violet-600 text-white' : 'bg-zinc-800 text-zinc-400 hover:bg-zinc-700'
              }`}
            >
              {t ? t.charAt(0).toUpperCase() + t.slice(1) + 's' : 'All'}
            </button>
          ))}
        </div>

        <input
          type="text"
          value={genre}
          onChange={e => setGenre(e.target.value)}
          placeholder="Genre filter (e.g., electronic.house)"
          className="px-3 py-1.5 text-sm bg-zinc-800 border border-zinc-700 rounded-lg text-zinc-300 placeholder:text-zinc-600 w-64"
        />

        <div className="flex rounded-lg border border-zinc-700 overflow-hidden">
          {['7d', '14d', '30d'].map(h => (
            <button
              key={h}
              onClick={() => setHorizon(h)}
              className={`px-3 py-1.5 text-sm transition-colors ${
                horizon === h ? 'bg-violet-600 text-white' : 'bg-zinc-800 text-zinc-400 hover:bg-zinc-700'
              }`}
            >
              {h}
            </button>
          ))}
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          label="Mean Absolute Error"
          value={summary.overall_mae != null ? summary.overall_mae.toFixed(3) : null}
          icon={TrendingDown}
          color="text-rose-400"
          subtitle="Lower is better"
        />
        <MetricCard
          label="Precision"
          value={summary.overall_precision != null ? (summary.overall_precision * 100).toFixed(1) + '%' : null}
          icon={Target}
          color="text-blue-400"
          subtitle="Of predicted breakouts, how many were real"
        />
        <MetricCard
          label="Recall"
          value={summary.overall_recall != null ? (summary.overall_recall * 100).toFixed(1) + '%' : null}
          icon={Percent}
          color="text-emerald-400"
          subtitle="Of actual breakouts, how many we caught"
        />
        <MetricCard
          label="F1 Score"
          value={summary.overall_f1 != null ? (summary.overall_f1 * 100).toFixed(1) + '%' : null}
          icon={Activity}
          color="text-violet-400"
          subtitle={`${summary.total_samples || 0} samples, ${summary.total_positives || 0} breakouts`}
        />
      </div>

      {/* Loading state */}
      {isLoading && (
        <div className="text-center py-12 text-zinc-500">Loading backtest results...</div>
      )}

      {/* Empty state */}
      {!isLoading && timeline.length === 0 && (
        <div className="text-center py-12 border border-zinc-800 rounded-lg bg-zinc-900">
          <FlaskConical size={48} className="mx-auto text-zinc-600 mb-4" />
          <h3 className="text-lg font-medium text-zinc-300">No backtest results yet</h3>
          <p className="text-sm text-zinc-500 mt-1 mb-4">
            Click "Run Backtest" to evaluate the model against historical data
          </p>
        </div>
      )}

      {/* Charts */}
      {timeline.length > 0 && (
        <>
          {/* Primary chart: Predicted vs Actual */}
          <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-6">
            <h3 className="text-lg font-semibold text-zinc-200 mb-4">
              Predicted Probability vs. Actual Breakout Rate
            </h3>
            <ResponsiveContainer width="100%" height={320}>
              <ComposedChart data={timeline}>
                <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
                <XAxis
                  dataKey="evaluation_date"
                  tick={{ fill: '#71717a', fontSize: 11 }}
                  tickFormatter={d => d.slice(5)}
                />
                <YAxis tick={{ fill: '#71717a', fontSize: 11 }} domain={[0, 1]} />
                <Tooltip
                  contentStyle={{ backgroundColor: '#18181b', border: '1px solid #3f3f46', borderRadius: 8 }}
                  labelStyle={{ color: '#a1a1aa' }}
                />
                <Legend />
                <Area
                  type="monotone"
                  dataKey="predicted_avg"
                  fill="#8b5cf6"
                  fillOpacity={0.1}
                  stroke="none"
                  name="Predicted (area)"
                />
                <Line
                  type="monotone"
                  dataKey="predicted_avg"
                  stroke="#8b5cf6"
                  strokeWidth={2}
                  dot={{ r: 3 }}
                  name="Predicted Avg"
                />
                <Line
                  type="monotone"
                  dataKey="actual_rate"
                  stroke="#34d399"
                  strokeWidth={2}
                  dot={{ r: 3 }}
                  name="Actual Rate"
                />
              </ComposedChart>
            </ResponsiveContainer>
          </div>

          {/* Two-column charts */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Accuracy Metrics Over Time */}
            <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-6">
              <h3 className="text-lg font-semibold text-zinc-200 mb-4">
                Accuracy Metrics Over Time
              </h3>
              <ResponsiveContainer width="100%" height={280}>
                <LineChart data={timeline}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
                  <XAxis
                    dataKey="evaluation_date"
                    tick={{ fill: '#71717a', fontSize: 11 }}
                    tickFormatter={d => d.slice(5)}
                  />
                  <YAxis tick={{ fill: '#71717a', fontSize: 11 }} domain={[0, 1]} />
                  <Tooltip
                    contentStyle={{ backgroundColor: '#18181b', border: '1px solid #3f3f46', borderRadius: 8 }}
                    labelStyle={{ color: '#a1a1aa' }}
                  />
                  <Legend />
                  <Line type="monotone" dataKey="precision" stroke="#60a5fa" strokeWidth={2} dot={false} name="Precision" />
                  <Line type="monotone" dataKey="recall" stroke="#34d399" strokeWidth={2} dot={false} name="Recall" />
                  <Line type="monotone" dataKey="f1" stroke="#a78bfa" strokeWidth={2} dot={false} name="F1 Score" />
                </LineChart>
              </ResponsiveContainer>
            </div>

            {/* Monthly Error */}
            <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-6">
              <h3 className="text-lg font-semibold text-zinc-200 mb-4">
                Monthly Prediction Error (MAE)
              </h3>
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={timeline}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
                  <XAxis
                    dataKey="evaluation_date"
                    tick={{ fill: '#71717a', fontSize: 11 }}
                    tickFormatter={d => d.slice(5)}
                  />
                  <YAxis tick={{ fill: '#71717a', fontSize: 11 }} domain={[0, 'auto']} />
                  <Tooltip
                    contentStyle={{ backgroundColor: '#18181b', border: '1px solid #3f3f46', borderRadius: 8 }}
                    labelStyle={{ color: '#a1a1aa' }}
                  />
                  <Bar dataKey="mae" fill="#f87171" radius={[4, 4, 0, 0]} name="MAE" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Genre Performance Table */}
          {genres.length > 0 && (
            <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-6">
              <h3 className="text-lg font-semibold text-zinc-200 mb-4">
                Genre Performance Breakdown
              </h3>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-zinc-400 border-b border-zinc-800">
                      <th className="text-left py-2 px-3">Genre</th>
                      <th className="text-right py-2 px-3">Samples</th>
                      <th className="text-right py-2 px-3">MAE</th>
                      <th className="text-right py-2 px-3">Precision</th>
                      <th className="text-right py-2 px-3">Recall</th>
                      <th className="text-right py-2 px-3">F1</th>
                    </tr>
                  </thead>
                  <tbody>
                    {genres.map(g => (
                      <tr key={g.genre} className="border-b border-zinc-800/50 hover:bg-zinc-800/30">
                        <td className="py-2 px-3 text-zinc-200 font-medium">{g.genre}</td>
                        <td className="py-2 px-3 text-right text-zinc-400">{g.sample_count}</td>
                        <td className="py-2 px-3 text-right text-zinc-300">{g.mae?.toFixed(3) ?? '—'}</td>
                        <td className="py-2 px-3 text-right text-zinc-300">
                          {g.precision != null ? (g.precision * 100).toFixed(1) + '%' : '—'}
                        </td>
                        <td className="py-2 px-3 text-right text-zinc-300">
                          {g.recall != null ? (g.recall * 100).toFixed(1) + '%' : '—'}
                        </td>
                        <td className="py-2 px-3 text-right text-zinc-300">
                          {g.f1 != null ? (g.f1 * 100).toFixed(1) + '%' : '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}
