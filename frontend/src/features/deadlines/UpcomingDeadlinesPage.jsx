import { useEffect, useState } from 'react'
import WorkspaceHeader from '../../components/WorkspaceHeader.jsx'
import { api } from '../../services/api.js'

function displayDate(isoDate) {
  const [year, month, day] = isoDate.split('-').map(Number)
  return new Date(year, month - 1, day).toLocaleDateString(undefined, {
    year: 'numeric', month: 'short', day: 'numeric',
  })
}

export default function UpcomingDeadlinesPage({ user, onLogout, onNavigate }) {
  const [deadlines, setDeadlines] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    api('/api/deadlines/upcoming')
      .then((result) => setDeadlines(result.deadlines))
      .catch((requestError) => setError(requestError.message))
      .finally(() => setLoading(false))
  }, [])

  return (
    <main className="workspace-page deadlines-workspace">
      <WorkspaceHeader user={user} activeModule="deadlines" onNavigate={onNavigate} onLogout={onLogout} />
      <section className="clients-content deadlines-content">
        <div className="clients-title-row">
          <div><p className="eyebrow">FILING SCHEDULE</p><h1>Upcoming Deadlines</h1><p className="clients-subtitle">Filing deadlines from today through the next 14 calendar days.</p></div>
        </div>

        <section className="client-list-card deadlines-card" aria-labelledby="deadlines-heading">
          <div className="client-list-heading"><div><h2 id="deadlines-heading">Filing deadlines</h2><p>Sorted by filing date, earliest first.</p></div><div className="client-count"><strong>{loading ? '—' : deadlines.length}</strong><span>{deadlines.length === 1 ? 'upcoming deadline' : 'upcoming deadlines'}</span></div></div>
          {error && <div className="client-notice error" role="alert"><span>!</span>{error}</div>}
          {loading ? <div className="client-list-state"><span className="spinner" /> Loading upcoming deadlines…</div> : error ? null : deadlines.length === 0 ? (
            <div className="client-list-state empty-clients"><div className="empty-client-icon" aria-hidden="true">◷</div><h3>No upcoming deadlines within the next 14 days.</h3><p>Filing deadlines for the coming days will appear here.</p></div>
          ) : (
            <div className="client-table-scroll"><table className="client-table upcoming-deadlines-table"><thead><tr><th>CLIENT</th><th>TAX ENGAGEMENT</th><th>TAX YEAR</th><th>RETURN TYPE</th><th>FILING DEADLINE</th><th>DAYS REMAINING</th></tr></thead><tbody>
              {deadlines.map((item) => <tr key={item.engagement_id}><td><strong>{item.client_name}</strong></td><td><strong>Engagement #{item.engagement_id}</strong></td><td>{item.tax_year}</td><td>{item.return_type}</td><td><strong>{displayDate(item.filing_deadline)}</strong></td><td><span className={`deadline-days${item.days_remaining <= 3 ? ' soon' : ''}`}>{item.days_remaining === 0 ? '0 days · Today' : `${item.days_remaining} days`}</span></td></tr>)}
            </tbody></table></div>
          )}
        </section>
      </section>
    </main>
  )
}
