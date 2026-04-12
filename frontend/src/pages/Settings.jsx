import { useState, useEffect } from 'react'
import {
  Settings as SettingsIcon, User, Wrench, Loader2, Save, Check,
  AlertCircle, CheckCircle2, Plus, X, Bot,
} from 'lucide-react'
import { useQueryClient } from '@tanstack/react-query'
import {
  useCeoProfile, useUpdateCeoProfile,
  useAgents, useTools, useAgentToolGrants,
  useCreateGrant, useDeleteGrant,
} from '../hooks/useSoundPulse'

const SECTIONS = [
  { id: 'ceo',   label: 'CEO Profile', icon: User },
  { id: 'tools', label: 'Tools & Agents', icon: Wrench },
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

// ─── Page shell ──────────────────────────────────────────────────────────

export default function Settings() {
  const [section, setSection] = useState('ceo')

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
          {section === 'ceo' && <CeoProfileSection />}
          {section === 'tools' && <ToolsAndAgentsSection />}
        </div>
      </div>
    </div>
  )
}
