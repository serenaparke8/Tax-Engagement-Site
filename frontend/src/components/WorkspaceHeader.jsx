import Brand from './Brand.jsx'

export default function WorkspaceHeader({ user, activeModule, onNavigate, onLogout }) {
  return (
    <header className="workspace-header">
      <Brand />
      <nav className="module-nav" aria-label="System modules">
        <button className={activeModule === 'clients' ? 'active' : ''} aria-current={activeModule === 'clients' ? 'page' : undefined} onClick={() => onNavigate('clients')}><span aria-hidden="true">▣</span>Clients</button>
        <button className={activeModule === 'engagements' ? 'active' : ''} aria-current={activeModule === 'engagements' ? 'page' : undefined} onClick={() => onNavigate('engagements')}><span aria-hidden="true">▤</span>Tax Engagements</button>
      </nav>
      <div className="account-area"><div className="avatar">{user.display_name.slice(0, 1).toUpperCase()}</div><div className="account-name"><strong>{user.display_name}</strong><span>Tax Preparer</span></div><button className="logout-button" onClick={onLogout}>Sign out</button></div>
    </header>
  )
}
