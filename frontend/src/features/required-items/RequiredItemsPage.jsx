import { useEffect, useMemo, useState } from 'react'
import WorkspaceHeader from '../../components/WorkspaceHeader.jsx'
import { api } from '../../services/api.js'

const itemStatuses = ['Outstanding', 'Received']
const customItemOption = 'Other / Custom Item'
const requiredItemCategories = [
  { name: 'Personal Information', items: ["Driver's License", 'Social Security Cards', 'Prior Year Tax Return', 'Dependent Information'] },
  { name: 'Income Documents', items: ['W-2', '1099-NEC', '1099-MISC', '1099-INT', '1099-DIV', '1099-R', 'SSA-1099', '1099-K'] },
  { name: 'Deductions & Expenses', items: ['Mortgage Interest Statement (1098)', 'Property Tax Statement', 'Charitable Contribution Records', 'Medical Expense Records'] },
  { name: 'Business & Self-Employment', items: ['Business Income Records', 'Business Expense Records', 'Mileage Log'] },
  { name: 'Education', items: ['Form 1098-T', 'Student Loan Interest Statement (1098-E)'] },
  { name: 'Other Tax Information', items: ['Estimated Tax Payments', 'Health Insurance Information'] },
]

function itemStatusClass(status) {
  return status === 'Received' ? 'received' : 'outstanding'
}

function DeleteRequiredItemConfirmation({ item, onCancel, onConfirm, deleting }) {
  return (
    <div className="modal-backdrop" role="presentation">
      <section className="client-modal confirmation-modal" role="alertdialog" aria-modal="true" aria-labelledby="delete-required-item-title" aria-describedby="delete-required-item-description">
        <p className="eyebrow">REMOVE REQUIRED ITEM</p>
        <h2 id="delete-required-item-title">Delete {item.required_item_description}?</h2>
        <p id="delete-required-item-description">This will remove this item for <strong>{item.client_name}</strong>, Engagement #{item.engagement_id} ({item.tax_year} · {item.return_type}). The client and engagement will remain.</p>
        <div className="modal-actions"><button className="secondary-button" type="button" onClick={onCancel} disabled={deleting}>Cancel</button><button className="delete-confirm-button" type="button" onClick={onConfirm} disabled={deleting}>{deleting ? 'Deleting…' : 'Delete required item'}</button></div>
      </section>
    </div>
  )
}

export default function RequiredItemsPage({ user, onLogout, onNavigate }) {
  const [engagements, setEngagements] = useState([])
  const [selectedEngagementId, setSelectedEngagementId] = useState('')
  const [items, setItems] = useState([])
  const [outstandingItems, setOutstandingItems] = useState([])
  const [selectedCategory, setSelectedCategory] = useState('')
  const [selectedRequiredItem, setSelectedRequiredItem] = useState('')
  const [customDescription, setCustomDescription] = useState('')
  const [loading, setLoading] = useState(true)
  const [itemsLoading, setItemsLoading] = useState(false)
  const [savingItem, setSavingItem] = useState(false)
  const [updatingItemId, setUpdatingItemId] = useState(null)
  const [deleteTarget, setDeleteTarget] = useState(null)
  const [deletingItem, setDeletingItem] = useState(false)
  const [notice, setNotice] = useState(null)

  const selectedEngagement = useMemo(
    () => engagements.find((engagement) => String(engagement.engagement_id) === selectedEngagementId),
    [engagements, selectedEngagementId],
  )
  const isCustomItem = selectedRequiredItem === customItemOption
  const categoryOptions = requiredItemCategories.find((category) => category.name === selectedCategory)?.items || []

  async function loadOutstandingItems() {
    const result = await api('/api/required-items/outstanding')
    setOutstandingItems(result.required_items)
  }

  async function loadEngagementItems(engagementId = selectedEngagementId) {
    if (!engagementId) {
      setItems([])
      return
    }
    setItemsLoading(true)
    try {
      const result = await api(`/api/required-items?engagement_id=${encodeURIComponent(engagementId)}`)
      setItems(result.required_items)
    } finally {
      setItemsLoading(false)
    }
  }

  useEffect(() => {
    Promise.all([api('/api/engagements'), api('/api/required-items/outstanding')])
      .then(([engagementResult, outstandingResult]) => {
        setEngagements(engagementResult.engagements)
        setOutstandingItems(outstandingResult.required_items)
        if (engagementResult.engagements.length) {
          setSelectedEngagementId(String(engagementResult.engagements[0].engagement_id))
        }
      })
      .catch((error) => setNotice({ kind: 'error', text: error.message }))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    loadEngagementItems().catch((error) => setNotice({ kind: 'error', text: error.message }))
  }, [selectedEngagementId])

  async function addRequiredItem(event) {
    event.preventDefault()
    setNotice(null)
    const cleanDescription = (isCustomItem ? customDescription : selectedRequiredItem).trim()
    if (!selectedEngagementId || !selectedCategory || !selectedRequiredItem || !cleanDescription) {
      setNotice({ kind: 'error', text: 'Select a category and required item. Enter a description for a custom item.' })
      return
    }
    setSavingItem(true)
    try {
      const result = await api('/api/required-items', {
        method: 'POST',
        body: JSON.stringify({
          engagement_id: Number(selectedEngagementId),
          required_item_description: cleanDescription,
        }),
      })
      setSelectedCategory('')
      setSelectedRequiredItem('')
      setCustomDescription('')
      await Promise.all([loadEngagementItems(), loadOutstandingItems()])
      setNotice({ kind: 'success', text: result.message })
    } catch (error) {
      setNotice({ kind: error.message.toLowerCase().includes('already listed') ? 'warning' : 'error', text: error.message })
    } finally {
      setSavingItem(false)
    }
  }

  async function updateItemStatus(item, status) {
    setNotice(null)
    setUpdatingItemId(item.required_item_id)
    try {
      const result = await api(`/api/required-items/${item.required_item_id}/status`, {
        method: 'PATCH',
        body: JSON.stringify({ item_status: status }),
      })
      setItems((current) => current.map((currentItem) => (
        currentItem.required_item_id === item.required_item_id
          ? result.required_item
          : currentItem
      )))
      await loadOutstandingItems()
      setNotice({ kind: 'success', text: result.message })
    } catch (error) {
      setNotice({ kind: 'error', text: error.message })
    } finally {
      setUpdatingItemId(null)
    }
  }

  async function deleteRequiredItem() {
    if (!deleteTarget) return
    setDeletingItem(true)
    setNotice(null)
    try {
      const result = await api(`/api/required-items/${deleteTarget.required_item_id}`, { method: 'DELETE' })
      await Promise.all([loadEngagementItems(), loadOutstandingItems()])
      setDeleteTarget(null)
      setNotice({ kind: 'success', text: result.message })
    } catch (error) {
      setDeleteTarget(null)
      setNotice({ kind: 'error', text: error.message })
    } finally {
      setDeletingItem(false)
    }
  }

  return (
    <main className="workspace-page required-items-workspace">
      <WorkspaceHeader user={user} activeModule="requiredItems" onNavigate={onNavigate} onLogout={onLogout} />
      <section className="clients-content required-items-content">
        <div className="clients-title-row">
          <div><p className="eyebrow">REQUIRED INFORMATION</p><h1>Required Items</h1><p className="clients-subtitle">Review outstanding information and update item status for each tax engagement.</p></div>
        </div>

        {notice && <div className={`client-notice ${notice.kind}`} role={notice.kind === 'error' ? 'alert' : 'status'}><span>{notice.kind === 'success' ? '✓' : '!'}</span>{notice.text}<button type="button" aria-label="Dismiss message" onClick={() => setNotice(null)}>×</button></div>}

        <section className="client-list-card required-item-manager" aria-labelledby="required-item-manager-heading">
          <div className="client-list-heading"><div><h2 id="required-item-manager-heading">Update document status</h2><p>Choose a tax engagement to review its required items.</p></div></div>
          <div className="required-item-controls">
            <label htmlFor="required-item-engagement">Tax engagement <span>Required</span></label>
            <select id="required-item-engagement" value={selectedEngagementId} onChange={(event) => { setSelectedEngagementId(event.target.value); setSelectedCategory(''); setSelectedRequiredItem(''); setCustomDescription(''); setNotice(null) }} disabled={loading || engagements.length === 0}>
              <option value="">Select a tax engagement</option>
              {engagements.map((engagement) => <option key={engagement.engagement_id} value={engagement.engagement_id}>{engagement.client_name} — {engagement.tax_year} {engagement.return_type} (Engagement #{engagement.engagement_id})</option>)}
            </select>
          </div>

          {selectedEngagement && <div className="required-item-engagement-summary"><span className="selected-client-mark" aria-hidden="true">▤</span><div><p className="eyebrow">SELECTED ENGAGEMENT</p><strong>{selectedEngagement.client_name}</strong><span>Engagement #{selectedEngagement.engagement_id} · {selectedEngagement.tax_year} · {selectedEngagement.return_type}</span></div></div>}

          <form className="required-item-add-form" onSubmit={addRequiredItem}>
            <div><label htmlFor="required-item-category">Category <span>Required</span></label><select id="required-item-category" value={selectedCategory} onChange={(event) => { setSelectedCategory(event.target.value); setSelectedRequiredItem(''); setCustomDescription('') }} required disabled={!selectedEngagementId}><option value="">Select a category</option>{requiredItemCategories.map((category) => <option key={category.name} value={category.name}>{category.name}</option>)}</select></div>
            <div><label htmlFor="required-item-choice">Required item <span>Required</span></label><select id="required-item-choice" value={selectedRequiredItem} onChange={(event) => { setSelectedRequiredItem(event.target.value); if (event.target.value !== customItemOption) setCustomDescription('') }} required disabled={!selectedCategory}><option value="">Select a required item</option>{categoryOptions.map((item) => <option key={item} value={item}>{item}</option>)}<option value={customItemOption}>{customItemOption}</option></select></div>
            {isCustomItem && <div className="required-item-custom-field"><label htmlFor="required-item-description">Custom item description <span>Required</span></label><input id="required-item-description" value={customDescription} onChange={(event) => setCustomDescription(event.target.value)} placeholder="Enter the information needed from the client" required disabled={!selectedEngagementId} /></div>}
            <button className="primary-button" type="submit" disabled={savingItem || !selectedEngagementId}>{savingItem ? 'Adding…' : 'Add item'}</button>
          </form>

          <div className="required-items-list-heading"><div><h3>Items for this engagement</h3><p>Choose Outstanding or Received to update an existing item.</p></div></div>
          {loading || itemsLoading ? <div className="client-list-state"><span className="spinner" /> Loading required items…</div> : !selectedEngagement ? (
            <div className="client-list-state empty-clients"><h3>{engagements.length ? 'Select a tax engagement' : 'No tax engagements available'}</h3><p>{engagements.length ? 'Choose an engagement above to review its required items.' : 'Create a tax engagement before adding required items.'}</p></div>
          ) : items.length === 0 ? (
            <div className="client-list-state empty-clients"><div className="empty-client-icon" aria-hidden="true">☷</div><h3>No required items for this engagement</h3><p>Add an item above to track information requested from the client.</p></div>
          ) : (
            <div className="client-table-scroll"><table className="client-table required-items-table"><thead><tr><th>REQUIRED ITEM</th><th>CURRENT STATUS</th><th>ACTIONS</th></tr></thead><tbody>
              {items.map((item) => <tr key={item.required_item_id}><td><strong>{item.required_item_description}</strong><span className="client-id">Item #{item.required_item_id}</span></td><td><span className={`item-status-pill ${itemStatusClass(item.item_status)}`}>{item.item_status}</span></td><td><div className="required-item-row-actions"><label className="sr-only" htmlFor={`item-status-${item.required_item_id}`}>Update status for {item.required_item_description}</label><select id={`item-status-${item.required_item_id}`} className="required-item-status-select" value={item.item_status} disabled={updatingItemId === item.required_item_id || deletingItem} onChange={(event) => updateItemStatus(item, event.target.value)}>{itemStatuses.map((status) => <option key={status} value={status}>{status}</option>)}</select><button className="row-action danger required-item-delete" type="button" onClick={() => setDeleteTarget(item)} disabled={updatingItemId === item.required_item_id || deletingItem}>Delete</button></div></td></tr>)}
            </tbody></table></div>
          )}
        </section>

        <section className="client-list-card outstanding-items-card" aria-labelledby="outstanding-items-heading">
          <div className="client-list-heading"><div><h2 id="outstanding-items-heading">Outstanding client information</h2><p>All required items currently marked Outstanding across tax engagements.</p></div><div className="client-count"><strong>{outstandingItems.length}</strong><span>{outstandingItems.length === 1 ? 'outstanding item' : 'outstanding items'}</span></div></div>
          {loading ? <div className="client-list-state"><span className="spinner" /> Loading outstanding items…</div> : outstandingItems.length === 0 ? (
            <div className="client-list-state empty-clients"><div className="empty-client-icon" aria-hidden="true">✓</div><h3>No outstanding client information</h3><p>Required items marked Received are not shown in this view.</p></div>
          ) : (
            <div className="client-table-scroll"><table className="client-table outstanding-items-table"><thead><tr><th>CLIENT</th><th>TAX ENGAGEMENT</th><th>OUTSTANDING INFORMATION</th><th>STATUS</th></tr></thead><tbody>
              {outstandingItems.map((item) => <tr key={item.required_item_id}><td><strong>{item.client_name}</strong></td><td><strong>Engagement #{item.engagement_id}</strong><span className="client-id">{item.tax_year} · {item.return_type}</span></td><td>{item.required_item_description}</td><td><span className="item-status-pill outstanding">Outstanding</span></td></tr>)}
            </tbody></table></div>
          )}
        </section>
      </section>
      {deleteTarget && <DeleteRequiredItemConfirmation item={deleteTarget} onCancel={() => setDeleteTarget(null)} onConfirm={deleteRequiredItem} deleting={deletingItem} />}
    </main>
  )
}
