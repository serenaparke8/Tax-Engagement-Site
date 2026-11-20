import { useEffect, useState } from 'react'
import WorkspaceHeader from '../../components/WorkspaceHeader.jsx'
import { api } from '../../services/api.js'

const emptyClient = { client_name: '', contact_name: '', email: '', phone: '' }

function ClientEditor({ client, onCancel, onSave }) {
  const [values, setValues] = useState(client ? {
    client_name: client.client_name,
    contact_name: client.contact_name || '',
    email: client.email || '',
    phone: client.phone || '',
  } : emptyClient)
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  const editing = Boolean(client)

  function update(field, value) {
    setValues((current) => ({ ...current, [field]: value }))
  }

  async function submit(event) {
    event.preventDefault()
    setError('')
    if (!values.client_name.trim()) {
      setError('Client name is required.')
      return
    }
    setSaving(true)
    try {
      await onSave(Object.fromEntries(Object.entries(values).map(([key, value]) => [key, value.trim()])))
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={(event) => event.target === event.currentTarget && onCancel()}>
      <section className="client-modal" role="dialog" aria-modal="true" aria-labelledby="client-form-title">
        <div className="modal-heading">
          <div><p className="eyebrow">CLIENT RECORD</p><h2 id="client-form-title">{editing ? 'Update client' : 'Add a client'}</h2></div>
          <button className="icon-button" type="button" aria-label="Close" onClick={onCancel}>×</button>
        </div>
        <form className="client-form" onSubmit={submit}>
          <label htmlFor="client-name">Client name <span>Required</span></label>
          <input id="client-name" autoFocus value={values.client_name} onChange={(event) => update('client_name', event.target.value)} required />
          <label htmlFor="contact-name">Contact name <span>Optional</span></label>
          <input id="contact-name" value={values.contact_name || ''} onChange={(event) => update('contact_name', event.target.value)} />
          <div className="form-row">
            <div><label htmlFor="client-email">Email <span>Optional</span></label><input id="client-email" value={values.email || ''} onChange={(event) => update('email', event.target.value)} /></div>
            <div><label htmlFor="client-phone">Phone <span>Optional</span></label><input id="client-phone" value={values.phone || ''} onChange={(event) => update('phone', event.target.value)} /></div>
          </div>
          {error && <div className="form-error" role="alert">{error}</div>}
          <div className="modal-actions"><button className="secondary-button" type="button" onClick={onCancel}>Cancel</button><button className="primary-button" type="submit" disabled={saving}>{saving ? 'Saving…' : editing ? 'Save changes' : 'Add client'}</button></div>
        </form>
      </section>
    </div>
  )
}

function DeleteConfirmation({ client, onCancel, onConfirm, deleting }) {
  return (
    <div className="modal-backdrop" role="presentation">
      <section className="client-modal confirmation-modal" role="alertdialog" aria-modal="true" aria-labelledby="delete-title" aria-describedby="delete-description">
        <p className="eyebrow">REMOVE CLIENT</p>
        <h2 id="delete-title">Delete {client.client_name}?</h2>
        <p id="delete-description">This will delete the client record if no tax engagements are associated with it.</p>
        <div className="modal-actions"><button className="secondary-button" type="button" onClick={onCancel}>Cancel</button><button className="delete-confirm-button" type="button" onClick={onConfirm} disabled={deleting}>{deleting ? 'Deleting…' : 'Delete client'}</button></div>
      </section>
    </div>
  )
}

export default function ClientsPage({ user, onLogout, onNavigate }) {
  const [clients, setClients] = useState([])
  const [loading, setLoading] = useState(true)
  const [modalClient, setModalClient] = useState(undefined)
  const [deleteClient, setDeleteClient] = useState(null)
  const [deleting, setDeleting] = useState(false)
  const [notice, setNotice] = useState(null)

  async function loadClients() {
    const result = await api('/api/clients')
    setClients(result.clients)
  }

  useEffect(() => {
    loadClients().catch((err) => setNotice({ kind: 'error', text: err.message })).finally(() => setLoading(false))
  }, [])

  function startAdd() {
    setNotice(null)
    setModalClient(null)
  }

  function startEdit(client) {
    setNotice(null)
    setModalClient(client)
  }

  async function saveClient(values) {
    const editing = Boolean(modalClient)
    const url = editing ? `/api/clients/${modalClient.client_id}` : '/api/clients'
    await api(url, { method: editing ? 'PUT' : 'POST', body: JSON.stringify(values) })
    await loadClients()
    setModalClient(undefined)
    setNotice({ kind: 'success', text: editing ? 'Client updated successfully.' : 'Client added successfully.' })
  }

  async function confirmDelete() {
    setDeleting(true)
    setNotice(null)
    try {
      const result = await api(`/api/clients/${deleteClient.client_id}`, { method: 'DELETE' })
      await loadClients()
      setNotice({ kind: 'success', text: result.message })
    } catch (err) {
      setNotice({ kind: 'error', text: err.message })
    } finally {
      setDeleting(false)
      setDeleteClient(null)
    }
  }

  return (
    <main className="workspace-page clients-workspace">
      <WorkspaceHeader user={user} activeModule="clients" onNavigate={onNavigate} onLogout={onLogout} />

      <section className="clients-content">
        <div className="clients-title-row">
          <div><p className="eyebrow">CLIENT RECORDS</p><h1>Clients</h1><p className="clients-subtitle">Keep client contact information organized in one place.</p></div>
          <button className="primary-button add-client-button" onClick={startAdd}><span aria-hidden="true">＋</span> Add client</button>
        </div>

        {notice && <div className={`client-notice ${notice.kind}`} role={notice.kind === 'error' ? 'alert' : 'status'}><span>{notice.kind === 'success' ? '✓' : '!'}</span>{notice.text}<button type="button" aria-label="Dismiss message" onClick={() => setNotice(null)}>×</button></div>}

        <section className="client-list-card" aria-labelledby="client-list-heading">
          <div className="client-list-heading"><div><h2 id="client-list-heading">All clients</h2><p>Client contact records</p></div><div className="client-count"><strong>{clients.length}</strong><span>{clients.length === 1 ? 'client' : 'clients'}</span></div></div>
          {loading ? <div className="client-list-state"><span className="spinner" /> Loading client records…</div> : clients.length === 0 ? (
            <div className="client-list-state empty-clients"><div className="empty-client-icon" aria-hidden="true">▤</div><h3>No clients added yet</h3><p>Add a client to begin organizing contact information.</p><button className="secondary-button" onClick={startAdd}>Add first client</button></div>
          ) : (
            <div className="client-table-scroll"><table className="client-table"><thead><tr><th>CLIENT</th><th>CONTACT</th><th>EMAIL</th><th>PHONE</th><th><span className="sr-only">Actions</span></th></tr></thead><tbody>
              {clients.map((client) => <tr key={client.client_id}><td><strong>{client.client_name}</strong><span className="client-id">Client #{client.client_id}</span></td><td>{client.contact_name || <span className="muted-value">—</span>}</td><td>{client.email || <span className="muted-value">—</span>}</td><td>{client.phone || <span className="muted-value">—</span>}</td><td className="client-actions"><button className="row-action" onClick={() => startEdit(client)}>Edit</button><button className="row-action danger" onClick={() => { setNotice(null); setDeleteClient(client) }}>Delete</button></td></tr>)}
            </tbody></table></div>
          )}
          {!loading && clients.length > 0 && <div className="client-list-footer">Showing {clients.length} {clients.length === 1 ? 'client' : 'clients'}</div>}
        </section>
      </section>

      {modalClient !== undefined && <ClientEditor client={modalClient} onCancel={() => setModalClient(undefined)} onSave={saveClient} />}
      {deleteClient && <DeleteConfirmation client={deleteClient} onCancel={() => setDeleteClient(null)} onConfirm={confirmDelete} deleting={deleting} />}
    </main>
  )
}
