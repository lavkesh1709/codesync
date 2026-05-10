import { useState, useRef } from 'react'
import { queryStream } from '../api/codesync'
import './styles.css'

const QUICK_QUESTIONS = [
  'How does dependency injection work?',
  'How does the Depends class work internally?',
  'How does the routing system work?',
  'How are middleware components implemented?',
  'How does authentication work?',
  'How does exception handling work?',
]

export default function QueryPage({ defaultRepoId }) {
  const [repoId, setRepoId] = useState(defaultRepoId || 'fastapi-main')
  const [question, setQuestion] = useState('')
  const [answer, setAnswer] = useState('')
  const [sources, setSources] = useState([])
  const [streaming, setStreaming] = useState(false)
  const [latency, setLatency] = useState(null)
  const [streamStatus, setStreamStatus] = useState(null)
  const startTime = useRef(null)

  async function askQuestion() {
    if (!repoId || !question || streaming) return
    setStreaming(true)
    setAnswer('')
    setSources([])
    setLatency(null)
    setStreamStatus('streaming')
    startTime.current = Date.now()

    try {
      for await (const event of queryStream(repoId, question)) {
        if (event.type === 'sources') setSources(event.sources)
        if (event.type === 'token') setAnswer(prev => prev + event.content)
        if (event.type === 'done') {
          setLatency(Date.now() - startTime.current)
          setStreaming(false)
          setStreamStatus('complete')
        }
      }
    } catch (err) {
      setAnswer(`Error: ${err.message}`)
      setStreaming(false)
      setStreamStatus('error')
    }
  }

  return (
    <div>
      {/* Hero */}
      <div style={{ marginBottom: '40px' }}>
        <div className="page-title">Query Codebase</div>
        <div className="page-subtitle">Ask in plain English — get answers with exact file and line citations, powered by BM25 + vector search and cross-encoder reranking.</div>
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
          <div className="field" style={{ maxWidth: '320px' }}>
            <label>Repository ID</label>
            <input type="text" value={repoId}
              onChange={e => setRepoId(e.target.value)}
              placeholder="fastapi-main" />
          </div>

          {/* Quick questions */}
          <div style={{ marginBottom: '16px' }}>
            <div className="section-label">Quick questions</div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
              {QUICK_QUESTIONS.map(q => (
                <button key={q} className="quick-btn"
                  onClick={() => setQuestion(q)}>
                  {q.length > 40 ? q.slice(0, 38) + '...' : q}
                </button>
              ))}
            </div>
          </div>

          {/* Question input */}
          <div style={{ display: 'flex', gap: '12px' }}>
            <input type="text" value={question}
              onChange={e => setQuestion(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && askQuestion()}
              placeholder="How does the routing system handle HTTP methods?"
              style={{ flex: 1, background: '#fff', border: '1.5px solid #e9e0c8', borderRadius: '8px', padding: '12px 16px', fontFamily: 'JetBrains Mono, monospace', fontSize: '14px', color: '#1c1917', outline: 'none', transition: 'border-color 0.15s' }}
              onFocus={e => e.target.style.borderColor = '#b45309'}
              onBlur={e => e.target.style.borderColor = '#e9e0c8'}
            />
            <button className="btn-primary" onClick={askQuestion} disabled={streaming}
              style={{ whiteSpace: 'nowrap', minWidth: '80px' }}>
              {streaming ? '...' : 'Ask ↵'}
            </button>
          </div>
        </div>
      </div>

      {/* Answer + Sources grid */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 280px', gap: '20px', alignItems: 'start' }}>

        {/* Answer */}
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
            <div className="section-label">Answer</div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              {latency && <span style={{ fontFamily: 'JetBrains Mono', fontSize: '11px', color: '#94a3b8' }}>↳ {latency}ms</span>}
              {streamStatus && (
                <span className={`status-pill ${streamStatus === 'streaming' ? 'processing' : streamStatus === 'complete' ? 'completed' : 'error'}`}>
                  <span style={{ width: '5px', height: '5px', borderRadius: '50%', background: 'currentColor', display: 'inline-block' }} />
                  {streamStatus}
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
              <span style={{ color: '#94a3b8', fontStyle: 'italic', fontSize: '14px' }}>
                {streaming ? 'Retrieving relevant code...' : 'Answer streams here word by word after you ask a question.'}
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
            <div style={{ padding: '20px 16px', fontFamily: 'JetBrains Mono', fontSize: '12px', color: '#94a3b8' }}>
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

      <style>{`@keyframes blink { 0%,100%{opacity:1} 50%{opacity:0} }`}</style>
    </div>
  )
}