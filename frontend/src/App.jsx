import { useEffect, useState } from 'react'
import Brand from './components/Brand.jsx'
import ClientsPage from './features/clients/ClientsPage.jsx'
import DashboardPage from './features/dashboard/DashboardPage.jsx'
import EngagementsPage from './features/engagements/EngagementsPage.jsx'
import RequiredItemsPage from './features/required-items/RequiredItemsPage.jsx'
import UpcomingDeadlinesPage from './features/deadlines/UpcomingDeadlinesPage.jsx'
import EngagementReportsPage from './features/reports/EngagementReportsPage.jsx'
import { api } from './services/api.js'

function Login({ onLogin }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function submit(event) {
    event.preventDefault()
    setError('')
    setBusy(true)
    try {
      await api('/api/auth/login', {
        method: 'POST',
        body: JSON.stringify({ username, password }),
      })
      await onLogin()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <main className="login-layout">
      <section className="intro-panel">
        <Brand />
        <div className="intro-copy">
          <p className="eyebrow light">A CLEAR VIEW OF EVERY ENGAGEMENT</p>
          <h1>Good work starts with knowing what comes next.</h1>
          <p className="intro-description">A shared workspace for keeping client engagements, deadlines, and required information organized.</p>
        </div>
        <div className="intro-footer"><span className="status-dot" /> Local demonstration environment</div>
      </section>

      <section className="form-panel" aria-labelledby="login-title">
        <div className="form-wrap">
          <div className="mobile-brand"><Brand /></div>
          <div className="form-heading">
            <p className="eyebrow">WELCOME BACK</p>
            <h2 id="login-title">Sign in to continue</h2>
            <p>Your engagement workspace is ready when you are.</p>
          </div>
          <form onSubmit={submit}>
            <label htmlFor="username">Username</label>
            <input id="username" name="username" autoComplete="username" value={username} onChange={(e) => setUsername(e.target.value)} required autoFocus />
            <label htmlFor="password">Password</label>
            <input id="password" name="password" type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required />
            {error && <div className="form-error" role="alert">{error}</div>}
            <button type="submit" disabled={busy}>{busy ? 'Signing in…' : 'Sign in'}<span aria-hidden="true">→</span></button>
          </form>
          <p className="local-note"><span aria-hidden="true">⌂</span> This application runs locally on your computer.</p>
        </div>
        <div className="form-bottom">Tax Engagement Management System <span>•</span> Client and engagement management</div>
      </section>
    </main>
  )
}

export default function App() {
  const [user, setUser] = useState(null)
  const [activeModule, setActiveModule] = useState('dashboard')
  const [loading, setLoading] = useState(true)

  async function loadSession() {
    await api('/api/auth/csrf')
    const result = await api('/api/auth/me')
    setUser(result.user)
  }

  useEffect(() => {
    loadSession().catch(() => setUser(null)).finally(() => setLoading(false))
  }, [])

  async function logout() {
    await api('/api/auth/logout', { method: 'POST' })
    setUser(null)
  }

  if (loading) return <main className="loading-screen"><span className="spinner" />Connecting to your workspace…</main>
  if (!user) return <Login onLogin={loadSession} />
  const pageProps = { user, onLogout: logout, onNavigate: setActiveModule }
  if (activeModule === 'dashboard') return <DashboardPage {...pageProps} />
  if (activeModule === 'engagements') return <EngagementsPage {...pageProps} />
  if (activeModule === 'requiredItems') return <RequiredItemsPage {...pageProps} />
  if (activeModule === 'deadlines') return <UpcomingDeadlinesPage {...pageProps} />
  if (activeModule === 'reports') return <EngagementReportsPage {...pageProps} />
  return <ClientsPage {...pageProps} />
}
