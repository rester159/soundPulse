import { useEffect } from 'react'

function FieldLabel({ name, required }) {
  return (
    <label className="block text-xs font-medium text-zinc-400 mb-1.5">
      {name}
      {required && <span className="text-red-400 ml-0.5">*</span>}
    </label>
  )
}

export default function RequestBuilder({ endpoint, values, onChange }) {
  const params = endpoint?.params || []

  useEffect(() => {
    if (!endpoint) return
    const defaults = {}
    for (const param of params) {
      if (param.default !== undefined) {
        defaults[param.name] = param.default
      }
    }
    onChange(defaults)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [endpoint?.path, endpoint?.method])

  function handleChange(name, value) {
    onChange({ ...values, [name]: value })
  }

  if (!endpoint || params.length === 0) {
    return (
      <div className="text-sm text-zinc-500 italic py-4">
        No parameters for this endpoint.
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {params.map((param) => {
        const currentValue = values[param.name] ?? param.default ?? ''

        if (param.type === 'enum') {
          return (
            <div key={param.name}>
              <FieldLabel name={param.name} required={param.required} />
              <select
                value={currentValue}
                onChange={(e) => handleChange(param.name, e.target.value)}
                className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm text-zinc-100 focus:outline-none focus:ring-2 focus:ring-violet-500/50 focus:border-violet-500 transition-all duration-150 ease-out appearance-none cursor-pointer"
              >
                {!param.required && <option value="">-- none --</option>}
                {(param.options || []).map((opt) => (
                  <option key={opt} value={opt}>
                    {opt}
                  </option>
                ))}
              </select>
            </div>
          )
        }

        if (param.type === 'boolean') {
          return (
            <div key={param.name}>
              <label className="flex items-center gap-2.5 cursor-pointer group">
                <input
                  type="checkbox"
                  checked={!!currentValue}
                  onChange={(e) => handleChange(param.name, e.target.checked)}
                  className="w-4 h-4 rounded bg-zinc-800 border-zinc-700 text-violet-500 focus:ring-violet-500/50 focus:ring-offset-0 cursor-pointer"
                />
                <span className="text-xs font-medium text-zinc-400 group-hover:text-zinc-300 transition-colors duration-150 ease-out">
                  {param.name}
                  {param.required && <span className="text-red-400 ml-0.5">*</span>}
                </span>
              </label>
            </div>
          )
        }

        if (param.type === 'number') {
          return (
            <div key={param.name}>
              <FieldLabel name={param.name} required={param.required} />
              <input
                type="number"
                value={currentValue}
                onChange={(e) => {
                  const val = e.target.value === '' ? '' : Number(e.target.value)
                  handleChange(param.name, val)
                }}
                min={param.min}
                max={param.max}
                step={param.step || 1}
                placeholder={param.placeholder || ''}
                className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm text-zinc-100 placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-violet-500/50 focus:border-violet-500 transition-all duration-150 ease-out font-mono"
              />
            </div>
          )
        }

        return (
          <div key={param.name}>
            <FieldLabel name={param.name} required={param.required} />
            <input
              type="text"
              value={currentValue}
              onChange={(e) => handleChange(param.name, e.target.value)}
              placeholder={param.placeholder || ''}
              className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm text-zinc-100 placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-violet-500/50 focus:border-violet-500 transition-all duration-150 ease-out font-mono"
            />
            {param.type === 'path' && (
              <p className="text-[11px] text-zinc-500 mt-1">
                Substituted into the URL path
              </p>
            )}
          </div>
        )
      })}
    </div>
  )
}
