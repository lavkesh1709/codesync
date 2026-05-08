import { Routes, Route, NavLink } from 'react-router-dom'
import IngestPage from './components/IngestPage'
import QueryPage from './components/QueryPage'
import { useEffect, useState } from 'react'
import { checkHealth } from './api/codesync'

export default function App() {
  const [serverStatus, setServerStatus] = useState('connecting...')

  useEffect(() => {
    checkHealth()
      .then(data => setServerStatus(`api:${data.env} — online`))
      .catch(() => setServerStatus('server offline'))
  }, [])

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg)' }}>

      {/* Header */}
      <header style={{
        borderBottom: '1px solid var(--border)',
        padding: '0 32px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        height: '56px',
        background: 'rgba(8,11,15,0.9)',
      }}>
        <div style={{ fontFamily: 'var(--display)', fontWeight: 800, fontSize: '18px', color: '#fff' }}>
          Code<span style={{ color: 'var(--green)' }}>Sync</span>
        </div>
        <div style={{ fontSize: '11px', color: 'var(--text-dim)', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{
            width: '6px', height: '6px', borderRadius: '50%',
            background: serverStatus.includes('offline') ? 'var(--red)' : 'var(--green)',
            display: 'inline-block'
          }} />
          {serverStatus}
        </div>
      </header>

      {/* Nav */}
      <nav style={{ borderBottom: '1px solid var(--border)', padding: '0 32px', display: 'flex' }}>
        {[
          { to: '/', label: '01 / Index Repository' },
          { to: '/query', label: '02 / Query Codebase' },
        ].map(({ to, label }) => (
          <NavLink key={to} to={to} end style={({ isActive }) => ({
            padding: '14px 20px',
            fontSize: '12px',
            fontFamily: 'var(--mono)',
            fontWeight: 500,
            color: isActive ? 'var(--green)' : 'var(--text-dim)',
            borderBottom: isActive ? '2px solid var(--green)' : '2px solid transparent',
            textDecoration: 'none',
            textTransform: 'uppercase',
            letterSpacing: '0.5px',
            transition: 'all 0.2s',
          })}>
            {label}
          </NavLink>
        ))}
      </nav>

      {/* Pages */}
      <main style={{ maxWidth: '1100px', margin: '0 auto', padding: '40px 32px' }}>
        <Routes>
          <Route path="/" element={<IngestPage />} />
          <Route path="/query" element={<QueryPage />} />
        </Routes>
      </main>

    </div>
  )
}