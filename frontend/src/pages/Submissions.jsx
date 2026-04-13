import { useState } from 'react'
import {
  Send, Loader2, CheckCircle2, AlertCircle, Clock, XCircle,
  Sparkles, RefreshCw, Package, Mic2, Globe, Music,
  ArrowRight, Plug,
} from 'lucide-react'
import { useQueryClient } from '@tanstack/react-query'
import {
  useSubmissionTargets, useExternalSubmissions, useAscapSubmissions,
  useDownstreamSweep,
} from '../hooks/useSoundPulse'

function StatusBadge({ status }) {
  const map = {
    submitted:    { cls: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30', icon: CheckCircle2 },
    accepted:     { cls: 'bg-emerald-500/25 text-emerald-200 border-emerald-500/40', icon: CheckCircle2 },
    in_progress:  { cls: 'bg-violet-500/15 text-violet-300 border-violet-500/30', icon: Loader2 },
    queued:       { cls: 'bg-zinc-700/30 text-zinc-300 border-zinc-600', icon: Clock },
    pending:      { cls: 'bg-zinc-700/30 text-zinc-300 border-zinc-600', icon: Clock },
    failed:       { cls: 'bg-rose-500/15 text-rose-300 border-rose-500/30', icon: XCircle },
    rejected:     { cls: 'bg-rose-500/25 text-rose-300 border-rose-500/40', icon: XCircle },
  }
  const entry = map[status] || { cls: 'bg-zinc-800 text-zinc-400 border-zinc-700', icon: AlertCircle }
  const Icon = entry.icon
  return (
    <span className={`px-2 py-0.5 text-[10px] rounded border flex items-center gap-1 ${entry.cls}`}>
      <Icon size={10} className={status === 'in_progress' ? 'animate-spin' : ''} />
      {status}
    </span>
  )
}

function TargetCard({ target }) {
  const typeIcon = {
    distributor: Package,
    pro: Mic2,
    rights: Mic2,
    content_id: Globe,
    sync: Music,
    playlist: Music,
    marketing: Sparkles,
  }[target.target_type] || Plug
  const TypeIcon = typeIcon
  const liveBadge = target.integration_status === 'live'
  return (
    <div className={`border rounded-lg p-3 ${liveBadge ? 'bg-emerald-500/5 border-emerald-500/30' : 'bg-zinc-900/40 border-zinc-800'}`}>
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <TypeIcon size={13} className="text-violet-400 flex-shrink-0" />
            <span className="text-xs font-semibold text-zinc-200 truncate">{target.display_name}</span>
            {liveBadge && (
              <span className="px-1.5 py-0.5 text-[9px] bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 rounded">LIVE</span>
            )}
          </div>
          <div className="text-[10px] text-zinc-500 mt-0.5">
            {target.target_type} · {target.target_service}
          </div>
        </div>
        <div className="flex-shrink-0 text-right">
          {target.credential_ready ? (
            <span className="text-[10px] text-emerald-400 flex items-center gap-0.5"><CheckCircle2 size={9} /> creds</span>
          ) : (
            <span className="text-[10px] text-amber-400 flex items-center gap-0.5" title={(target.missing_credentials || []).join(', ')}>
              <AlertCircle size={9} /> {target.missing_credentials?.length || 0} missing
            </span>
          )}
        </div>
      </div>
      {target.notes && (
        <div className="text-[10px] text-zinc-600 mt-1.5">{target.notes}</div>
      )}
    </div>
  )
}

function TargetSection({ title, type, targets }) {
  const filtered = targets.filter(t => t.target_type === type)
  if (filtered.length === 0) return null
  return (
    <div className="space-y-2">
      <div className="text-[10px] uppercase tracking-wider text-zinc-500">{title} ({filtered.length})</div>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
        {filtered.map(t => <TargetCard key={t.target_service} target={t} />)}
      </div>
    </div>
  )
}

export default function Submissions() {
  const { data: targetsData, isLoading: targetsLoading } = useSubmissionTargets()
  const { data: extData, isLoading: extLoading } = useExternalSubmissions({ limit: 50 })
  const { data: ascapData } = useAscapSubmissions()
  const sweep = useDownstreamSweep()
  const qc = useQueryClient()
  const [sweepResult, setSweepResult] = useState(null)

  const targets = targetsData?.data?.targets || []
  const submissions = extData?.data?.submissions || []
  const ascap = ascapData?.data?.submissions || []

  const handleSweep = async () => {
    if (!window.confirm('Run the downstream pipeline sweep? This walks qa_passed songs and dispatches them through every enabled target. Press release + social media agents will generate real content.')) return
    try {
      const res = await sweep.mutateAsync({ limit: 10 })
      setSweepResult(res?.data)
      qc.invalidateQueries({ queryKey: ['admin', 'external-submissions'] })
      qc.invalidateQueries({ queryKey: ['admin', 'ascap-submissions'] })
    } catch (e) {
      setSweepResult({ error: e?.response?.data?.detail || e?.message })
    }
  }

  const liveCount = targets.filter(t => t.integration_status === 'live').length
  const credsReadyCount = targets.filter(t => t.credential_ready).length

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Send className="text-violet-400" size={24} />
          <div>
            <h1 className="text-xl font-semibold text-zinc-100">Submissions</h1>
            <p className="text-xs text-zinc-500">
              Downstream pipeline — distributors, PROs, sync marketplaces, playlists, marketing.
            </p>
          </div>
        </div>
        <button
          onClick={handleSweep}
          disabled={sweep.isPending}
          className="px-4 py-2 bg-violet-600 hover:bg-violet-500 disabled:bg-zinc-800 text-white text-sm rounded flex items-center gap-2 transition-colors"
        >
          {sweep.isPending ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
          Run downstream sweep
        </button>
      </div>

      <div className="grid grid-cols-3 gap-3">
        <div className="bg-zinc-900/40 border border-zinc-800 rounded-lg p-3">
          <div className="text-[10px] uppercase tracking-wider text-zinc-500">Total targets</div>
          <div className="text-2xl font-bold text-zinc-100 mt-1">{targets.length + (ascap.length > 0 ? 1 : 1)}</div>
          <div className="text-[10px] text-zinc-500">incl. ASCAP (separate table)</div>
        </div>
        <div className="bg-zinc-900/40 border border-zinc-800 rounded-lg p-3">
          <div className="text-[10px] uppercase tracking-wider text-zinc-500">Live integrations</div>
          <div className="text-2xl font-bold text-emerald-400 mt-1">{liveCount}</div>
          <div className="text-[10px] text-zinc-500">press release + social media</div>
        </div>
        <div className="bg-zinc-900/40 border border-zinc-800 rounded-lg p-3">
          <div className="text-[10px] uppercase tracking-wider text-zinc-500">Credentials ready</div>
          <div className="text-2xl font-bold text-violet-300 mt-1">{credsReadyCount} / {targets.length}</div>
          <div className="text-[10px] text-zinc-500">env vars configured</div>
        </div>
      </div>

      {sweepResult && (
        <div className="bg-zinc-900/40 border border-zinc-800 rounded-lg p-4">
          <div className="text-sm font-medium text-zinc-200 mb-2">Sweep result</div>
          {sweepResult.error ? (
            <div className="text-xs text-rose-400">{sweepResult.error}</div>
          ) : (
            <div className="text-[11px] text-zinc-400 space-y-1 max-h-64 overflow-y-auto">
              <div>Scanned: <span className="text-zinc-200">{sweepResult.scanned}</span></div>
              {(sweepResult.results || []).map((r, i) => (
                <div key={i} className="border-t border-zinc-800 pt-2 mt-2">
                  <div className="text-zinc-200">{r.title} <span className="text-zinc-600">({r.song_id?.slice(0, 8)})</span></div>
                  <div className="grid grid-cols-3 gap-x-3 gap-y-0.5 mt-1">
                    {Object.entries(r.steps || {}).map(([k, v]) => (
                      <div key={k} className="flex items-center gap-1 text-[10px]">
                        <span className="text-zinc-500 truncate">{k}</span>
                        <ArrowRight size={8} className="text-zinc-700" />
                        <span className={
                          v === 'submitted' || v === 'accepted' ? 'text-emerald-400' :
                          v === 'disabled' ? 'text-zinc-600' :
                          v?.startsWith('deferred') ? 'text-amber-400' :
                          v === 'already_done' ? 'text-zinc-500' : 'text-rose-400'
                        }>{v}</span>
                      </div>
                    ))}
                  </div>
                  {r.errors?.length > 0 && (
                    <div className="text-rose-400 text-[10px] mt-1">errors: {r.errors.join(' | ')}</div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Targets matrix */}
      <div className="space-y-5">
        <div className="text-sm font-semibold text-zinc-300">Integration Targets</div>
        {targetsLoading ? (
          <div className="flex items-center gap-2 text-sm text-zinc-500"><Loader2 size={14} className="animate-spin" /> Loading targets…</div>
        ) : (
          <>
            <TargetSection title="Distributors" type="distributor" targets={targets} />
            <TargetSection title="Performance Rights Orgs" type="pro" targets={targets} />
            <TargetSection title="Rights / Royalties" type="rights" targets={targets} />
            <TargetSection title="Content ID" type="content_id" targets={targets} />
            <TargetSection title="Sync Marketplaces" type="sync" targets={targets} />
            <TargetSection title="Playlist Pitching" type="playlist" targets={targets} />
            <TargetSection title="Marketing" type="marketing" targets={targets} />
          </>
        )}
      </div>

      {/* Recent submissions */}
      <div className="space-y-2">
        <div className="text-sm font-semibold text-zinc-300">Recent external submissions ({submissions.length})</div>
        {extLoading ? (
          <div className="flex items-center gap-2 text-sm text-zinc-500"><Loader2 size={14} className="animate-spin" /> Loading…</div>
        ) : submissions.length === 0 ? (
          <div className="text-xs text-zinc-600">No submissions yet. Run the sweep to generate the first batch.</div>
        ) : (
          <div className="space-y-1">
            {submissions.map(s => (
              <div key={s.id} className="bg-zinc-900/40 border border-zinc-800 rounded p-2 flex items-center gap-3 text-[11px]">
                <span className="text-zinc-300 font-mono">{s.target_service}</span>
                <span className="text-zinc-600">·</span>
                <span className="text-zinc-500">{s.submission_subject_type}</span>
                <StatusBadge status={s.status} />
                {s.external_id && <span className="text-zinc-600 font-mono">{s.external_id.slice(0, 30)}</span>}
                {s.last_error_message && <span className="text-rose-400 truncate flex-1">{s.last_error_message}</span>}
                <span className="ml-auto text-zinc-600">{new Date(s.created_at).toLocaleString()}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* ASCAP section (separate table) */}
      {ascap.length > 0 && (
        <div className="space-y-2">
          <div className="text-sm font-semibold text-zinc-300">ASCAP work registrations ({ascap.length})</div>
          <div className="space-y-1">
            {ascap.map(s => (
              <div key={s.id} className="bg-zinc-900/40 border border-zinc-800 rounded p-2 flex items-center gap-3 text-[11px]">
                <span className="text-zinc-300 font-mono">ascap</span>
                <span className="text-zinc-500 truncate flex-1">{s.submission_title}</span>
                <StatusBadge status={s.status} />
                {s.ascap_work_id && <span className="text-emerald-400 font-mono">work_id: {s.ascap_work_id}</span>}
                {s.last_error_message && <span className="text-rose-400 text-[10px] truncate max-w-xs">{s.last_error_message}</span>}
                <span className="ml-auto text-zinc-600">{new Date(s.created_at).toLocaleString()}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
