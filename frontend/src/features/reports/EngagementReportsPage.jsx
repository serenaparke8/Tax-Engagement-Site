import { useEffect, useState } from 'react'
import WorkspaceHeader from '../../components/WorkspaceHeader.jsx'
import { api } from '../../services/api.js'

const initialFilters = { status: '', tax_year: '', assigned_preparer: '' }

function displayDate(value) {
  if (!value) return '—'
  const [year, month, day] = value.split('-').map(Number)
  return new Date(year, month - 1, day).toLocaleDateString(undefined, {
    year: 'numeric', month: 'short', day: 'numeric',
  })
}

export default function EngagementReportsPage({ user, onLogout, onNavigate }) {
  const [criteria, setCriteria] = useState(null)
  const [filters, setFilters] = useState(initialFilters)
  const [engagements, setEngagements] = useState([])
  const [loadingCriteria, setLoadingCriteria] = useState(true)
  const [generating, setGenerating] = useState(false)
  const [generated, setGenerated] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    api('/api/reports/criteria')
      .then((result) => setCriteria(result.criteria))
      .catch((requestError) => setError(requestError.message))
      .finally(() => setLoadingCriteria(false))
  }, [])

  function updateFilter(field, value) {
    setFilters((current) => ({ ...current, [field]: value }))
  }

  async function generateReport(event) {
    event.preventDefault()
    setError('')
    setGenerating(true)
    const query = new URLSearchParams(
      Object.entries(filters).filter(([, value]) => value !== ''),
    )
    try {
      const result = await api(`/api/reports/engagements?${query.toString()}`)
      setEngagements(result.engagements)
      setGenerated(true)
    } catch (requestError) {
      setError(requestError.message)
      setGenerated(false)
    } finally {
      setGenerating(false)
    }
  }

  return (
    <main className="workspace-page engagement-reports-workspace">
      <WorkspaceHeader user={user} activeModule="reports" onNavigate={onNavigate} onLogout={onLogout} />
      <section className="clients-content engagement-reports-content">
        <div className="clients-title-row"><div><p className="eyebrow">ENGAGEMENT REPORTING</p><h1>Engagement Reports</h1><p className="clients-subtitle">Select one or more criteria to generate a report of matching tax engagements.</p></div></div>
        {error && <div className="client-notice error" role="alert"><span>!</span>{error}</div>}

        <section className="client-list-card report-criteria-card" aria-labelledby="report-criteria-heading">
          <div className="client-list-heading"><div><h2 id="report-criteria-heading">Report criteria</h2><p>Combine engagement status, tax year, and assigned preparer filters.</p></div></div>
          {loadingCriteria ? <div className="client-list-state"><span className="spinner" /> Loading report criteria…</div> : criteria && (
            <form className="engagement-report-filters" onSubmit={generateReport}>
              <div><label htmlFor="report-status">Engagement Status</label><select id="report-status" value={filters.status} onChange={(event) => updateFilter('status', event.target.value)}><option value="">All statuses</option>{criteria.statuses.map((status) => <option key={status} value={status}>{status}</option>)}</select></div>
              <div><label htmlFor="report-tax-year">Tax Year</label><select id="report-tax-year" value={filters.tax_year} onChange={(event) => updateFilter('tax_year', event.target.value)}><option value="">All tax years</option>{criteria.tax_years.map((year) => <option key={year} value={year}>{year}</option>)}</select></div>
              <div><label htmlFor="report-preparer">Assigned Preparer</label><select id="report-preparer" value={filters.assigned_preparer} onChange={(event) => updateFilter('assigned_preparer', event.target.value)}><option value="">All preparers</option>{criteria.assigned_preparers.map((preparer) => <option key={preparer} value={preparer}>{preparer}</option>)}</select></div>
              <button className="primary-button" type="submit" disabled={generating}>{generating ? 'Generating…' : 'Generate report'}</button>
            </form>
          )}
        </section>

        <section className="client-list-card report-results-card" aria-labelledby="report-results-heading" aria-live="polite">
          <div className="client-list-heading"><div><h2 id="report-results-heading">Report results</h2><p>{generated ? 'Engagements matching the selected criteria.' : 'Generate a report to view matching engagement records.'}</p></div>{generated && <div className="client-count"><strong>{engagements.length}</strong><span>{engagements.length === 1 ? 'engagement' : 'engagements'}</span></div>}</div>
          {!generated ? (
            <div className="client-list-state report-prompt-state"><p>Select any combination of criteria above, then generate the report.</p></div>
          ) : engagements.length === 0 ? (
            <div className="client-list-state empty-clients"><div className="empty-client-icon" aria-hidden="true">⌕</div><h3>No engagements match the selected criteria.</h3><p>Adjust the selected filters and generate the report again.</p></div>
          ) : (
            <div className="client-table-scroll"><table className="client-table engagement-report-table"><thead><tr><th>CLIENT</th><th>ENGAGEMENT ID</th><th>TAX YEAR</th><th>RETURN TYPE</th><th>ASSIGNED PREPARER</th><th>ENGAGEMENT START DATE</th><th>FILING DEADLINE</th><th>ENGAGEMENT STATUS</th></tr></thead><tbody>
              {engagements.map((item) => <tr key={item.engagement_id}><td><strong>{item.client_name}</strong></td><td>#{item.engagement_id}</td><td>{item.tax_year}</td><td>{item.return_type}</td><td>{item.assigned_preparer}</td><td>{displayDate(item.engagement_start_date)}</td><td>{displayDate(item.filing_deadline)}</td><td><span className={`engagement-status-pill ${item.engagement_status === 'Completed' ? 'completed' : item.engagement_status === 'Waiting on Client' ? 'waiting' : 'in-progress'}`}>{item.engagement_status}</span></td></tr>)}
            </tbody></table></div>
          )}
        </section>
      </section>
    </main>
  )
}
