import { useState, useEffect } from 'react'
import {
  Settings as SettingsIcon, User, Wrench, Loader2, Save, Check,
  AlertCircle, CheckCircle2, Plus, X, Bot, Inbox, ThumbsUp, ThumbsDown,
} from 'lucide-react'
import { useQueryClient } from '@tanstack/react-query'
import {
  useCeoProfile, useUpdateCeoProfile,
  useAgents, useTools, useAgentToolGrants,
  useCreateGrant, useDeleteGrant,
  useCeoDecisions, useApproveCeoDecision, useRejectCeoDecision,
} from '../hooks/useSoundPulse'

const SECTIONS = [
  { id: 'decisions', label: 'Pending Decisions', icon: Inbox },
  { id: 'ceo',       label: 'CEO Profile',      icon: User },
  { id: 'tools',     label: 'Tools & Agents',   icon: Wrench },
]

// ─── CEO Profile section ─────────────────────────────────────────────────

function CeoProfileSection() {
  const { data, isLoading } = useCeoProfile()
  const update = useUpdateCeoProfile()
  const qc = useQueryClient()
  const [form, setForm] = useState({})
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    if (data?.data) {
      setForm({
        name: data.data.name || '',
        email: data.data.email || '',
        phone: data.data.phone || '',
        telegram_handle: data.data.telegram_handle || '',
        telegram_chat_id: data.data.telegram_chat_id || '',
        slack_channel: data.data.slack_channel || '',
        preferred_channel: data.data.preferred_channel || 'email',
        escalation_severity_threshold: data.data.escalation_severity_threshold || 'medium',
        timezone: data.data.timezone || 'UTC',
      })
    }
  }, [data])

  const handleChange = (k, v) => setForm(prev => ({ ...prev, [k]: v }))

  const handleSave = async () => {
    await update.mutateAsync({ body: form })
    setSaved(true)
    setTimeout(() => setSaved(false), 2000)
    qc.invalidateQueries({ queryKey: ['admin', 'ceo-profile'] })
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20 text-zinc-500">
        <Loader2 size={20} className="animate-spin mr-2" /> Loading CEO profile...
      </div>
    )
  }

  return (
    <div className="max-w-2xl space-y-6">
      <div>
        <h2 className="text-lg font-bold text-zinc-100 mb-1">CEO Profile</h2>
        <p className="text-xs text-zinc-500">
          Contact info used by the CEO Action Agent to escalate critical
          decisions (artist creation, paid spend, brand pivots).
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Field label="Name" value={form.name} onChange={v => handleChange('name', v)} />
        <Field label="Email" type="email" value={form.email} onChange={v => handleChange('email', v)} />
        <Field label="Phone" type="tel" value={form.phone} onChange={v => handleChange('phone', v)} />
        <Field label="Telegram handle" placeholder="@yourhandle" value={form.telegram_handle} onChange={v => handleChange('telegram_handle', v)} />
        <Field label="Telegram chat ID" value={form.telegram_chat_id} onChange={v => handleChange('telegram_chat_id', v)} />
        <Field label="Slack channel" placeholder="#alerts" value={form.slack_channel} onChange={v => handleChange('slack_channel', v)} />

        <div>
          <label className="text-xs text-zinc-500 block mb-1">Preferred channel</label>
          <select
            value={form.preferred_channel || 'email'}
            onChange={e => handleChange('preferred_channel', e.target.value)}
            className="w-full bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-2 text-sm text-zinc-100"
          >
            <option value="email">Email</option>
            <option value="phone">Phone</option>
            <option value="telegram">Telegram</option>
            <option value="slack">Slack</option>
          </select>
        </div>

        <div>
          <label className="text-xs text-zinc-500 block mb-1">Min escalation severity</label>
          <select
            value={form.escalation_severity_threshold || 'medium'}
            onChange={e => handleChange('escalation_severity_threshold', e.target.value)}
            className="w-full bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-2 text-sm text-zinc-100"
          >
            <option value="low">Low (everything)</option>
            <option value="medium">Medium</option>
            <option value="high">High</option>
            <option value="critical">Critical only</option>
          </select>
        </div>

        <Field label="Timezone" placeholder="America/New_York" value={form.timezone} onChange={v => handleChange('timezone', v)} />
      </div>

      <button
        onClick={handleSave}
        disabled={update.isPending}
        className="flex items-center gap-2 px-4 py-2 bg-violet-600 hover:bg-violet-700 disabled:opacity-50 text-white rounded-lg text-sm font-medium"
      >
        {update.isPending ? <Loader2 size={14} className="animate-spin" /> : saved ? <Check size={14} /> : <Save size={14} />}
        {saved ? 'Saved' : 'Save profile'}
      </button>
    </div>
  )
}

function Field({ label, value, onChange, type = 'text', placeholder }) {
  return (
    <div>
      <label className="text-xs text-zinc-500 block mb-1">{label}</label>
      <input
        type={type}
        value={value || ''}
        onChange={e => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-2 text-sm text-zinc-100 placeholder-zinc-600"
      />
    </div>
  )
}

// ─── Tools & Agents section ──────────────────────────────────────────────

const STATUS_COLORS = {
  active:               'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
  planned:              'bg-amber-500/15 text-amber-300 border-amber-500/30',
  pending_credentials:  'bg-amber-500/15 text-amber-300 border-amber-500/30',
  blocked:              'bg-rose-500/15 text-rose-300 border-rose-500/30',
  deprecated:           'bg-rose-500/15 text-rose-300 border-rose-500/30',
  requires_audit:       'bg-amber-500/15 text-amber-300 border-amber-500/30',
  requires_app_review:  'bg-amber-500/15 text-amber-300 border-amber-500/30',
}

function StatusBadge({ status }) {
  const cls = STATUS_COLORS[status] || 'bg-zinc-800 text-zinc-400 border-zinc-700'
  return (
    <span className={`inline-flex items-center px-1.5 py-0.5 rounded border text-[9px] font-semibold uppercase tracking-wider ${cls}`}>
      {status?.replace(/_/g, ' ')}
    </span>
  )
}

function ToolsAndAgentsSection() {
  const [pivot, setPivot] = useState('by_tool')
  const [filter, setFilter] = useState('')
  const { data: tools, isLoading: toolsLoading } = useTools()
  const { data: agents, isLoading: agentsLoading } = useAgents()
  const { data: grants, isLoading: grantsLoading, refetch: refetchGrants } = useAgentToolGrants(pivot)
  const createGrant = useCreateGrant()
  const deleteGrant = useDeleteGrant()
  const qc = useQueryClient()

  const handleGrant = async (agent_id, tool_id) => {
    await createGrant.mutateAsync({ body: { agent_id, tool_id } })
    qc.invalidateQueries({ queryKey: ['admin', 'agent-tool-grants'] })
  }

  const handleRevoke = async (agent_id, tool_id) => {
    await deleteGrant.mutateAsync({ agent_id, tool_id })
    qc.invalidateQueries({ queryKey: ['admin', 'agent-tool-grants'] })
  }

  if (toolsLoading || agentsLoading || grantsLoading) {
    return (
      <div className="flex items-center justify-center py-20 text-zinc-500">
        <Loader2 size={20} className="animate-spin mr-2" /> Loading registry...
      </div>
    )
  }

  const toolsList = tools?.data?.tools || []
  const agentsList = agents?.data?.agents || []
  const grantsData = grants?.data?.data || []

  // Filter
  const filterLower = filter.toLowerCase()
  const filteredGrants = filter
    ? grantsData.filter(item => {
        if (pivot === 'by_tool') {
          return item.tool_name?.toLowerCase().includes(filterLower) ||
                 item.category?.toLowerCase().includes(filterLower) ||
                 item.agents?.some(a => a.agent_name?.toLowerCase().includes(filterLower))
        } else {
          return item.agent_name?.toLowerCase().includes(filterLower) ||
                 item.tools?.some(t => t.tool_name?.toLowerCase().includes(filterLower))
        }
      })
    : grantsData

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-bold text-zinc-100 mb-1">Tools & Agents</h2>
        <p className="text-xs text-zinc-500">
          {agentsList.length} agents wired to {toolsList.length} tools.
          Same data, two pivots.
        </p>
      </div>

      {/* Pivot toggle + filter */}
      <div className="flex items-center gap-3">
        <div className="flex bg-zinc-900 border border-zinc-800 rounded-lg p-1">
          <button
            onClick={() => setPivot('by_tool')}
            className={`px-3 py-1 text-xs rounded font-medium transition-colors ${
              pivot === 'by_tool' ? 'bg-violet-600/30 text-violet-200 border border-violet-500/50' : 'text-zinc-500 hover:text-zinc-300'
            }`}
          >
            By tool
          </button>
          <button
            onClick={() => setPivot('by_agent')}
            className={`px-3 py-1 text-xs rounded font-medium transition-colors ${
              pivot === 'by_agent' ? 'bg-violet-600/30 text-violet-200 border border-violet-500/50' : 'text-zinc-500 hover:text-zinc-300'
            }`}
          >
            By agent
          </button>
        </div>

        <input
          type="text"
          value={filter}
          onChange={e => setFilter(e.target.value)}
          placeholder="Filter..."
          className="flex-1 bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-1.5 text-xs text-zinc-100 placeholder-zinc-600"
        />
      </div>

      {/* By tool view */}
      {pivot === 'by_tool' && (
        <div className="space-y-3">
          {filteredGrants.map(item => {
            const tool = toolsList.find(t => t.id === item.tool_id)
            return (
              <div key={item.tool_id} className="bg-zinc-900 border border-zinc-800 rounded-lg p-4">
                <div className="flex items-start justify-between gap-3 mb-2">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap mb-1">
                      <Wrench size={14} className="text-violet-400 flex-shrink-0" />
                      <span className="font-bold text-zinc-100 text-sm">{item.tool_name}</span>
                      <span className="text-[10px] text-zinc-600 uppercase">{item.category}</span>
                      <StatusBadge status={item.status} />
                      {item.automation_class && (
                        <span className="text-[9px] px-1.5 py-0.5 bg-zinc-800 text-zinc-400 rounded border border-zinc-700">
                          Class {item.automation_class}
                        </span>
                      )}
                    </div>
                    {tool?.description && (
                      <p className="text-[11px] text-zinc-500 mb-2">{tool.description}</p>
                    )}
                    {tool?.credential_env_vars?.length > 0 && (
                      <div className="flex items-center gap-1 mb-2">
                        {tool.credentials_configured ? (
                          <CheckCircle2 size={10} className="text-emerald-400" />
                        ) : (
                          <AlertCircle size={10} className="text-rose-400" />
                        )}
                        <span className="text-[10px] text-zinc-500 font-mono">
                          {tool.credential_env_vars.join(', ')}
                        </span>
                      </div>
                    )}
                  </div>
                </div>

                <div className="flex flex-wrap gap-1.5 pt-2 border-t border-zinc-800/60">
                  {item.agents.map(a => (
                    <span
                      key={a.agent_id}
                      className="group inline-flex items-center gap-1 px-2 py-0.5 bg-violet-600/15 text-violet-200 text-[10px] rounded border border-violet-500/30"
                    >
                      <Bot size={9} />
                      {a.agent_name}
                      <button
                        onClick={() => handleRevoke(a.agent_id, item.tool_id)}
                        className="opacity-0 group-hover:opacity-100 hover:text-rose-300"
                        title="Revoke"
                      >
                        <X size={10} />
                      </button>
                    </span>
                  ))}
                  <GrantDropdown
                    tool_id={item.tool_id}
                    agents={agentsList}
                    grantedAgentIds={item.agents.map(a => a.agent_id)}
                    onGrant={(agent_id) => handleGrant(agent_id, item.tool_id)}
                  />
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* By agent view */}
      {pivot === 'by_agent' && (
        <div className="space-y-3">
          {filteredGrants.map(item => {
            const agent = agentsList.find(a => a.id === item.agent_id)
            return (
              <div key={item.agent_id} className="bg-zinc-900 border border-zinc-800 rounded-lg p-4">
                <div className="flex items-start justify-between gap-3 mb-2">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <Bot size={14} className="text-violet-400 flex-shrink-0" />
                      {item.code_letter && (
                        <span className="text-[10px] font-mono px-1.5 py-0.5 bg-zinc-800 rounded border border-zinc-700">
                          {item.code_letter}
                        </span>
                      )}
                      <span className="font-bold text-zinc-100 text-sm">{item.agent_name}</span>
                    </div>
                    {agent?.purpose && (
                      <p className="text-[11px] text-zinc-500 mb-2">{agent.purpose}</p>
                    )}
                  </div>
                </div>

                <div className="flex flex-wrap gap-1.5 pt-2 border-t border-zinc-800/60">
                  {item.tools.map(t => (
                    <span
                      key={t.tool_id}
                      className="group inline-flex items-center gap-1 px-2 py-0.5 bg-zinc-800 text-zinc-300 text-[10px] rounded border border-zinc-700"
                    >
                      <Wrench size={9} />
                      {t.tool_name}
                      <button
                        onClick={() => handleRevoke(item.agent_id, t.tool_id)}
                        className="opacity-0 group-hover:opacity-100 hover:text-rose-300"
                        title="Revoke"
                      >
                        <X size={10} />
                      </button>
                    </span>
                  ))}
                  <GrantDropdown
                    agent_id={item.agent_id}
                    tools={toolsList}
                    grantedToolIds={item.tools.map(t => t.tool_id)}
                    onGrant={(tool_id) => handleGrant(item.agent_id, tool_id)}
                  />
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

function GrantDropdown({ tool_id, agent_id, agents, tools, grantedAgentIds, grantedToolIds, onGrant }) {
  const [open, setOpen] = useState(false)
  const options = agents
    ? agents.filter(a => !grantedAgentIds.includes(a.id))
    : tools.filter(t => !grantedToolIds.includes(t.id))

  if (options.length === 0) return null

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="inline-flex items-center gap-1 px-2 py-0.5 bg-zinc-800/50 hover:bg-zinc-800 text-zinc-400 hover:text-zinc-200 text-[10px] rounded border border-zinc-700/60 border-dashed"
      >
        <Plus size={10} /> grant
      </button>
      {open && (
        <div className="absolute z-10 mt-1 left-0 w-64 max-h-60 overflow-y-auto bg-zinc-900 border border-zinc-800 rounded-lg shadow-xl py-1">
          {options.map(o => (
            <button
              key={o.id}
              onClick={() => { onGrant(o.id); setOpen(false) }}
              className="w-full text-left px-3 py-1.5 text-xs text-zinc-300 hover:bg-zinc-800"
            >
              {o.name || o.display_name}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

// ─── Pending Decisions section ───────────────────────────────────────────

function SetupRequiredCard({ decision, onApprove, onReject, busy }) {
  const data = decision.data || {}
  const missing = data.missing || []
  return (
    <div className="rounded-xl border border-amber-500/40 bg-amber-500/5 p-4 space-y-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2 text-[10px] uppercase tracking-wider text-amber-400">
            <span className="px-1.5 py-0.5 rounded border border-amber-500/40 text-amber-300 bg-amber-500/10">
              setup required
            </span>
            <span>{new Date(decision.created_at).toLocaleString()}</span>
          </div>
          <div className="text-zinc-100 font-semibold mt-1">
            {data.lane_display_name || 'Submission blocker'} — {data.artist_name || 'artist'}
          </div>
          <div className="text-xs text-zinc-400 mt-0.5">
            {data.summary}
          </div>
          {data.blocking_song_id && (
            <div className="text-[10px] text-zinc-600 mt-0.5 font-mono">
              Blocking song: {data.blocking_song_id.slice(0, 8)}
            </div>
          )}
        </div>
        <div className="flex gap-2 flex-shrink-0">
          <button
            onClick={() => onApprove(decision)}
            disabled={busy}
            className="flex items-center gap-1.5 px-3 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-40 text-white text-xs font-medium rounded-lg"
          >
            <CheckCircle2 size={12} /> Mark done
          </button>
          <button
            onClick={() => onReject(decision)}
            disabled={busy}
            className="flex items-center gap-1.5 px-3 py-2 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 text-xs font-medium rounded-lg border border-zinc-700"
          >
            Defer
          </button>
        </div>
      </div>

      <div className="space-y-2 pt-2 border-t border-amber-500/20">
        <div className="text-[10px] uppercase tracking-wider text-zinc-500">
          Action items ({missing.length})
        </div>
        {missing.map((item, i) => (
          <div key={i} className="bg-zinc-950 border border-zinc-800 rounded p-2.5 space-y-1">
            <div className="text-xs font-semibold text-zinc-200">{item.description}</div>
            <div className="text-[11px] text-zinc-400">{item.resolution_hint}</div>
            {item.env_var && (
              <div className="flex items-center gap-1 text-[10px] text-zinc-500">
                Set env var:
                <code className="text-amber-300 font-mono bg-zinc-900 px-1.5 py-0.5 rounded">
                  {item.env_var}
                </code>
              </div>
            )}
            {item.social_platform && (
              <div className="text-[10px] text-zinc-500">
                Create account on:
                <span className="text-violet-300 ml-1 uppercase">{item.social_platform}</span>
              </div>
            )}
          </div>
        ))}
      </div>

      {data.implementation_task && (
        <div className="text-[9px] text-zinc-600 pt-1 border-t border-amber-500/20">
          Submission lane ships in {data.implementation_task} ({data.submission_mode} mode)
        </div>
      )}
    </div>
  )
}

function DecisionCard({ decision, onApprove, onReject, busy }) {
  // Setup-required decisions get their own card with a checklist rendering
  if (decision.decision_type === 'setup_required') {
    return <SetupRequiredCard decision={decision} onApprove={onApprove} onReject={onReject} busy={busy} />
  }

  const [expanded, setExpanded] = useState(false)
  const data = decision.data || {}
  const breakdown = data.breakdown || {}
  const scores = data.scores || {}
  const proposedId = data.proposed_artist_id
  const proposedName = data.proposed_artist_name

  const summary =
    decision.proposal === 'reuse'
      ? `Reuse existing artist ${proposedName || proposedId?.slice(0, 8) || '(unknown)'}`
      : decision.proposal === 'create_new'
        ? `Create new artist for this blueprint`
        : decision.proposal

  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900 p-4 space-y-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2 text-[10px] uppercase tracking-wider text-zinc-500">
            <span className="px-1.5 py-0.5 rounded border border-violet-500/40 text-violet-300 bg-violet-500/10">
              {decision.decision_type}
            </span>
            <span>{new Date(decision.created_at).toLocaleString()}</span>
          </div>
          <div className="text-zinc-100 font-semibold mt-1">{summary}</div>
          {data.blueprint_genre && (
            <div className="text-xs text-zinc-500 mt-0.5">
              Blueprint genre: {data.blueprint_genre}
              {typeof data.roster_size === 'number' && ` · roster size ${data.roster_size}`}
            </div>
          )}
          {data.reason && (
            <div className="text-[11px] text-zinc-600 italic mt-1">{data.reason}</div>
          )}
        </div>
        <div className="flex gap-2 flex-shrink-0">
          <button
            onClick={() => onApprove(decision)}
            disabled={busy}
            className="flex items-center gap-1.5 px-3 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-40 text-white text-xs font-medium rounded-lg transition-colors"
          >
            <ThumbsUp size={12} /> Approve
          </button>
          <button
            onClick={() => onReject(decision)}
            disabled={busy}
            className="flex items-center gap-1.5 px-3 py-2 bg-zinc-800 hover:bg-rose-600/80 disabled:opacity-40 text-zinc-300 hover:text-white text-xs font-medium rounded-lg border border-zinc-700 transition-colors"
          >
            <ThumbsDown size={12} /> Reject
          </button>
        </div>
      </div>

      {Object.keys(scores).length > 0 && (
        <button
          onClick={() => setExpanded(!expanded)}
          className="text-[11px] text-violet-300 hover:text-violet-200"
        >
          {expanded ? 'Hide' : 'Show'} scoring ({Object.keys(scores).length} artist{Object.keys(scores).length === 1 ? '' : 's'})
        </button>
      )}

      {expanded && (
        <div className="border-t border-zinc-800 pt-3 space-y-3">
          {Object.entries(scores)
            .sort((a, b) => b[1] - a[1])
            .map(([artistId, composite]) => {
              const dims = breakdown[artistId] || {}
              const isProposed = artistId === proposedId
              return (
                <div
                  key={artistId}
                  className={`rounded border p-2.5 ${
                    isProposed
                      ? 'border-emerald-500/40 bg-emerald-500/5'
                      : 'border-zinc-800 bg-zinc-950/50'
                  }`}
                >
                  <div className="flex items-center justify-between mb-1.5">
                    <div className="text-xs font-mono text-zinc-400">
                      {artistId.slice(0, 8)}
                      {isProposed && (
                        <span className="ml-2 text-[9px] uppercase tracking-wider text-emerald-300">
                          proposed
                        </span>
                      )}
                    </div>
                    <div className="text-sm font-bold text-zinc-100 tabular-nums">
                      {composite.toFixed(3)}
                    </div>
                  </div>
                  <div className="grid grid-cols-5 gap-1 text-[9px] text-zinc-500">
                    {Object.entries(dims).map(([name, value]) => (
                      <div key={name} className="bg-zinc-900 rounded px-1.5 py-1">
                        <div
                          className={`font-bold tabular-nums ${
                            value >= 0.7 ? 'text-emerald-300' :
                            value >= 0.4 ? 'text-amber-300' :
                            'text-rose-300'
                          }`}
                        >
                          {value.toFixed(2)}
                        </div>
                        <div className="truncate" title={name}>{name.replace(/_/g, ' ')}</div>
                      </div>
                    ))}
                  </div>
                </div>
              )
            })}
          {data.threshold && (
            <div className="text-[10px] text-zinc-600">
              Reuse threshold: {data.threshold.toFixed(2)}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function PendingDecisionsSection() {
  const [filter, setFilter] = useState('pending')
  const { data, isLoading } = useCeoDecisions({ status: filter })
  const approve = useApproveCeoDecision()
  const reject = useRejectCeoDecision()
  const qc = useQueryClient()
  const [busyId, setBusyId] = useState(null)

  const decisions = data?.data?.decisions || []

  const handleApprove = async (d) => {
    setBusyId(d.decision_id)
    try {
      await approve.mutateAsync({ decisionId: d.decision_id })
      qc.invalidateQueries({ queryKey: ['admin', 'ceo-decisions'] })
      qc.invalidateQueries({ queryKey: ['admin', 'blueprints'] })
    } finally {
      setBusyId(null)
    }
  }
  const handleReject = async (d) => {
    setBusyId(d.decision_id)
    try {
      await reject.mutateAsync({ decisionId: d.decision_id })
      qc.invalidateQueries({ queryKey: ['admin', 'ceo-decisions'] })
    } finally {
      setBusyId(null)
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-zinc-100">Pending Decisions</h2>
          <p className="text-xs text-zinc-500">CEO gate queue — approvals unblock the autonomous pipeline.</p>
        </div>
        <div className="flex gap-1 bg-zinc-900 border border-zinc-800 rounded-lg p-1">
          {['pending', 'approved', 'rejected'].map(s => (
            <button
              key={s}
              onClick={() => setFilter(s)}
              className={`px-3 py-1 text-xs rounded font-medium capitalize transition-colors ${
                filter === s
                  ? 'bg-violet-600/30 text-violet-200 border border-violet-500/50'
                  : 'text-zinc-500 hover:text-zinc-300'
              }`}
            >
              {s}
            </button>
          ))}
        </div>
      </div>

      {isLoading && (
        <div className="flex items-center justify-center py-12 text-zinc-500">
          <Loader2 size={18} className="animate-spin mr-2" /> Loading decisions...
        </div>
      )}

      {!isLoading && decisions.length === 0 && (
        <div className="flex flex-col items-center justify-center py-16 text-center">
          <Inbox size={40} className="text-zinc-700 mb-3" />
          <div className="text-sm text-zinc-400">No {filter} decisions</div>
          <div className="text-xs text-zinc-600 mt-1 max-w-sm">
            When a blueprint runs through the assignment engine, the recommendation lands here for your approval.
          </div>
        </div>
      )}

      <div className="space-y-3">
        {decisions.map(d => (
          <DecisionCard
            key={d.decision_id}
            decision={d}
            onApprove={handleApprove}
            onReject={handleReject}
            busy={busyId === d.decision_id}
          />
        ))}
      </div>
    </div>
  )
}

// ─── Page shell ──────────────────────────────────────────────────────────

export default function Settings() {
  const [section, setSection] = useState('decisions')

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="flex items-center gap-3 mb-6">
        <SettingsIcon size={24} className="text-violet-400" />
        <h1 className="text-2xl font-bold text-zinc-100">Settings</h1>
      </div>

      <div className="flex gap-6">
        {/* Sidebar */}
        <nav className="w-48 flex-shrink-0">
          <div className="space-y-1">
            {SECTIONS.map(s => {
              const Icon = s.icon
              const active = section === s.id
              return (
                <button
                  key={s.id}
                  onClick={() => setSection(s.id)}
                  className={`w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-colors ${
                    active
                      ? 'bg-violet-600/20 text-violet-200 border border-violet-500/40'
                      : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900 border border-transparent'
                  }`}
                >
                  <Icon size={14} /> {s.label}
                </button>
              )
            })}
          </div>
        </nav>

        {/* Content */}
        <div className="flex-1 min-w-0">
          {section === 'decisions' && <PendingDecisionsSection />}
          {section === 'ceo' && <CeoProfileSection />}
          {section === 'tools' && <ToolsAndAgentsSection />}
        </div>
      </div>
    </div>
  )
}
