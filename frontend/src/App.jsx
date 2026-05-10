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
    logs: [{ time: '--:--:--', msg: 'CodeSync ready. Paste a GitHub URL and click Index.', type: 'info' }],
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
      .then(data => setServerStatus(`api:${data.env} — online`))
      .catch(() => setServerStatus('server offline'))
  }, [])

  const accent = dark ? '#f59e0b' : '#b45309'
  const borderColor = dark ? 'rgba(180,83,9,0.2)' : '#e9e0c8'
  const headerBg = dark ? 'rgba(17,16,16,0.97)' : 'rgba(255,255,255,0.95)'
  const textDim = dark ? '#a8a29e' : '#78716c'
  const titleColor = dark ? '#f5f0eb' : '#1c1917'

  return (
    <div style={{ minHeight: '100vh' }}>
      <header style={{
        borderBottom: `1px solid ${borderColor}`,
        padding: '0 32px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        height: '60px',
        background: headerBg,
        backdropFilter: 'blur(10px)',
        position: 'sticky',
        top: 0,
        zIndex: 100,
        boxShadow: '0 1px 3px rgba(0,0,0,0.06)',
      }}>
        <div style={{ fontFamily: 'var(--display)', fontWeight: 800, fontSize: '20px', color: titleColor }}>
          Code<span style={{ color: accent }}>Sync</span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '20px' }}>
          {/* Server status */}
          <div style={{ fontSize: '11px', color: textDim, display: 'flex', alignItems: 'center', gap: '8px', fontFamily: 'var(--mono)' }}>
            <span style={{
              width: '7px', height: '7px', borderRadius: '50%',
              background: serverStatus.includes('offline') ? '#dc2626' : '#059669',
              display: 'inline-block',
            }} />
            {serverStatus}
          </div>

          {/* Theme toggle */}
          <button
            onClick={() => setDark(d => !d)}
            title={dark ? 'Switch to light mode' : 'Switch to dark mode'}
            style={{
              width: '36px',
              height: '20px',
              borderRadius: '10px',
              border: `1.5px solid ${borderColor}`,
              background: dark ? '#b45309' : '#e9e0c8',
              cursor: 'pointer',
              position: 'relative',
              transition: 'background 0.25s, border-color 0.25s',
              flexShrink: 0,
            }}
          >
            <span style={{
              position: 'absolute',
              top: '2px',
              left: dark ? '17px' : '2px',
              width: '12px',
              height: '12px',
              borderRadius: '50%',
              background: '#fff',
              transition: 'left 0.25s',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: '7px',
            }}>
              {dark ? '🌙' : '☀'}
            </span>
          </button>
        </div>
      </header>

      <nav style={{ borderBottom: `1px solid ${borderColor}`, padding: '0 32px', display: 'flex', background: headerBg, backdropFilter: 'blur(8px)' }}>
        {[
          { to: '/', label: '01 / Index Repository' },
          { to: '/query', label: '02 / Query Codebase' },
        ].map(({ to, label }) => (
          <NavLink key={to} to={to} end style={({ isActive }) => ({
            padding: '14px 20px',
            fontSize: '12px',
            fontFamily: 'var(--mono)',
            fontWeight: 500,
            color: isActive ? accent : textDim,
            borderBottom: isActive ? `2px solid ${accent}` : '2px solid transparent',
            textDecoration: 'none',
            textTransform: 'uppercase',
            letterSpacing: '0.5px',
            transition: 'all 0.15s',
          })}>
            {label}
          </NavLink>
        ))}
      </nav>

      <main style={{ maxWidth: '1100px', margin: '0 auto', padding: '40px 32px' }}>
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
