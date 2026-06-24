import { useState, useRef, useEffect } from 'react'
import { ingestRepo, getIngestStatus } from '../api/codesync'
import './styles.css'

const STEPS = [
  { key: 'cloning',   label: 'Clone repository',      progress: 20 },
  { key: 'walking',   label: 'Scan files',             progress: 38 },
  { key: 'chunking',  label: 'Split into chunks',      progress: 54 },
  { key: 'embedding', label: 'Generate embeddings',    progress: 75 },
  { key: 'storing',   label: 'Store in database',      progress: 90 },
]

const PRESETS = [
  { label: 'FastAPI',   url: 'https://github.com/tiangolo/fastapi',  id: 'fastapi-main' },
  { label: 'Flask',     url: 'https://github.com/pallets/flask',      id: 'flask-main' },
  { label: 'Requests',  url: 'https://github.com/psf/requests',       id: 'requests-main' },
]

export default function IngestPage({ state, setState, onComplete }) {
  const { repoUrl, repoId, loading, status, logs, progress } = state
  const [expandError, setExpandError] = useState(false)
  const [fullError, setFullError] = useState(null)
  const [completedSteps, setCompletedSteps] = useState([])
  const [activeStep, setActiveStep] = useState(null)

  const pollRef   = useRef(null)
  const logRef    = useRef(null)
  const lastStep  = useRef(null)

  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight
  }, [logs])

  const set = (patch) => setState(prev => ({ ...prev, ...patch }))
  const addLog = (msg, type = 'info') => {
    const time = new Date().toTimeString().slice(0, 8)
    setState(prev => ({ ...prev, logs: [...prev.logs, { time, msg, type }] }))
  }

  async function startIngest() {
    if (!repoUrl || !repoId) { addLog('Enter both a URL and a Repository ID', 'warn'); return }
    if (loading) return

    setExpandError(false)
    setFullError(null)
    setCompletedSteps([])
    setActiveStep(null)
    lastStep.current = null

    set({ loading: true, status: 'processing', progress: 5,
          logs: [{ time: new Date().toTimeString().slice(0, 8), msg: `Starting ingestion for ${repoId}...`, type: 'info' }] })

    try {
      const data = await ingestRepo(repoUrl, repoId)
      addLog(`Job accepted — polling for status...`, 'info')
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

        // Update step progress
        if (stepDef && data.status !== lastStep.current) {
          lastStep.current = data.status
          setActiveStep(data.status)
          setCompletedSteps(prev => {
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
          addLog(`Indexed ${data.files_processed} files · ${data.chunks_created} chunks stored`, 'success')
          onComplete(rid)
        } else if (data.status === 'failed') {
          clearInterval(pollRef.current)
          setActiveStep(null)
          const err = data.error || 'Unknown error — check server logs'
          setFullError(err)
          const preview = err.length > 100 ? err.slice(0, 100) + '…' : err
          addLog(`Failed: ${preview}`, 'error')
          set({ status: 'error', loading: false, progress: 0 })
        }
      } catch (err) {
        addLog(`Poll error: ${err.message}`, 'warn')
      }
    }, 2000)
  }

  const stepIndex = STEPS.findIndex(s => s.key === activeStep)

  return (
    <div>
      <div style={{ marginBottom: '36px' }}>
        <div className="page-title">Index a Repository</div>
        <div className="page-subtitle">
          Clone, chunk, embed and store any GitHub codebase — then query it in plain English with exact file citations.
        </div>
      </div>

      {/* Config panel */}
      <div className="panel" style={{ marginBottom: '24px' }}>
        <div className="panel-header">
          <div className="panel-dot" style={{ background: '#ff5f57' }} />
          <div className="panel-dot" style={{ background: '#febc2e' }} />
          <div className="panel-dot" style={{ background: '#28c840' }} />
          <span className="panel-label">ingestion.config</span>
        </div>

        <div className="panel-body">
          <div style={{ marginBottom: '20px' }}>
            <div className="section-label">Quick presets</div>
            <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
              {PRESETS.map(p => (
                <button key={p.id} className="quick-btn"
                  onClick={() => set({ repoUrl: p.url, repoId: p.id })}>
                  {p.label}
                </button>
              ))}
            </div>
          </div>

          <div className="field">
            <label>GitHub Repository URL</label>
            <input type="text" value={repoUrl}
              onChange={e => set({ repoUrl: e.target.value })}
              placeholder="https://github.com/owner/repo" />
          </div>

          <div className="field">
            <label>Repository ID</label>
            <input type="text" value={repoId}
              onChange={e => set({ repoId: e.target.value })}
              placeholder="my-repo"
              onKeyDown={e => e.key === 'Enter' && startIngest()} />
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '14px', flexWrap: 'wrap' }}>
            <button className="btn-primary" onClick={startIngest} disabled={loading}>
              {loading ? '⟳  Indexing…' : '▶  Index Repository'}
            </button>
            {status && (
              <span className={`status-pill ${status === 'processing' ? 'processing' : status === 'completed' ? 'completed' : 'error'}`}>
                <span style={{ width: '5px', height: '5px', borderRadius: '50%', background: 'currentColor', display: 'inline-block' }} />
                {status}
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Step tracker */}
      {(loading || status === 'completed' || status === 'error') && (
        <div className="panel" style={{ marginBottom: '24px' }}>
          <div className="panel-header">
            <span className="panel-label" style={{ marginLeft: 0 }}>Pipeline</span>
          </div>
          <div style={{ padding: '20px 24px', display: 'flex', gap: '0', alignItems: 'center' }}>
            {STEPS.map((step, i) => {
              const done  = completedSteps.includes(step.key)
              const active = activeStep === step.key
              const idle  = !done && !active
              return (
                <div key={step.key} style={{ display: 'flex', alignItems: 'center', flex: 1, minWidth: 0 }}>
                  <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '6px', flex: 1 }}>
                    <div style={{
                      width: '28px', height: '28px', borderRadius: '50%',
                      background: done ? 'var(--green)' : active ? 'var(--accent)' : 'var(--bg3)',
                      border: `2px solid ${done ? 'var(--green)' : active ? 'var(--accent)' : 'var(--border)'}`,
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      fontSize: '12px', color: done || active ? '#fff' : 'var(--text-dimmer)',
                      transition: 'all 0.3s',
                      boxShadow: active ? '0 0 0 3px rgba(180,83,9,0.2)' : 'none',
                      animation: active ? 'pulse 1.5s ease infinite' : 'none',
                    }}>
                      {done ? '✓' : i + 1}
                    </div>
                    <span style={{
                      fontSize: '10px',
                      fontFamily: 'JetBrains Mono, monospace',
                      color: done ? 'var(--green)' : active ? 'var(--accent)' : 'var(--text-dimmer)',
                      textAlign: 'center',
                      whiteSpace: 'nowrap',
                      transition: 'color 0.3s',
                    }}>
                      {step.label}
                    </span>
                  </div>
                  {i < STEPS.length - 1 && (
                    <div style={{
                      height: '2px', flex: 1,
                      background: done ? 'var(--green)' : 'var(--border)',
                      margin: '0 4px', marginBottom: '22px',
                      transition: 'background 0.4s',
                    }} />
                  )}
                </div>
              )
            })}
          </div>

          {/* Progress bar */}
          <div className="progress-track" style={{ margin: '0 24px 20px', marginTop: 0 }}>
            <div className={`progress-fill ${progress < 15 ? 'indeterminate' : ''}`}
              style={{ width: `${progress}%` }} />
          </div>
        </div>
      )}

      {/* Log terminal */}
      <div className="log-terminal">
        <div className="log-terminal-header">
          <div className="log-terminal-dot" style={{ background: '#ff5f57' }} />
          <div className="log-terminal-dot" style={{ background: '#febc2e' }} />
          <div className="log-terminal-dot" style={{ background: '#28c840' }} />
          <span className="log-terminal-title">ingestion.log</span>
          {loading && <span style={{ marginLeft: 'auto', width: '6px', height: '6px', borderRadius: '50%', background: '#28c840', animation: 'blink 1s step-end infinite' }} />}
        </div>
        <div className="log-terminal-body" ref={logRef}>
          {logs.map((entry, i) => (
            <div key={i} className="log-entry">
              <span className="log-time">{entry.time}</span>
              <span className={`log-level-${entry.type}`}>[{entry.type.toUpperCase().padEnd(5)}]</span>
              <span className="log-msg">{entry.msg}</span>
            </div>
          ))}
          {loading && <div className="log-entry"><span className="log-time">{'      '}</span><span className="log-level-info">{'      '}</span><span className="log-msg log-cursor">▋</span></div>}
        </div>
      </div>

      {/* Full error detail */}
      {fullError && (
        <div className="error-panel" style={{ marginTop: '16px' }}>
          <div className="error-panel-header" onClick={() => setExpandError(e => !e)}>
            <span>⚠ Error details</span>
            <span>{expandError ? '▲ hide' : '▼ show'}</span>
          </div>
          {expandError && (
            <pre className="error-panel-body">{fullError}</pre>
          )}
        </div>
      )}

      <style>{`
        @keyframes pulse { 0%,100%{box-shadow:0 0 0 3px rgba(180,83,9,0.2)} 50%{box-shadow:0 0 0 6px rgba(180,83,9,0.08)} }
        @keyframes blink { 0%,100%{opacity:1} 50%{opacity:0} }
        .log-cursor { color:#00ff88; animation: blink 0.7s step-end infinite; }
      `}</style>
    </div>
  )
}
