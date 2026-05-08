// All API calls in one place
// Vite proxy forwards /api/* to FastAPI at localhost:8000

export async function checkHealth() {
  const res = await fetch('/health')
  return res.json()
}

export async function ingestRepo(repoUrl, repoId) {
  const res = await fetch('/api/v1/ingest', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ repo_url: repoUrl, repo_id: repoId })
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function getIngestStatus(jobId, repoId) {
  const res = await fetch(`/api/v1/ingest/${jobId}/status?repo_id=${repoId}`)
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function* queryStream(repoId, question, topK = 5) {
  // Returns an async generator — yields parsed SSE events
  const res = await fetch('/api/v2/query', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ repo_id: repoId, question, top_k: topK })
  })

  if (!res.ok) throw new Error(await res.text())

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop()

    for (const line of lines) {
      if (!line.startsWith('data: ')) continue
      try {
        yield JSON.parse(line.slice(6))
      } catch {}
    }
  }
}