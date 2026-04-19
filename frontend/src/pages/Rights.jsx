/**
 * Rights tab — manage publishers, writers, and composers.
 *
 * One polymorphic table (rights_holders) with a kind discriminator.
 * Three tabs in this page swap the kind filter on the GET. Add/Edit/
 * Delete share the same modal — kind is fixed at create time.
 *
 * Entries here will be referenced by song_metadata_master.writers /
 * publishers / composers JSONB columns (instead of duplicating contact
 * + IPI + PRO info on every song row).
 */
import { useState } from 'react'
import {
  Briefcase, Plus, Edit3, Trash2, Loader2, X, AlertCircle, CheckCircle2,
  RefreshCw, Mail, Phone, FileText, Hash,
} from 'lucide-react'
import { useQueryClient } from '@tanstack/react-query'
import {
  useRightsHolders,
  useCreateRightsHolder,
  useUpdateRightsHolder,
  useDeleteRightsHolder,
} from '../hooks/useSoundPulse'

const KINDS = [
  { id: 'publisher', label: 'Publishers', singular: 'publisher', help: 'Music publishing companies that own/administer publishing rights — used for MLC mechanical registration.' },
  { id: 'writer',    label: 'Writers',    singular: 'writer',    help: 'Songwriters / lyricists — registered with ASCAP / BMI / SESAC by IPI number.' },
  { id: 'composer',  label: 'Composers',  singular: 'composer',  help: 'Music composers — same PRO registration path as writers; separated for credit clarity (some songs split lyrics + music).' },
]

const PRO_OPTIONS = [
  '', 'ASCAP', 'BMI', 'SESAC', 'GMR',
  'PRS', 'SOCAN', 'GEMA', 'SACEM', 'JASRAC', 'APRA AMCOS', 'SIAE', 'SUISA',
  'Other',
]

function HolderModal({ kindMeta, existing = null, onClose, onSaved }) {
  const create = useCreateRightsHolder()
  const update = useUpdateRightsHolder()
  const qc = useQueryClient()
  const isEdit = Boolean(existing)
  const e = existing || {}

  const [legalName, setLegalName] = useState(e.legal_name || '')
  const [stageName, setStageName] = useState(e.stage_name || '')
  const [ipiNumber, setIpiNumber] = useState(e.ipi_number || '')
  const [isni, setIsni] = useState(e.isni || '')
  const [proAffiliation, setProAffiliation] = useState(e.pro_affiliation || '')
  const [publisherCompanyName, setPublisherCompanyName] = useState(e.publisher_company_name || '')
  const [email, setEmail] = useState(e.email || '')
  const [phone, setPhone] = useState(e.phone || '')
  const [address, setAddress] = useState(e.address || '')
  const [taxId, setTaxId] = useState(e.tax_id || '')
  const [defaultSplitPercent, setDefaultSplitPercent] = useState(
    e.default_split_percent != null ? String(e.default_split_percent) : ''
  )
  const [notes, setNotes] = useState(e.notes || '')
  const [error, setError] = useState(null)
  const [savedFlag, setSavedFlag] = useState(false)

  const mut = isEdit ? update : create

  const handleSubmit = async () => {
    setError(null)
    if (!legalName.trim()) {
      setError('Legal name is required')
      return
    }
    const split = defaultSplitPercent.trim() === '' ? null : parseFloat(defaultSplitPercent)
    if (split !== null && (Number.isNaN(split) || split < 0 || split > 100)) {
      setError('Default split must be a number between 0 and 100')
      return
    }
    const body = {
      legal_name: legalName.trim(),
      stage_name: stageName.trim() || null,
      ipi_number: ipiNumber.trim() || null,
      isni: isni.trim() || null,
      pro_affiliation: proAffiliation || null,
      publisher_company_name: publisherCompanyName.trim() || null,
      email: email.trim() || null,
      phone: phone.trim() || null,
      address: address.trim() || null,
      tax_id: taxId.trim() || null,
      default_split_percent: split,
      notes: notes.trim() || null,
    }
    if (!isEdit) body.kind = kindMeta.id
    try {
      isEdit
        ? await update.mutateAsync({ holderId: existing.id, body })
        : await create.mutateAsync({ body })
      setSavedFlag(true)
      qc.invalidateQueries({ queryKey: ['admin', 'rights-holders'] })
      setTimeout(() => { onSaved?.(); onClose?.() }, 800)
    } catch (e2) {
      setError(e2?.response?.data?.detail || e2?.message || 'save failed')
    }
  }

  const inp = (val, setter, placeholder, type = 'text') => (
    <input
      type={type}
      value={val}
      onChange={(ev) => setter(ev.target.value)}
      placeholder={placeholder}
      className="w-full px-3 py-2 bg-zinc-950 border border-zinc-800 rounded text-sm text-zinc-100 placeholder-zinc-600"
    />
  )
  const ta = (val, setter, placeholder, rows = 2) => (
    <textarea
      value={val}
      onChange={(ev) => setter(ev.target.value)}
      placeholder={placeholder}
      rows={rows}
      className="w-full px-3 py-2 bg-zinc-950 border border-zinc-800 rounded text-sm text-zinc-100 placeholder-zinc-600 resize-y"
    />
  )

  return (
    <div className="fixed inset-0 z-50 bg-black/80 flex items-start justify-center p-4 overflow-y-auto" onClick={onClose}>
      <div className="bg-zinc-950 border border-zinc-800 rounded-xl max-w-2xl w-full my-4" onClick={(ev) => ev.stopPropagation()}>
        <div className="flex items-center justify-between p-4 border-b border-zinc-800 sticky top-0 bg-zinc-950 z-10">
          <div className="flex items-center gap-2 text-sm font-semibold text-zinc-200">
            <Briefcase size={14} className="text-violet-400" />
            {isEdit ? `Edit ${kindMeta.singular} — ${existing.legal_name}` : `Add new ${kindMeta.singular}`}
          </div>
          <button onClick={onClose} className="text-zinc-500 hover:text-zinc-300"><X size={16} /></button>
        </div>

        <div className="p-5 space-y-5">
          <section className="space-y-3">
            <div className="text-[11px] uppercase tracking-wider text-violet-400 font-semibold">Identity</div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <label className="block text-xs text-zinc-400">
                Legal name *
                <div className="mt-1">{inp(legalName, setLegalName, 'e.g. SoundPulse Records LLC')}</div>
              </label>
              <label className="block text-xs text-zinc-400">
                Stage name {kindMeta.id === 'publisher' ? '(DBA)' : '(pen name)'}
                <div className="mt-1">{inp(stageName, setStageName, 'optional public alias')}</div>
              </label>
            </div>
          </section>

          <section className="space-y-3">
            <div className="text-[11px] uppercase tracking-wider text-violet-400 font-semibold">Rights org IDs</div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <label className="block text-xs text-zinc-400">
                IPI number
                <div className="mt-1">{inp(ipiNumber, setIpiNumber, '11-digit Interested Parties Information')}</div>
                <div className="text-[10px] text-zinc-600 mt-0.5">Issued by your PRO. Required for ASCAP/BMI registration.</div>
              </label>
              <label className="block text-xs text-zinc-400">
                ISNI
                <div className="mt-1">{inp(isni, setIsni, '0000 0000 0000 0000')}</div>
                <div className="text-[10px] text-zinc-600 mt-0.5">International Standard Name Identifier (optional).</div>
              </label>
              <label className="block text-xs text-zinc-400">
                PRO affiliation
                <select
                  value={proAffiliation}
                  onChange={(ev) => setProAffiliation(ev.target.value)}
                  className="w-full mt-1 px-3 py-2 bg-zinc-950 border border-zinc-800 rounded text-sm text-zinc-100"
                >
                  {PRO_OPTIONS.map((opt) => (
                    <option key={opt} value={opt}>{opt || '— pick a PRO —'}</option>
                  ))}
                </select>
              </label>
              {kindMeta.id !== 'publisher' && (
                <label className="block text-xs text-zinc-400">
                  Publisher company
                  <div className="mt-1">{inp(publisherCompanyName, setPublisherCompanyName, 'if signed to a publisher')}</div>
                </label>
              )}
            </div>
          </section>

          <section className="space-y-3">
            <div className="text-[11px] uppercase tracking-wider text-violet-400 font-semibold">Contact</div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <label className="block text-xs text-zinc-400">
                Email
                <div className="mt-1">{inp(email, setEmail, 'rights@example.com', 'email')}</div>
              </label>
              <label className="block text-xs text-zinc-400">
                Phone
                <div className="mt-1">{inp(phone, setPhone, '+1 555 555 1234', 'tel')}</div>
              </label>
              <div className="md:col-span-2">
                <label className="block text-xs text-zinc-400">
                  Address
                  <div className="mt-1">{ta(address, setAddress, 'Street, city, state, postal code, country', 2)}</div>
                </label>
              </div>
            </div>
          </section>

          <section className="space-y-3">
            <div className="text-[11px] uppercase tracking-wider text-violet-400 font-semibold">Tax & defaults</div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <label className="block text-xs text-zinc-400">
                Tax ID
                <div className="mt-1">{inp(taxId, setTaxId, 'EIN / SSN / VAT — for W-9 / W-8 reference')}</div>
              </label>
              <label className="block text-xs text-zinc-400">
                Default split %
                <div className="mt-1">{inp(defaultSplitPercent, setDefaultSplitPercent, '50.00', 'number')}</div>
                <div className="text-[10px] text-zinc-600 mt-0.5">Typical % this party gets on a song. 0–100, or leave blank.</div>
              </label>
            </div>
          </section>

          <section>
            <label className="block text-xs text-zinc-400">
              Notes
              <div className="mt-1">{ta(notes, setNotes, 'free-form notes — admin id, contract reference, signing date, etc.', 3)}</div>
            </label>
          </section>

          {error && (
            <div className="bg-rose-500/10 border border-rose-500/30 rounded p-2 text-xs text-rose-300 flex items-center gap-2">
              <AlertCircle size={14} /> {error}
            </div>
          )}

          {savedFlag && (
            <div className="bg-emerald-500/10 border border-emerald-500/30 rounded p-2 text-xs text-emerald-300 flex items-center gap-2">
              <CheckCircle2 size={14} /> {isEdit ? 'Saved' : 'Created'}
            </div>
          )}
        </div>

        <div className="flex items-center justify-end gap-2 p-4 border-t border-zinc-800 sticky bottom-0 bg-zinc-950">
          <button onClick={onClose} className="px-4 py-2 text-zinc-400 text-xs hover:text-zinc-200">Cancel</button>
          <button
            onClick={handleSubmit}
            disabled={mut.isPending || !legalName.trim()}
            className="px-5 py-2 bg-violet-600 hover:bg-violet-500 disabled:bg-zinc-800 disabled:text-zinc-600 text-white text-sm font-medium rounded flex items-center gap-2"
          >
            {mut.isPending ? <Loader2 size={14} className="animate-spin" /> : (isEdit ? <Edit3 size={14} /> : <Plus size={14} />)}
            {mut.isPending
              ? (isEdit ? 'Saving…' : 'Creating…')
              : (isEdit ? 'Save changes' : `Add ${kindMeta.singular}`)}
          </button>
        </div>
      </div>
    </div>
  )
}

function HoldersTable({ kindMeta }) {
  const { data, isLoading, isError, error, refetch, isFetching } = useRightsHolders(kindMeta.id)
  const items = data?.data?.items || []
  const remove = useDeleteRightsHolder()
  const qc = useQueryClient()

  const [creating, setCreating] = useState(false)
  const [editing, setEditing] = useState(null)
  const [actionStatus, setActionStatus] = useState(null)

  const handleDelete = async (row) => {
    if (!window.confirm(`Delete ${kindMeta.singular} "${row.legal_name}"? This will not affect songs that already reference them by id.`)) return
    setActionStatus(null)
    try {
      await remove.mutateAsync({ holderId: row.id })
      setActionStatus({ kind: 'success', msg: `Deleted ${row.legal_name}` })
      qc.invalidateQueries({ queryKey: ['admin', 'rights-holders'] })
      refetch()
    } catch (e) {
      setActionStatus({ kind: 'error', msg: e?.response?.data?.detail || e?.message || 'delete failed' })
    }
  }

  return (
    <div className="space-y-3">
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <p className="text-xs text-zinc-500 max-w-2xl">{kindMeta.help}</p>
        <div className="flex items-center gap-2">
          <button
            onClick={() => refetch()}
            disabled={isFetching}
            className="flex items-center gap-1 px-2 py-1.5 text-xs text-zinc-400 hover:text-zinc-200 disabled:opacity-50"
          >
            <RefreshCw size={12} className={isFetching ? 'animate-spin' : ''} /> Refresh
          </button>
          <button
            onClick={() => setCreating(true)}
            className="flex items-center gap-1.5 px-3 py-2 bg-violet-600 hover:bg-violet-500 text-white text-xs font-medium rounded-lg"
          >
            <Plus size={14} /> Add {kindMeta.singular}
          </button>
        </div>
      </div>

      {actionStatus && (
        <div className={`p-2 rounded border text-xs ${
          actionStatus.kind === 'success'
            ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
            : 'bg-rose-500/10 border-rose-500/30 text-rose-300'
        }`}>
          {actionStatus.msg}
        </div>
      )}

      {isLoading && (
        <div className="flex items-center justify-center py-12 text-zinc-500">
          <Loader2 size={20} className="animate-spin mr-2" /> Loading {kindMeta.label.toLowerCase()}…
        </div>
      )}
      {isError && (
        <div className="bg-rose-500/10 border border-rose-500/30 rounded p-3 text-xs text-rose-300">
          Failed to load: {error?.message}
        </div>
      )}

      {!isLoading && items.length === 0 && (
        <div className="border border-dashed border-zinc-800 rounded-xl p-10 text-center text-zinc-500">
          <Briefcase size={28} className="mx-auto mb-3 text-zinc-600" />
          <div className="text-sm font-medium text-zinc-400">No {kindMeta.label.toLowerCase()} yet</div>
          <div className="text-xs mt-1">Add one to register them with PROs (ASCAP / BMI / MLC) downstream.</div>
          <button
            onClick={() => setCreating(true)}
            className="mt-4 inline-flex items-center gap-1.5 px-3 py-2 bg-violet-600 hover:bg-violet-500 text-white text-xs rounded"
          >
            <Plus size={12} /> Add {kindMeta.singular}
          </button>
        </div>
      )}

      {items.length > 0 && (
        <div className="border border-zinc-800 rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-zinc-900 text-[10px] uppercase tracking-wider text-zinc-500">
              <tr>
                <th className="text-left px-3 py-2">Legal name</th>
                <th className="text-left px-3 py-2">Stage / DBA</th>
                <th className="text-left px-3 py-2">IPI</th>
                <th className="text-left px-3 py-2">PRO</th>
                <th className="text-left px-3 py-2">Contact</th>
                <th className="text-right px-3 py-2 w-24">Split %</th>
                <th className="text-right px-3 py-2 w-32">Actions</th>
              </tr>
            </thead>
            <tbody>
              {items.map((row) => (
                <tr key={row.id} className="border-t border-zinc-800 hover:bg-zinc-900/50">
                  <td className="px-3 py-2 font-medium text-zinc-100">{row.legal_name}</td>
                  <td className="px-3 py-2 text-xs text-zinc-400">{row.stage_name || '—'}</td>
                  <td className="px-3 py-2 text-xs text-zinc-400 font-mono">{row.ipi_number || '—'}</td>
                  <td className="px-3 py-2 text-xs">
                    {row.pro_affiliation
                      ? <span className="px-1.5 py-0.5 rounded border border-violet-500/40 bg-violet-500/10 text-violet-300">{row.pro_affiliation}</span>
                      : <span className="text-zinc-600">—</span>}
                  </td>
                  <td className="px-3 py-2 text-xs text-zinc-400">
                    {row.email && <div className="flex items-center gap-1"><Mail size={10} />{row.email}</div>}
                    {row.phone && <div className="flex items-center gap-1"><Phone size={10} />{row.phone}</div>}
                    {!row.email && !row.phone && <span className="text-zinc-600">—</span>}
                  </td>
                  <td className="px-3 py-2 text-right text-xs text-zinc-400 tabular-nums">
                    {row.default_split_percent != null ? `${row.default_split_percent}%` : '—'}
                  </td>
                  <td className="px-3 py-2 text-right">
                    <button
                      onClick={() => setEditing(row)}
                      className="text-xs text-violet-300 hover:text-violet-200 mr-2"
                    >
                      Edit
                    </button>
                    <button
                      onClick={() => handleDelete(row)}
                      disabled={remove.isPending}
                      className="text-xs text-zinc-500 hover:text-rose-300 disabled:opacity-50"
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {creating && (
        <HolderModal
          kindMeta={kindMeta}
          onClose={() => setCreating(false)}
          onSaved={() => qc.invalidateQueries({ queryKey: ['admin', 'rights-holders'] })}
        />
      )}
      {editing && (
        <HolderModal
          kindMeta={kindMeta}
          existing={editing}
          onClose={() => setEditing(null)}
          onSaved={() => qc.invalidateQueries({ queryKey: ['admin', 'rights-holders'] })}
        />
      )}
    </div>
  )
}

export default function Rights() {
  const [activeKind, setActiveKind] = useState('publisher')
  const activeMeta = KINDS.find((k) => k.id === activeKind) || KINDS[0]

  return (
    <div className="p-4 md:p-6 max-w-6xl mx-auto">
      <div className="flex items-start justify-between mb-6 gap-3 flex-wrap">
        <div>
          <div className="flex items-center gap-3 mb-1">
            <Briefcase size={24} className="text-violet-400" />
            <h1 className="text-2xl font-bold text-zinc-100">Rights holders</h1>
          </div>
          <p className="text-sm text-zinc-500 max-w-2xl">
            Canonical publishers, writers, and composers. Songs reference these by id (instead of duplicating IPI / PRO / contact info on every <code>songs_master.writers</code> blob), so PRO + MLC submissions stay consistent and one update propagates everywhere.
          </p>
        </div>
      </div>

      {/* Segmented control */}
      <div className="inline-flex items-center gap-1 bg-zinc-900 border border-zinc-800 rounded-lg p-1 mb-6">
        {KINDS.map((k) => (
          <button
            key={k.id}
            onClick={() => setActiveKind(k.id)}
            className={`px-4 py-1.5 text-xs font-medium rounded transition-colors ${
              activeKind === k.id
                ? 'bg-violet-600/30 text-violet-200 border border-violet-500/50'
                : 'text-zinc-400 hover:text-zinc-200'
            }`}
          >
            {k.label}
          </button>
        ))}
      </div>

      <HoldersTable kindMeta={activeMeta} />
    </div>
  )
}
