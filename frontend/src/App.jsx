import { Routes, Route, NavLink } from 'react-router-dom'
import IngestPage from './components/IngestPage'
import QueryPage from './components/QueryPage'
import { useEffect, useState } from 'react'
import { checkHealth } from './api/codesync'

export default function App() {
  const [serverStatus, setServerStatus] = useState('connecting...')
  const [dark, setDark] = useState(() => localStorage.getItem('theme') === 'dark')

  const [ingestState, setIngestState] = useState({
    repoUrl: '',
    repoId: '',
    status: null,
    logs: [{ time: '--:--:--', msg: 'Ready. Paste a GitHub URL and click Index.', type: 'info' }],
    progress: 0,
    loading: false,
  })

  const [lastIndexedRepo, setLastIndexedRepo] = useState('fastapi-main')

  useEffect(() => {
    document.body.classList.toggle('dark', dark)
    localStorage.setItem('theme', dark ? 'dark' : 'light')
  }, [dark])

  useEffect(() => {
    checkHealth()
      .then(data => setServerStatus(`${data.env} — online`))
      .catch(() => setServerStatus('offline'))
  }, [])

  const online = !serverStatus.includes('offline') && serverStatus !== 'connecting...'

  return (
    <div style={{ minHeight: '100vh' }}>

      <header style={{
        borderBottom: '1px solid var(--border)',
        padding: '0 24px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        height: '52px',
        background: 'var(--bg)',
        position: 'sticky',
        top: 0,
        zIndex: 100,
        boxShadow: '0 1px 8px rgba(0,0,0,0.06)',
      }}>
        <span style={{
          fontFamily: 'var(--sans)',
          fontWeight: 700,
          fontSize: '15px',
          color: 'var(--text)',
          letterSpacing: '-0.3px',
        }}>
          Code<span style={{ color: 'var(--accent)' }}>Sync</span>
        </span>

        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', color: 'var(--text-2)' }}>
            <span style={{
              width: '6px', height: '6px', borderRadius: '50%',
              background: online ? 'var(--green)' : 'var(--text-3)',
              display: 'inline-block', flexShrink: 0,
            }} />
            {serverStatus}
          </div>

          <button
            onClick={() => setDark(d => !d)}
            title="Toggle theme"
            style={{
              width: '30px', height: '30px',
              borderRadius: '6px',
              border: '1px solid var(--border)',
              background: 'transparent',
              cursor: 'pointer',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              color: 'var(--text-2)',
              fontSize: '15px',
              lineHeight: 1,
              transition: 'background 0.12s, color 0.12s',
            }}
          >
            {dark ? '☀' : '◑'}
          </button>
        </div>
      </header>

      <nav style={{
        borderBottom: '1px solid var(--border)',
        padding: '0 24px',
        display: 'flex',
        background: 'var(--bg)',
      }}>
        {[
          { to: '/',      label: 'Index' },
          { to: '/query', label: 'Query' },
        ].map(({ to, label }) => (
          <NavLink key={to} to={to} end style={({ isActive }) => ({
            padding: '11px 14px',
            fontSize: '13px',
            fontWeight: 500,
            color: isActive ? 'var(--text)' : 'var(--text-2)',
            borderBottom: isActive ? '2px solid var(--accent)' : '2px solid transparent',
            textDecoration: 'none',
            transition: 'color 0.12s',
            marginBottom: '-1px',
          })}>
            {label}
          </NavLink>
        ))}
      </nav>

      <main style={{ maxWidth: '860px', margin: '0 auto', padding: '32px 24px' }}>
        <Routes>
          <Route path="/" element={
            <IngestPage
              state={ingestState}
              setState={setIngestState}
              onComplete={(repoId) => setLastIndexedRepo(repoId)}
            />}
          />
          <Route path="/query" element={
            <QueryPage defaultRepoId={lastIndexedRepo} />
          } />
        </Routes>
      </main>
    </div>
  )
}
