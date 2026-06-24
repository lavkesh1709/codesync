import { useState, useRef } from 'react'
import { queryStream } from '../api/codesync'
import './styles.css'

const QUICK_QUESTIONS = [
  'How does dependency injection work?',
  'How does the routing system work?',
  'How does authentication work?',
  'How does exception handling work?',
  'How is middleware implemented?',
  'How are background tasks handled?',
]

export default function QueryPage({ defaultRepoId }) {
  const [repoId, setRepoId] = useState(defaultRepoId || '')
  const [question, setQuestion] = useState('')
  const [answer, setAnswer] = useState('')
  const [sources, setSources] = useState([])
  const [streaming, setStreaming] = useState(false)
  const [latency, setLatency] = useState(null)
  const [error, setError] = useState(null)
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

  return (
    <div>
      <div style={{ marginBottom: '36px' }}>
        <div className="page-title">Query Codebase</div>
        <div className="page-subtitle">
          Ask in plain English — get answers with exact file and line citations powered by hybrid BM25 + vector search.
        </div>
      </div>

      {/* Input panel */}
      <div className="panel" style={{ marginBottom: '24px' }}>
        <div className="panel-header">
          <div className="panel-dot" style={{ background: '#ff5f57' }} />
          <div className="panel-dot" style={{ background: '#febc2e' }} />
          <div className="panel-dot" style={{ background: '#28c840' }} />
          <span className="panel-label">query.input</span>
        </div>

        <div className="panel-body">
          <div className="field" style={{ maxWidth: '340px' }}>
            <label>Repository ID</label>
            <input type="text" value={repoId}
              onChange={e => setRepoId(e.target.value)}
              placeholder="my-repo" />
          </div>

          <div style={{ marginBottom: '16px' }}>
            <div className="section-label">Quick questions</div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
              {QUICK_QUESTIONS.map(q => (
                <button key={q} className="quick-btn" onClick={() => setQuestion(q)}>
                  {q.length > 42 ? q.slice(0, 40) + '…' : q}
                </button>
              ))}
            </div>
          </div>

          <div style={{ display: 'flex', gap: '12px' }}>
            <input type="text" value={question}
              onChange={e => setQuestion(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && askQuestion()}
              placeholder="How does the routing system handle HTTP methods?"
              className="query-input"
            />
            <button className="btn-primary" onClick={askQuestion} disabled={streaming}
              style={{ whiteSpace: 'nowrap', minWidth: '90px' }}>
              {streaming ? '…' : 'Ask ↵'}
            </button>
          </div>
        </div>
      </div>

      {/* Error banner */}
      {error && (
        <div className="error-panel" style={{ marginBottom: '20px' }}>
          <div className="error-panel-header" style={{ cursor: 'default' }}>
            <span>⚠ {error}</span>
          </div>
        </div>
      )}

      {/* Answer + Sources */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 280px', gap: '20px', alignItems: 'start' }}>

        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
            <div className="section-label">Answer</div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              {latency && (
                <span style={{ fontFamily: 'JetBrains Mono', fontSize: '11px', color: 'var(--text-dimmer)' }}>
                  ↳ {(latency / 1000).toFixed(1)}s
                </span>
              )}
              {streaming && (
                <span className="status-pill processing">
                  <span style={{ width: '5px', height: '5px', borderRadius: '50%', background: 'currentColor', display: 'inline-block' }} />
                  streaming
                </span>
              )}
              {!streaming && answer && (
                <span className="status-pill completed">
                  <span style={{ width: '5px', height: '5px', borderRadius: '50%', background: 'currentColor', display: 'inline-block' }} />
                  complete
                </span>
              )}
            </div>
          </div>

          <div className={`answer-box ${streaming ? 'streaming' : ''}`}>
            {answer ? (
              <>
                {answer}
                {streaming && <span style={{ color: '#00ff88', animation: 'blink 0.7s step-end infinite' }}>▋</span>}
              </>
            ) : (
              <span style={{ color: 'var(--text-dimmer)', fontStyle: 'italic', fontSize: '13px' }}>
                {streaming
                  ? 'Searching codebase…'
                  : 'Answer streams here word by word after you ask a question.'}
              </span>
            )}
          </div>
        </div>

        {/* Sources */}
        <div className="panel" style={{ position: 'sticky', top: '20px' }}>
          <div className="panel-header">
            <span className="panel-label" style={{ marginLeft: 0 }}>
              Sources {sources.length > 0 && `(${sources.length})`}
            </span>
          </div>
          {sources.length === 0 ? (
            <div style={{ padding: '20px 16px', fontFamily: 'JetBrains Mono', fontSize: '12px', color: 'var(--text-dimmer)' }}>
              File citations appear here
            </div>
          ) : (
            sources.map((s, i) => (
              <div key={i} className="source-card">
                <div className="source-file">{s.file.replace(/\\/g, '/')}</div>
                <div className="source-lines">lines {s.start_line}–{s.end_line}</div>
              </div>
            ))
          )}
        </div>
      </div>

      <style>{`
        @keyframes blink { 0%,100%{opacity:1} 50%{opacity:0} }
        .query-input {
          flex: 1;
          background: var(--input-bg);
          border: 1.5px solid var(--border);
          border-radius: 8px;
          padding: 12px 16px;
          font-family: JetBrains Mono, monospace;
          font-size: 14px;
          color: var(--text);
          outline: none;
          transition: border-color 0.15s, box-shadow 0.15s;
        }
        .query-input:focus {
          border-color: var(--accent);
          box-shadow: 0 0 0 3px rgba(180,83,9,0.1);
        }
        .query-input::placeholder { color: var(--text-dimmer); }
      `}</style>
    </div>
  )
}
