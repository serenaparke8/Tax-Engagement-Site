import { useEffect, useMemo, useState } from 'react'
import WorkspaceHeader from '../../components/WorkspaceHeader.jsx'
import { api } from '../../services/api.js'

const emptyDetails = {
  tax_year: '',
  return_type: '',
  assigned_preparer: '',
  engagement_start_date: '',
  filing_deadline: '',
}
const statuses = ['In Progress', 'Waiting on Client', 'Completed']

function ClientSelection({ clients, selectedClient, onSelect, onChange }) {
  const [query, setQuery] = useState('')
  const matches = clients.filter((client) => client.client_name.toLowerCase().includes(query.trim().toLowerCase()))

  if (selectedClient) {
    return (
      <div className="selected-client-card">
        <div className="selected-client-mark" aria-hidden="true">▣</div>
        <div className="selected-client-details"><p className="eyebrow">SELECTED CLIENT</p><strong>{selectedClient.client_name}</strong><span>{selectedClient.contact_name || 'No contact name'}{selectedClient.email ? ` · ${selectedClient.email}` : ''}{selectedClient.phone ? ` · ${selectedClient.phone}` : ''}</span></div>
        <button type="button" className="row-action" onClick={onChange}>Change</button>
      </div>
    )
  }

  return (
    <div className="client-picker">
      <label htmlFor="client-search">Search and select an existing client <span>Required</span></label>
      <input id="client-search" autoFocus value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search client name" />
      <div className="client-picker-results" role="listbox" aria-label="Matching clients">
        {matches.length === 0 ? <p className="picker-empty">No matching clients.</p> : matches.map((client) => (
          <button type="button" role="option" aria-selected="false" className="client-picker-option" key={client.client_id} onClick={() => onSelect(client)}>
            <span className="picker-avatar">{client.client_name.slice(0, 1).toUpperCase()}</span>
            <span><strong>{client.client_name}</strong><small>{client.contact_name || client.email || 'Client record'}</small></span>
            <span className="picker-arrow" aria-hidden="true">›</span>
          </button>
        ))}
      </div>
    </div>
  )
}

function EngagementEditor({ kind, engagement, clients, onCancel, onSave }) {
  const creating = kind === 'create'
  const [selectedClient, setSelectedClient] = useState(null)
  const [values, setValues] = useState(creating ? emptyDetails : {
    tax_year: String(engagement.tax_year),
    return_type: engagement.return_type,
    assigned_preparer: engagement.assigned_preparer,
    engagement_start_date: engagement.engagement_start_date,
    filing_deadline: engagement.filing_deadline,
  })
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)

  function update(field, value) {
    setValues((current) => ({ ...current, [field]: value }))
  }

  async function submit(event) {
    event.preventDefault()
    setError('')
    if (creating && !selectedClient) {
      setError('Select an existing client for this engagement.')
      return
    }
    if (!String(values.tax_year).trim() || !values.return_type.trim() || !values.assigned_preparer.trim() || !values.engagement_start_date || !values.filing_deadline) {
      setError('Complete all required engagement information.')
      return
    }
    setSaving(true)
    try {
      await onSave({
        ...values,
        tax_year: String(values.tax_year).trim(),
        return_type: values.return_type.trim(),
        assigned_preparer: values.assigned_preparer.trim(),
        ...(creating ? { client_id: selectedClient.client_id } : {}),
      })
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="modal-backdrop" role="presentation">
      <section className="client-modal engagement-editor" role="dialog" aria-modal="true" aria-labelledby="engagement-form-title">
        <div className="modal-heading">
          <div><p className="eyebrow">TAX ENGAGEMENT</p><h2 id="engagement-form-title">{creating ? 'Create engagement' : 'Edit engagement information'}</h2></div>
          <button className="icon-button" type="button" aria-label="Close" onClick={onCancel}>×</button>
        </div>

        {creating && <ClientSelection clients={clients} selectedClient={selectedClient} onSelect={setSelectedClient} onChange={() => setSelectedClient(null)} />}
        {!creating && <div className="selected-client-card compact"><div className="selected-client-mark" aria-hidden="true">▣</div><div className="selected-client-details"><p className="eyebrow">CLIENT</p><strong>{engagement.client_name}</strong><span>Engagement #{engagement.engagement_id}</span></div><span className="status-pill">{engagement.engagement_status}</span></div>}

        <form className="client-form engagement-form" onSubmit={submit}>
          <div className="form-row">
            <div><label htmlFor="tax-year">Tax year <span>Required</span></label><input id="tax-year" type="number" min="1" step="1" value={values.tax_year} onChange={(event) => update('tax_year', event.target.value)} required /></div>
            <div><label htmlFor="return-type">Return type <span>Required</span></label><input id="return-type" value={values.return_type} onChange={(event) => update('return_type', event.target.value)} required /></div>
          </div>
          <label htmlFor="assigned-preparer">Assigned preparer <span>Required</span></label>
          <input id="assigned-preparer" value={values.assigned_preparer} onChange={(event) => update('assigned_preparer', event.target.value)} required />
          <div className="form-row">
            <div><label htmlFor="engagement-start-date">Engagement start date <span>Required</span></label><input id="engagement-start-date" type="date" value={values.engagement_start_date} onChange={(event) => update('engagement_start_date', event.target.value)} required /></div>
            <div><label htmlFor="filing-deadline">Filing deadline <span>Required</span></label><input id="filing-deadline" type="date" value={values.filing_deadline} onChange={(event) => update('filing_deadline', event.target.value)} required /></div>
          </div>
          {creating && <div className="initial-status-note"><span className="status-dot" /> New engagements start as <strong>In Progress</strong>.</div>}
          {error && <div className="form-error" role="alert">{error}</div>}
          <div className="modal-actions"><button className="secondary-button" type="button" onClick={onCancel}>Cancel</button><button className="primary-button" type="submit" disabled={saving}>{saving ? 'Saving…' : creating ? 'Create engagement' : 'Save details'}</button></div>
        </form>
      </section>
    </div>
  )
}

function EngagementDetails({ engagement, onClose, onEdit, onEditStatus }) {
  const rows = [
    ['Tax year', engagement.tax_year],
    ['Return type', engagement.return_type],
    ['Assigned preparer', engagement.assigned_preparer],
    ['Engagement start date', engagement.engagement_start_date],
    ['Filing deadline', engagement.filing_deadline],
  ]
  return (
    <div className="modal-backdrop" role="presentation">
      <section className="client-modal engagement-detail-modal" role="dialog" aria-modal="true" aria-labelledby="engagement-detail-title">
        <div className="modal-heading"><div><p className="eyebrow">ENGAGEMENT #{engagement.engagement_id}</p><h2 id="engagement-detail-title">{engagement.client_name}</h2></div><button className="icon-button" type="button" aria-label="Close" onClick={onClose}>×</button></div>
        <div className="engagement-detail-client"><span className="selected-client-mark" aria-hidden="true">▣</span><div><span>Client contact</span><strong>{engagement.client_contact_name || 'Not provided'}</strong><small>{engagement.client_email || 'No email'}{engagement.client_phone ? ` · ${engagement.client_phone}` : ''}</small></div></div>
        <div className="engagement-detail-grid">{rows.map(([label, value]) => <div key={label}><span>{label}</span><strong>{value}</strong></div>)}<div><span>Engagement status</span><strong><span className="status-pill">{engagement.engagement_status}</span></strong></div></div>
        <div className="modal-actions detail-actions"><button className="secondary-button" onClick={onEditStatus}>Update status</button><button className="primary-button" onClick={onEdit}>Edit engagement details</button></div>
      </section>
    </div>
  )
}

function StatusEditor({ engagement, onCancel, onSave }) {
  const [status, setStatus] = useState(engagement.engagement_status)
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)

  async function submit(event) {
    event.preventDefault()
    setSaving(true)
    setError('')
    try {
      await onSave(status)
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="modal-backdrop" role="presentation">
      <section className="client-modal status-editor" role="dialog" aria-modal="true" aria-labelledby="status-title">
        <div className="modal-heading"><div><p className="eyebrow">UC-6 · SEPARATE STATUS OPERATION</p><h2 id="status-title">Update engagement status</h2></div><button className="icon-button" type="button" aria-label="Close" onClick={onCancel}>×</button></div>
        <p className="status-client-name">{engagement.client_name} <span>·</span> Engagement #{engagement.engagement_id}</p>
        <form className="client-form" onSubmit={submit}>
          <div className="status-current-row"><span>Current status</span><span className="status-pill">{engagement.engagement_status}</span></div>
          <label htmlFor="engagement-status">New status</label>
          <select id="engagement-status" value={status} onChange={(event) => setStatus(event.target.value)}>{statuses.map((value) => <option key={value} value={value}>{value}</option>)}</select>
          {error && <div className="form-error" role="alert">{error}</div>}
          <div className="modal-actions"><button className="secondary-button" type="button" onClick={onCancel}>Cancel</button><button className="primary-button" type="submit" disabled={saving}>{saving ? 'Saving…' : 'Save status'}</button></div>
        </form>
      </section>
    </div>
  )
}

export default function EngagementsPage({ user, onLogout, onNavigate }) {
  const [clients, setClients] = useState([])
  const [engagements, setEngagements] = useState([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [notice, setNotice] = useState(null)
  const [editor, setEditor] = useState(null)
  const [selected, setSelected] = useState(null)
  const [statusEditing, setStatusEditing] = useState(null)

  async function loadData() {
    const [clientResult, engagementResult] = await Promise.all([
      api('/api/clients'),
      api('/api/engagements'),
    ])
    setClients(clientResult.clients)
    setEngagements(engagementResult.engagements)
  }

  useEffect(() => {
    loadData().catch((err) => setNotice({ kind: 'error', text: err.message })).finally(() => setLoading(false))
  }, [])

  const filteredEngagements = useMemo(() => {
    const query = search.trim().toLowerCase()
    if (!query) return engagements
    return engagements.filter((item) => [item.client_name, item.tax_year, item.return_type, item.assigned_preparer, item.engagement_status].some((value) => String(value).toLowerCase().includes(query)))
  }, [engagements, search])

  async function saveDetails(values) {
    const creating = editor.kind === 'create'
    const url = creating ? '/api/engagements' : `/api/engagements/${editor.engagement.engagement_id}`
    const result = await api(url, { method: creating ? 'POST' : 'PUT', body: JSON.stringify(values) })
    await loadData()
    setEditor(null)
    setSelected(null)
    setNotice({ kind: 'success', text: result.message })
  }

  function startEdit() {
    setEditor({ kind: 'edit', engagement: selected })
    setSelected(null)
    setNotice(null)
  }

  async function saveStatus(status) {
    const result = await api(`/api/engagements/${statusEditing.engagement_id}/status`, {
      method: 'PATCH',
      body: JSON.stringify({ engagement_status: status }),
    })
    await loadData()
    setStatusEditing(null)
    setSelected(null)
    setNotice({ kind: 'success', text: result.message })
  }

  return (
    <main className="workspace-page engagements-workspace">
      <WorkspaceHeader user={user} activeModule="engagements" onNavigate={onNavigate} onLogout={onLogout} />
      <section className="clients-content engagements-content">
        <div className="clients-title-row">
          <div><p className="eyebrow">ENGAGEMENT MANAGEMENT</p><h1>Tax Engagements</h1><p className="clients-subtitle">Create engagements, update their details, and manage their status.</p></div>
          <button className="primary-button add-client-button" onClick={() => { setNotice(null); setEditor({ kind: 'create' }) }}><span aria-hidden="true">＋</span> New engagement</button>
        </div>

        {notice && <div className={`client-notice ${notice.kind}`} role={notice.kind === 'error' ? 'alert' : 'status'}><span>{notice.kind === 'success' ? '✓' : '!'}</span>{notice.text}<button type="button" aria-label="Dismiss message" onClick={() => setNotice(null)}>×</button></div>}

        <section className="client-list-card" aria-labelledby="engagement-list-heading">
          <div className="client-list-heading engagement-list-heading"><div><h2 id="engagement-list-heading">All tax engagements</h2><p>Select an engagement to review or update it.</p></div><div className="client-count"><strong>{engagements.length}</strong><span>{engagements.length === 1 ? 'engagement' : 'engagements'}</span></div></div>
          <div className="engagement-search-wrap"><label className="sr-only" htmlFor="engagement-search">Search engagements</label><span aria-hidden="true">⌕</span><input id="engagement-search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search client, tax year, return type, preparer, or status" /></div>
          {loading ? <div className="client-list-state"><span className="spinner" /> Loading engagements…</div> : filteredEngagements.length === 0 ? (
            <div className="client-list-state empty-clients"><div className="empty-client-icon" aria-hidden="true">▤</div><h3>{engagements.length ? 'No matching engagements' : 'No engagements added yet'}</h3><p>{engagements.length ? 'Try a different search.' : 'Create an engagement for an existing client.'}</p>{!engagements.length && clients.length > 0 && <button className="secondary-button" onClick={() => setEditor({ kind: 'create' })}>Create first engagement</button>}{!clients.length && <button className="secondary-button" onClick={() => onNavigate('clients')}>Go to Clients</button>}</div>
          ) : (
            <div className="client-table-scroll"><table className="client-table engagement-table"><thead><tr><th>CLIENT</th><th>TAX YEAR / TYPE</th><th>PREPARER</th><th>FILING DEADLINE</th><th>STATUS</th><th><span className="sr-only">Actions</span></th></tr></thead><tbody>
              {filteredEngagements.map((item) => <tr key={item.engagement_id}><td><strong>{item.client_name}</strong><span className="client-id">Engagement #{item.engagement_id}</span></td><td>{item.tax_year} · {item.return_type}</td><td>{item.assigned_preparer}</td><td>{item.filing_deadline}</td><td><span className={`status-pill ${item.engagement_status === 'Completed' ? 'completed' : item.engagement_status === 'Waiting on Client' ? 'waiting' : ''}`}>{item.engagement_status}</span></td><td className="client-actions"><button className="row-action" onClick={() => { setSelected(item); setNotice(null) }}>View</button></td></tr>)}
            </tbody></table></div>
          )}
          {!loading && filteredEngagements.length > 0 && <div className="client-list-footer">Showing {filteredEngagements.length} {filteredEngagements.length === 1 ? 'engagement' : 'engagements'}</div>}
        </section>
      </section>

      {editor && <EngagementEditor kind={editor.kind} engagement={editor.engagement} clients={clients} onCancel={() => setEditor(null)} onSave={saveDetails} />}
      {selected && <EngagementDetails engagement={selected} onClose={() => setSelected(null)} onEdit={startEdit} onEditStatus={() => { setStatusEditing(selected); setSelected(null) }} />}
      {statusEditing && <StatusEditor engagement={statusEditing} onCancel={() => setStatusEditing(null)} onSave={saveStatus} />}
    </main>
  )
}
