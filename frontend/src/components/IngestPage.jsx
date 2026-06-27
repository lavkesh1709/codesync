import { useState, useRef, useEffect } from 'react'
import { ingestRepo, getIngestStatus } from '../api/codesync'
import './styles.css'

const STEPS = [
  { key: 'cloning',   label: 'Clone',  progress: 20 },
  { key: 'walking',   label: 'Scan',   progress: 38 },
  { key: 'chunking',  label: 'Chunk',  progress: 54 },
  { key: 'embedding', label: 'Embed',  progress: 75 },
  { key: 'storing',   label: 'Store',  progress: 90 },
]

const PRESETS = [
  { label: 'FastAPI',  url: 'https://github.com/tiangolo/fastapi', id: 'fastapi-main' },
  { label: 'Flask',    url: 'https://github.com/pallets/flask',     id: 'flask-main' },
  { label: 'Requests', url: 'https://github.com/psf/requests',      id: 'requests-main' },
]

export default function IngestPage({ state, setState, onComplete }) {
  const { repoUrl, repoId, loading, status, logs, progress } = state
  const [expandError, setExpandError] = useState(false)
  const [fullError, setFullError] = useState(null)
  const [completedSteps, setCompletedSteps] = useState([])
  const [activeStep, setActiveStep] = useState(null)

  const pollRef  = useRef(null)
  const logRef   = useRef(null)
  const lastStep = useRef(null)

  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight
  }, [logs])

  const set = (patch) => setState(prev => ({ ...prev, ...patch }))
  const addLog = (msg, type = 'info') => {
    const time = new Date().toTimeString().slice(0, 8)
    setState(prev => ({ ...prev, logs: [...prev.logs, { time, msg, type }] }))
  }

  async function startIngest() {
    if (!repoUrl || !repoId) { addLog('Enter both a URL and a Repository ID.', 'warn'); return }
    if (loading) return

    setExpandError(false)
    setFullError(null)
    setCompletedSteps([])
    setActiveStep(null)
    lastStep.current = null

    set({
      loading: true, status: 'processing', progress: 5,
      logs: [{ time: new Date().toTimeString().slice(0, 8), msg: `Starting ingestion for ${repoId}...`, type: 'info' }],
    })

    try {
      const data = await ingestRepo(repoUrl, repoId)
      addLog('Job accepted — polling for progress...', 'info')
      set({ progress: 10 })
      pollStatus(data.job_id, repoId)
    } catch (err) {
      addLog(`Request failed: ${err.message}`, 'error')
      set({ loading: false, status: 'error', progress: 0 })
    }
  }

  function pollStatus(jobId, rid) {
    pollRef.current = setInterval(async () => {
      try {
        const data = await getIngestStatus(jobId, rid)
        const stepDef = STEPS.find(s => s.key === data.status)

        if (stepDef && data.status !== lastStep.current) {
          lastStep.current = data.status
          setActiveStep(data.status)
          setCompletedSteps(() => {
            const idx = STEPS.findIndex(s => s.key === data.status)
            return STEPS.slice(0, idx).map(s => s.key)
          })
          set({ progress: stepDef.progress })
          addLog(`${stepDef.label}...`, 'info')
        }

        if (data.status === 'completed') {
          clearInterval(pollRef.current)
          setActiveStep(null)
          setCompletedSteps(STEPS.map(s => s.key))
          set({ progress: 100, status: 'completed', loading: false })
          addLog(`Done — ${data.files_processed} files · ${data.chunks_created} chunks indexed`, 'success')
          onComplete(rid)
        } else if (data.status === 'failed') {
          clearInterval(pollRef.current)
          setActiveStep(null)
          const err = data.error || 'Unknown error'
          setFullError(err)
          addLog(`Failed: ${err.length > 100 ? err.slice(0, 100) + '…' : err}`, 'error')
          set({ status: 'error', loading: false, progress: 0 })
        }
      } catch (err) {
        addLog(`Poll error: ${err.message}`, 'warn')
      }
    }, 2000)
  }

  return (
    <div>
      {/* Heading */}
      <div style={{ marginBottom: '24px' }}>
        <h1 style={{ fontSize: '18px', fontWeight: 600, color: 'var(--text)', marginBottom: '4px' }}>
          Index Repository
        </h1>
        <p style={{ fontSize: '13px', color: 'var(--text-2)', lineHeight: 1.6 }}>
          Clone, chunk, and embed a GitHub codebase for semantic search.
        </p>
      </div>

      {/* Form */}
      <div className="card" style={{ marginBottom: '12px' }}>
        <div style={{ padding: '20px' }}>

          {/* Presets */}
          <div style={{ marginBottom: '20px' }}>
            <div className="section-label">Quick start</div>
            <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
              {PRESETS.map(p => (
                <button key={p.id} className="chip"
                  onClick={() => set({ repoUrl: p.url, repoId: p.id })}>
                  {p.label}
                </button>
              ))}
            </div>
          </div>

          <div className="divider" style={{ marginBottom: '20px' }} />

          <div className="form-group">
            <label className="form-label">GitHub Repository URL</label>
            <input className="form-input" type="text" value={repoUrl}
              onChange={e => set({ repoUrl: e.target.value })}
              placeholder="https://github.com/owner/repo" />
          </div>

          <div className="form-group" style={{ marginBottom: '20px' }}>
            <label className="form-label">Repository ID</label>
            <input className="form-input" type="text" value={repoId}
              onChange={e => set({ repoId: e.target.value })}
              placeholder="my-repo"
              onKeyDown={e => e.key === 'Enter' && startIngest()} />
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <button className="btn btn-primary" onClick={startIngest} disabled={loading}>
              {loading ? 'Indexing...' : 'Index Repository'}
            </button>
            {status === 'processing' && <span className="badge badge-processing">Processing</span>}
            {status === 'completed'  && <span className="badge badge-completed">Completed</span>}
            {status === 'error'      && <span className="badge badge-error">Failed</span>}
          </div>
        </div>

        {/* Inline progress bar at card bottom */}
        {(loading || status === 'completed') && (
          <div className="progress-bar" style={{ borderRadius: 0 }}>
            <div className={`progress-bar-fill ${progress < 15 ? 'indeterminate' : ''}`}
              style={{ width: `${progress}%` }} />
          </div>
        )}
      </div>

      {/* Pipeline stepper */}
      {(loading || status === 'completed' || status === 'error') && (
        <div className="card" style={{ marginBottom: '12px' }}>
          <div style={{
            padding: '10px 20px',
            borderBottom: '1px solid var(--border)',
            fontSize: '12px',
            fontWeight: 500,
            color: 'var(--text-2)',
          }}>
            Pipeline
          </div>
          <div className="stepper">
            {STEPS.map((step, i) => {
              const done   = completedSteps.includes(step.key)
              const active = activeStep === step.key
              return (
                <div key={step.key}
                  className={`step ${done ? 'done' : ''} ${active ? 'active' : ''}`}>
                  <div className="step-circle">
                    {done ? '✓' : i + 1}
                  </div>
                  <span className="step-label">{step.label}</span>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Log terminal */}
      <div className="terminal">
        <div className="terminal-bar">
          <span className="terminal-title">ingestion.log</span>
          {loading && <span className="terminal-live" />}
        </div>
        <div className="terminal-body" ref={logRef}>
          {logs.map((entry, i) => (
            <div key={i} className="log-row">
              <span className="log-ts">{entry.time}</span>
              <span className={`log-lvl log-lvl-${entry.type}`}>[{entry.type.toUpperCase().padEnd(5)}]</span>
              <span className="log-msg">{entry.msg}</span>
            </div>
          ))}
          {loading && (
            <div className="log-row">
              <span className="log-ts" />
              <span className="log-lvl" />
              <span className="log-msg log-cursor">▋</span>
            </div>
          )}
        </div>
      </div>

      {/* Error detail */}
      {fullError && (
        <div className="error-box">
          <div className="error-box-header" onClick={() => setExpandError(e => !e)}>
            <span>Error details</span>
            <span style={{ fontSize: '11px' }}>{expandError ? 'hide ▲' : 'show ▼'}</span>
          </div>
          {expandError && <pre className="error-box-body">{fullError}</pre>}
        </div>
      )}
    </div>
  )
}
