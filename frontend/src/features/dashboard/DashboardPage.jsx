import { useEffect, useState } from 'react'
import WorkspaceHeader from '../../components/WorkspaceHeader.jsx'
import { api } from '../../services/api.js'

function displayDate(value) {
  if (!value) return '—'
  const [year, month, day] = value.split('-').map(Number)
  return new Date(year, month - 1, day).toLocaleDateString(undefined, {
    year: 'numeric', month: 'short', day: 'numeric',
  })
}

function statusClass(status) {
  if (status === 'Completed') return 'completed'
  if (status === 'Waiting on Client') return 'waiting'
  return 'in-progress'
}

function EngagementTable({ engagements, emptyMessage }) {
  if (engagements.length === 0) {
    return <div className="client-list-state dashboard-section-empty"><p>{emptyMessage}</p></div>
  }

  return (
    <div className="client-table-scroll">
      <table className="client-table dashboard-engagement-table">
        <thead><tr><th>CLIENT / ENGAGEMENT</th><th>TAX YEAR / RETURN TYPE</th><th>ASSIGNED PREPARER</th><th>FILING DEADLINE</th><th>STATUS</th><th>OUTSTANDING ITEMS</th></tr></thead>
        <tbody>{engagements.map((item) => (
          <tr key={item.engagement_id}>
            <td><strong>{item.client_name}</strong><span className="client-id">Engagement #{item.engagement_id}</span></td>
            <td><strong>{item.tax_year}</strong><span className="client-id">{item.return_type}</span></td>
            <td>{item.assigned_preparer}</td>
            <td>{displayDate(item.filing_deadline)}</td>
            <td><span className={`engagement-status-pill ${statusClass(item.engagement_status)}`}>{item.engagement_status}</span></td>
            <td>{item.outstanding_item_count}</td>
          </tr>
        ))}</tbody>
      </table>
    </div>
  )
}

export default function DashboardPage({ user, onLogout, onNavigate }) {
  const [dashboard, setDashboard] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    api('/api/dashboard')
      .then((result) => setDashboard(result.dashboard))
      .catch((requestError) => setError(requestError.message))
      .finally(() => setLoading(false))
  }, [])

  return (
    <main className="workspace-page dashboard-workspace">
      <WorkspaceHeader user={user} activeModule="dashboard" onNavigate={onNavigate} onLogout={onLogout} />
      <section className="clients-content dashboard-content">
        <div className="clients-title-row"><div><p className="eyebrow">TAX PRACTICE OVERVIEW</p><h1>Engagement Dashboard</h1><p className="clients-subtitle">A summary of current engagements, filing deadlines, and outstanding client information.</p></div></div>
        {error && <div className="client-notice error" role="alert"><span>!</span>{error}</div>}
        {loading ? <div className="client-list-state"><span className="spinner" /> Loading dashboard…</div> : error ? null : !dashboard?.has_engagements ? (
          <section className="client-list-card dashboard-empty-card" aria-live="polite"><div className="client-list-state empty-clients"><div className="empty-client-icon" aria-hidden="true">▤</div><h2>No engagement records are available.</h2><p>Create a tax engagement to see the dashboard overview.</p></div></section>
        ) : (
          <>
            <section className="dashboard-summary-grid" aria-label="Engagement summary">
              <article className="dashboard-summary-card active-summary"><span>ACTIVE ENGAGEMENTS</span><strong>{dashboard.summary.active_engagements}</strong><small>In Progress or Waiting on Client</small></article>
              <article className="dashboard-summary-card waiting-summary"><span>AWAITING CLIENT</span><strong>{dashboard.summary.waiting_on_client}</strong><small>Waiting on Client status</small></article>
              <article className="dashboard-summary-card deadline-summary"><span>DUE IN 14 DAYS</span><strong>{dashboard.summary.deadlines_within_14_days}</strong><small>Today through day 14</small></article>
              <article className="dashboard-summary-card completed-summary"><span>COMPLETED</span><strong>{dashboard.summary.completed_engagements}</strong><small>Completed engagements</small></article>
            </section>

            <section className="client-list-card dashboard-list-card" aria-labelledby="active-engagements-heading">
              <div className="client-list-heading"><div><h2 id="active-engagements-heading">Active engagements</h2><p>Engagements in progress or waiting on the client.</p></div><div className="client-count"><strong>{dashboard.active_engagements.length}</strong><span>{dashboard.active_engagements.length === 1 ? 'active engagement' : 'active engagements'}</span></div></div>
              <EngagementTable engagements={dashboard.active_engagements} emptyMessage="There are no active engagements." />
            </section>

            <section className="client-list-card dashboard-list-card" aria-labelledby="completed-engagements-heading">
              <div className="client-list-heading"><div><h2 id="completed-engagements-heading">Completed engagements</h2><p>Engagements marked Completed.</p></div><div className="client-count"><strong>{dashboard.completed_engagements.length}</strong><span>{dashboard.completed_engagements.length === 1 ? 'completed engagement' : 'completed engagements'}</span></div></div>
              <EngagementTable engagements={dashboard.completed_engagements} emptyMessage="There are no completed engagements." />
            </section>
          </>
        )}
      </section>
    </main>
  )
}
