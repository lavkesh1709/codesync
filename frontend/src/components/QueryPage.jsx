import { useState, useRef } from 'react'
import { queryStream } from '../api/codesync'
import './styles.css'

const SUGGESTED = [
  'How does dependency injection work?',
  'How does the routing system work?',
  'How does authentication work?',
  'How does exception handling work?',
  'How is middleware implemented?',
]

export default function QueryPage({ defaultRepoId }) {
  const [repoId, setRepoId]       = useState(defaultRepoId || '')
  const [question, setQuestion]   = useState('')
  const [answer, setAnswer]       = useState('')
  const [sources, setSources]     = useState([])
  const [streaming, setStreaming] = useState(false)
  const [latency, setLatency]     = useState(null)
  const [error, setError]         = useState(null)
  const startTime = useRef(null)

  async function askQuestion() {
    if (!repoId || !question || streaming) return
    setStreaming(true)
    setAnswer('')
    setSources([])
    setLatency(null)
    setError(null)
    startTime.current = Date.now()

    try {
      for await (const event of queryStream(repoId, question)) {
        if (event.type === 'sources') setSources(event.sources)
        if (event.type === 'token')   setAnswer(prev => prev + event.content)
        if (event.type === 'done') {
          setLatency(Date.now() - startTime.current)
          setStreaming(false)
        }
      }
    } catch (err) {
      setError(err.message)
      setStreaming(false)
    }
  }

  const hasResults = answer || streaming || sources.length > 0

  return (
    <div>
      {/* Heading */}
      <div style={{ marginBottom: '24px' }}>
        <h1 style={{ fontSize: '18px', fontWeight: 600, color: 'var(--text)', marginBottom: '4px' }}>
          Query Codebase
        </h1>
        <p style={{ fontSize: '13px', color: 'var(--text-2)', lineHeight: 1.6 }}>
          Ask questions in plain English — get answers with exact file and line citations.
        </p>
      </div>

      {/* Input card */}
      <div className="card" style={{ marginBottom: '16px' }}>
        <div style={{ padding: '20px' }}>

          <div className="form-group" style={{ maxWidth: '300px', marginBottom: '20px' }}>
            <label className="form-label">Repository ID</label>
            <input className="form-input" type="text" value={repoId}
              onChange={e => setRepoId(e.target.value)}
              placeholder="my-repo" />
          </div>

          <div style={{ marginBottom: '16px' }}>
            <div className="section-label">Suggestions</div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
              {SUGGESTED.map(q => (
                <button key={q} className="chip" onClick={() => setQuestion(q)}>
                  {q.length > 46 ? q.slice(0, 44) + '…' : q}
                </button>
              ))}
            </div>
          </div>

          <div style={{ display: 'flex', gap: '8px' }}>
            <input
              className="form-input"
              style={{ flex: 1 }}
              type="text"
              value={question}
              onChange={e => setQuestion(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && askQuestion()}
              placeholder="How does the routing system handle HTTP methods?"
            />
            <button className="btn btn-primary" onClick={askQuestion} disabled={streaming}
              style={{ minWidth: '72px' }}>
              {streaming ? '...' : 'Ask →'}
            </button>
          </div>

        </div>
      </div>

      {/* Error */}
      {error && (
        <div style={{
          display: 'flex', alignItems: 'center', gap: '8px',
          padding: '10px 14px',
          background: 'var(--red-bg)',
          border: '1px solid rgba(248,113,113,0.25)',
          borderRadius: '8px',
          marginBottom: '16px',
          fontSize: '13px',
          color: 'var(--red)',
        }}>
          <span>⚠</span>
          <span>{error}</span>
        </div>
      )}

      {/* Results grid */}
      {hasResults && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 260px', gap: '16px', alignItems: 'start' }}>

          {/* Answer */}
          <div>
            <div style={{
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              marginBottom: '8px',
            }}>
              <span className="section-label" style={{ marginBottom: 0 }}>Answer</span>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                {latency && (
                  <span style={{ fontSize: '12px', color: 'var(--text-3)', fontFamily: 'var(--mono)' }}>
                    {(latency / 1000).toFixed(1)}s
                  </span>
                )}
                {streaming && <span className="badge badge-processing">Streaming</span>}
                {!streaming && answer && <span className="badge badge-completed">Done</span>}
              </div>
            </div>

            <div className="card" style={{ padding: '20px' }}>
              <div className="answer-area">
                {answer
                  ? <>{answer}{streaming && <span className="answer-cursor" />}</>
                  : <span style={{ color: 'var(--text-3)' }}>
                      {streaming ? 'Searching codebase…' : ''}
                    </span>
                }
              </div>
            </div>
          </div>

          {/* Sources */}
          <div>
            <div className="section-label" style={{ marginBottom: '8px' }}>
              Sources {sources.length > 0 && `(${sources.length})`}
            </div>
            <div className="card" style={{ position: 'sticky', top: '68px' }}>
              {sources.length === 0 ? (
                <div style={{ padding: '16px', fontSize: '13px', color: 'var(--text-3)' }}>
                  File citations appear here
                </div>
              ) : (
                sources.map((s, i) => (
                  <div key={i} className="source-item">
                    <div className="source-file">{s.file.replace(/\\/g, '/')}</div>
                    <div className="source-lines">lines {s.start_line}–{s.end_line}</div>
                  </div>
                ))
              )}
            </div>
          </div>

        </div>
      )}

      {/* Empty state */}
      {!hasResults && !error && (
        <div style={{
          textAlign: 'center',
          padding: '64px 20px',
          color: 'var(--text-3)',
          fontSize: '14px',
        }}>
          Ask a question above to get started
        </div>
      )}
    </div>
  )
}
