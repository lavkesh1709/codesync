# CodeSync

**Ask questions about any codebase in plain English. Get answers with exact file and line citations.**

CodeSync is a self-hosted RAG (Retrieval-Augmented Generation) system for codebase intelligence. Point it at a public GitHub repository, ask questions the way you'd ask a senior engineer who has read every line of code, and get answers that cite the exact file and line where the answer lives.

> Built from scratch to understand retrieval engineering and LLM infrastructure — no LangChain, no LlamaIndex, no RAG frameworks.

**Live demo:** https://codesync-cee8.onrender.com

---

## Demo

<!-- Add a GIF here: record a 20s clip of indexing a repo + streaming a query answer -->

**Question:** *"How does dependency injection work internally?"*

**Answer:**
```
FastAPI's dependency injection is handled through the Depends() function
defined in fastapi/params.py (lines 746–749).

At request time, solve_dependencies() in fastapi/dependencies/utils.py
(lines 347–421) walks the dependency tree depth-first, calls each
dependency function, and injects results into your route handler.

Sources:
  fastapi/params.py                lines 746–749
  fastapi/dependencies/utils.py   lines 347–421
  fastapi/routing.py               lines 201–244
```

---

## Architecture

```
Ingestion pipeline
  GitHub URL → Clone → Walk files → AST chunk (tree-sitter)
             → Embed (Cohere API) → Store in pgvector

Query pipeline
  Question → Embed (Cohere API) → Hybrid search (BM25 + pgvector)
           → Reciprocal Rank Fusion → Groq LLM → SSE stream
```

### Key technical decisions

**Hybrid retrieval (BM25 + pgvector)**
Pure vector search finds semantically similar text but misses exact matches — a question about `solve_dependencies` returned French documentation instead of the function definition. BM25 catches exact token matches. Reciprocal Rank Fusion merges both ranked lists. Hybrid search fixed the docs-over-source-code problem completely.

**AST-aware chunking (tree-sitter)**
Line-based chunking cuts functions in half, making embeddings incoherent. tree-sitter parses Python ASTs and extracts complete functions and classes as individual chunks. A 60-line function becomes one semantically complete unit.

**Dependency graph expansion**
Import statements are parsed at ingestion time and stored as an adjacency list. When `auth/routes.py` is retrieved, chunks from `auth/utils.py` (which routes.py imports) are automatically added — giving the LLM the full call chain, not just the entry point.

**Cohere embeddings via HTTP API**
Embedding models loaded locally (sentence-transformers) exceed the 512 MB RAM limit on Render's free tier. Replaced with Cohere's `embed-english-light-v3.0` via HTTP API — same 384-dim output, zero local memory overhead, with retry logic and exponential backoff for rate limits.

**Semantic cache**
Answers are stored with their question embedding. On each new query, a cosine similarity check (threshold 0.92) runs first. A cache hit returns the answer in ~50ms instead of ~4s. Cache is invalidated when the repo is re-indexed.

**Streaming responses (SSE)**
`POST /api/v2/query` streams tokens as Groq generates them. Sources arrive first as a JSON event, then the answer streams word by word.

---

## Tech Stack

| Layer | Technology |
|---|---|
| API | FastAPI (async) |
| Database | PostgreSQL 16 + pgvector (HNSW index) — Neon |
| ORM + migrations | SQLAlchemy 2.0 async + Alembic |
| Vector search | pgvector cosine similarity |
| Keyword search | BM25 (rank-bm25) |
| Embeddings | Cohere API (`embed-english-light-v3.0`, 384-dim) |
| Code parsing | tree-sitter |
| LLM | Groq API (llama-3.1-8b-instant) |
| Task queue | Celery + Redis — Upstash |
| Frontend | React 19 + Vite 8 |
| Package manager | uv |
| Hosting | Render (Docker) |

---

## Project Structure

```
codesync/
├── app/
│   ├── api/routes/          # HTTP layer — ingest, query v1, query v2 (SSE)
│   ├── core/
│   │   ├── ingestion/       # cloner, file_walker, chunker, embedder, tasks
│   │   └── retrieval/       # searcher (hybrid BM25+vector+RRF), generator
│   ├── db/
│   │   ├── models.py        # SQLAlchemy table definitions
│   │   ├── session.py       # async connection pool
│   │   └── repositories/    # all SQL queries — repository pattern
│   ├── config.py            # pydantic-settings, config from env vars only
│   └── main.py              # FastAPI app, static serving, lifespan migrations
├── frontend/                # React 19 + Vite source
├── static/                  # built frontend (served by FastAPI in production)
└── alembic/                 # database migrations
```

---

## API

```
POST /api/v1/ingest                     Index a repository
GET  /api/v1/ingest/{job_id}/status    Poll ingestion progress
POST /api/v1/query                      Query — full JSON + semantic cache
POST /api/v2/query                      Query — SSE streaming
GET  /health                            Health check
```

**Index a repository:**
```bash
curl -X POST https://codesync-cee8.onrender.com/api/v1/ingest \
  -H "Content-Type: application/json" \
  -d '{"repo_url": "https://github.com/tiangolo/fastapi", "repo_id": "fastapi"}'
```

**Query it:**
```bash
curl -X POST https://codesync-cee8.onrender.com/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"repo_id": "fastapi", "question": "How does routing work?"}'
```

---

## Running Locally

**Prerequisites:** Python 3.11+, Node.js 18+, uv, git

**Free accounts required:**
- [Neon](https://neon.tech) — cloud Postgres with pgvector
- [Upstash](https://upstash.com) — cloud Redis
- [Groq](https://console.groq.com) — LLM API
- [Cohere](https://dashboard.cohere.com) — embeddings API

```bash
git clone https://github.com/lavkesh1709/codesync.git
cd codesync

uv sync

cp .env.example .env
# Fill in DATABASE_URL, GROQ_API_KEY, COHERE_API_KEY, REDIS_URL

uv run alembic upgrade head
```

Then open three terminals:

```bash
# Terminal 1 — API
uv run uvicorn app.main:app --reload --port 8000

# Terminal 2 — Celery worker (async ingestion)
uv run celery -A app.core.ingestion.tasks.celery_app worker --loglevel=info --pool=solo

# Terminal 3 — Frontend
cd frontend && npm install && npm run dev
```

Open http://localhost:5173

No Docker Desktop required. Neon and Upstash are cloud services — the same instances used in production.

---

## What I Learned Building This

The quality of a RAG system is determined by retrieval, not the LLM. Improving the prompt had almost no effect. Improving what gets retrieved made answers dramatically better.

**Things that actually mattered:**

- **Chunking strategy beats model choice.** Line-based chunking cut functions in half. AST chunking with tree-sitter made each chunk a semantically complete unit. This single change improved retrieval quality more than any model swap.

- **Pure vector search fails on code.** The first version returned French documentation when asked about `solve_dependencies`. BM25 catches exact identifier matches that cosine similarity misses. Hybrid retrieval with RRF fixed it completely.

- **Latency comes from embedding, not the LLM.** The slow part of the query pipeline is embedding the question, not Groq generating the answer. Semantic caching eliminates this for repeated questions — 50ms vs 4s.

- **Repository pattern pays off fast.** All SQL lives in `db/repositories/`. Switching the embedding backend from local sentence-transformers to Cohere's API required changing one file. Nothing else broke.

- **Async from the first line.** Retrofitting async into sync FastAPI is painful. Starting with `async def` everywhere from day one saved significant refactoring when adding streaming endpoints and background workers.

---

## Roadmap

- [x] Hybrid retrieval — BM25 + pgvector + Reciprocal Rank Fusion
- [x] AST-aware chunking with tree-sitter
- [x] Dependency graph (import adjacency list)
- [x] Async ingestion with Celery + job status polling
- [x] Streaming responses (SSE)
- [x] Semantic cache (pgvector similarity, 0.92 threshold)
- [x] Deployed to Render
- [ ] HyDE — embed a hypothetical answer instead of the raw question
- [ ] Hierarchical index — directory and file summaries for large repo navigation
- [ ] Cross-encoder reranking (disabled on free tier RAM limit)
- [ ] Circuit breaker — auto-failover from Groq to Gemini
- [ ] Private repository support via GitHub PAT

---

## Known Limitations

**Ingestion is slow on the free tier**
Cohere's free trial key is rate-limited to ~30 calls/minute. Indexing a large repo (10,000+ chunks) takes 8–10 minutes. The pipeline retries automatically on rate limit responses.

**Import parsing is Python-only**
The dependency graph uses Python's `ast` module. JS/TS/Go repos get no import-based context expansion.

**No rate limiting**
The API has no per-client rate limiting — the Groq and Cohere keys can be exhausted in production without it.

**Private repositories not supported**
Public GitHub URLs only.

**Cross-encoder reranking disabled in production**
The ms-marco-MiniLM cross-encoder requires ~400 MB RAM. Disabled on Render's free tier (512 MB total). Re-enables automatically if `ENABLE_RERANKING=true` is set on a paid instance.
