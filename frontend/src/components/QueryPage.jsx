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
      <div style={{ marginBottom: '28px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '8px' }}>
          <div style={{
            width: '34px', height: '34px', borderRadius: '9px',
            background: 'var(--accent-bg)',
            border: '1px solid rgba(99,102,241,0.2)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            flexShrink: 0,
          }}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
            </svg>
          </div>
          <h1 style={{ fontSize: '20px', fontWeight: 700, color: 'var(--text)', letterSpacing: '-0.4px', lineHeight: 1 }}>
            Query Codebase
          </h1>
        </div>
        <p style={{ fontSize: '13px', color: 'var(--text-2)', lineHeight: 1.6, marginLeft: '44px' }}>
          Ask in plain English — get answers with exact file and line citations.
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
        <div style={{ textAlign: 'center', padding: '56px 20px' }}>
          <div style={{
            width: '52px', height: '52px', borderRadius: '14px',
            background: 'var(--accent-bg)',
            border: '1px solid rgba(99,102,241,0.18)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            margin: '0 auto 16px',
          }}>
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
            </svg>
          </div>
          <p style={{ fontSize: '15px', fontWeight: 600, color: 'var(--text-2)', marginBottom: '8px' }}>
            Ask anything about the codebase
          </p>
          <p style={{ fontSize: '13px', color: 'var(--text-3)', lineHeight: 1.7 }}>
            "How does authentication work?" · "Where is payment handled?"<br/>
            "What does OrderService do?" · "How is middleware implemented?"
          </p>
        </div>
      )}
    </div>
  )
}
