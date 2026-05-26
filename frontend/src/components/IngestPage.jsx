import { useState, useRef, useEffect } from 'react'
import { ingestRepo, getIngestStatus } from '../api/codesync'
import './styles.css'

export default function IngestPage({ state, setState, onComplete }) {
  const { repoUrl, repoId, loading, status, logs, progress } = state

  const setRepoUrl = val => setState(prev => ({ ...prev, repoUrl: val }))
  const setRepoId = val => setState(prev => ({ ...prev, repoId: val }))
  const setLoading = val => setState(prev => ({ ...prev, loading: val }))
  const setStatus = val => setState(prev => ({ ...prev, status: val }))
  const setProgress = val => setState(prev => ({ ...prev, progress: val }))

  const pollRef = useRef(null)
  const logRef = useRef(null)
  const lastStepRef = useRef(null)

  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight
  }, [logs])

  const addLog = (msg, type = 'info') => {
    const time = new Date().toTimeString().slice(0, 8)
    setState(prev => ({ ...prev, logs: [...prev.logs, { time, msg, type }] }))
  }

  const PRESETS = [
    { label: 'FastAPI', url: 'https://github.com/tiangolo/fastapi', id: 'fastapi-main' },
    { label: 'Flask', url: 'https://github.com/pallets/flask', id: 'flask-main' },
    { label: 'Requests', url: 'https://github.com/psf/requests', id: 'requests-main' },
  ]

  async function startIngest() {
    if (!repoUrl || !repoId) {
      addLog('Please enter both a repository URL and an ID', 'error')
      return
    }
    setLoading(true)
    setStatus('processing')
    setProgress(5)
    lastStepRef.current = null
    addLog(`Queuing ingest for ${repoId}...`)

    try {
      const data = await ingestRepo(repoUrl, repoId)
      addLog(`Job queued — ${data.job_id.slice(0, 8)}...`)
      setProgress(10)
      pollStatus(data.job_id, repoId)
    } catch (err) {
      addLog(`Error: ${err.message}`, 'error')
      setLoading(false)
      setStatus('error')
      setProgress(0)
    }
  }

  const STEP_PROGRESS = { cloning: 20, walking: 40, chunking: 55, embedding: 75, storing: 90, parsing_imports: 95 }

  function pollStatus(jobId, rid) {
    pollRef.current = setInterval(async () => {
      try {
        const data = await getIngestStatus(jobId, rid)
        if (data.step && STEP_PROGRESS[data.step]) {
          setProgress(STEP_PROGRESS[data.step])
          // Only print the log if the step actually transitioned
          if (data.step !== lastStepRef.current) {
            addLog(`Step: ${data.step.replace('_', ' ')}...`)
            lastStepRef.current = data.step
          }
        }
        if (data.status === 'completed') {
          clearInterval(pollRef.current)
          setProgress(100)
          addLog(`✓ Complete — ${data.files_processed} files, ${data.chunks_created} chunks indexed`)
          setStatus('completed')
          setLoading(false)
          onComplete(repoId)
        } else if (data.status === 'failed') {
          clearInterval(pollRef.current)
          addLog(data.error ? `Failed: ${data.error}` : 'Indexing failed', 'error')
          setStatus('error')
          setLoading(false)
          setProgress(0)
        }
      } catch (err) {
        addLog(`Poll error: ${err.message}`, 'warn')
      }
    }, 5000)
  }

  return (
    <div>
      {/* Hero */}
      <div style={{ marginBottom: '40px' }}>
        <div className="page-title">Index a Repository</div>
        <div className="page-subtitle">Clone, chunk, embed and store any GitHub codebase — then ask questions in plain English and get answers with exact file citations.</div>
      </div>

      <div className="panel">
        <div className="panel-header">
          <div className="panel-dot" style={{ background: '#ff5f57' }} />
          <div className="panel-dot" style={{ background: '#febc2e' }} />
          <div className="panel-dot" style={{ background: '#28c840' }} />
          <span className="panel-label">ingestion.config</span>
        </div>

        <div className="panel-body">

          {/* Quick presets */}
          <div style={{ marginBottom: '20px' }}>
            <div className="section-label">Quick presets</div>
            <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
              {PRESETS.map(p => (
                <button key={p.id} className="quick-btn"
                  onClick={() => { setRepoUrl(p.url); setRepoId(p.id) }}>
                  {p.label}
                </button>
              ))}
            </div>
          </div>

          <div className="field">
            <label>GitHub Repository URL</label>
            <input type="text" value={repoUrl} onChange={e => setRepoUrl(e.target.value)}
              placeholder="https://github.com/tiangolo/fastapi" />
          </div>

          <div className="field">
            <label>Repository ID</label>
            <input type="text" value={repoId} onChange={e => setRepoId(e.target.value)}
              placeholder="fastapi-main"
              onKeyDown={e => e.key === 'Enter' && startIngest()} />
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '16px', flexWrap: 'wrap' }}>
            <button className="btn-primary" onClick={startIngest} disabled={loading}>
              {loading ? '⟳ Processing...' : '▶ Index Repository'}
            </button>
            {status && (
              <span className={`status-pill ${status}`}>
                <span style={{ width: '5px', height: '5px', borderRadius: '50%', background: 'currentColor', display: 'inline-block' }} />
                {status}
              </span>
            )}
          </div>

          {/* Progress bar */}
          {loading && (
            <div className="progress-track" style={{ marginTop: '16px' }}>
              <div className={`progress-fill ${progress < 15 ? 'indeterminate' : ''}`}
                style={{ width: `${progress}%` }} />
            </div>
          )}

          {/* Log terminal */}
          <div className="log-terminal">
            <div className="log-terminal-header">
              <div className="log-terminal-dot" style={{ background: '#ff5f57' }} />
              <div className="log-terminal-dot" style={{ background: '#febc2e' }} />
              <div className="log-terminal-dot" style={{ background: '#28c840' }} />
              <span className="log-terminal-title">ingestion.log</span>
            </div>
            <div className="log-terminal-body" ref={logRef}>
              {logs.map((log, i) => (
                <div key={i} className="log-entry">
                  <span className="log-time">{log.time}</span>
                  <span className={`log-level-${log.type}`}>[{log.type.toUpperCase()}]</span>
                  <span className="log-msg">{log.msg}</span>
                </div>
              ))}
            </div>
          </div>

        </div>
      </div>
    </div>
  )
}