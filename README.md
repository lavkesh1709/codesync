# CodeSync

**Ask questions about any codebase in plain English. Get answers with exact file and line citations.**

CodeSync is a self-hosted RAG (Retrieval-Augmented Generation) system built for codebase intelligence. Point it at a GitHub repository, and ask questions the way you'd ask a senior engineer who has read every line of code.

> Built to deeply understand retrieval engineering, LLM infrastructure, and production backend systems — not to use existing RAG frameworks.

---

## Demo

**Question:** "How does dependency injection work internally?"

**Answer:**
```
FastAPI's dependency injection is handled through the Depends() function
defined in fastapi/params.py (lines 746-749).

At request time, solve_dependencies() in fastapi/dependencies/utils.py
(lines 347-421) walks the dependency tree depth-first, calls each
dependency function, and injects results into your route handler.

Sources:
  fastapi/params.py                    lines 746-749   score 0.94
  fastapi/dependencies/utils.py        lines 347-421   score 0.91
  fastapi/routing.py                   lines 201-244   score 0.87
```

---

## Architecture

```
Ingestion Pipeline (async, Celery worker):
  GitHub URL → Clone → Walk files → AST chunk → Embed → Store in pgvector

Query Pipeline (real-time, streaming):
  Question → Embed → Hybrid search (BM25 + vector) → Rerank → Groq → Stream
```

### Key technical decisions

**Hybrid retrieval (BM25 + pgvector)**
Pure vector search finds semantically similar text but misses exact matches — a question about `solve_dependencies` returns documentation instead of the function definition. BM25 catches exact token matches. Reciprocal Rank Fusion combines both ranked lists into one.

**Cross-encoder reranking**
After hybrid search retrieves 20 candidates, a cross-encoder model (`ms-marco-MiniLM`) scores each `(question, chunk)` pair directly — much more precise than cosine similarity alone. Top 5 go to the LLM.

**AST-aware chunking (tree-sitter)**
Line-based chunking cuts functions in half. tree-sitter parses Python ASTs and extracts complete functions and classes as individual chunks. A 60-line function becomes one semantically complete unit.

**Dependency graph expansion**
Import statements are parsed during ingestion and stored as an adjacency list. When `auth/routes.py` is retrieved, chunks from `auth/utils.py` (which routes.py imports) are automatically included in context — giving the LLM the full call chain.

**Async ingestion (Celery)**
Ingestion of a large repo takes 8+ minutes. The API returns a `job_id` immediately. A Celery worker processes in the background. Client polls `/api/v1/ingest/{job_id}/status`.

**Streaming responses (SSE)**
The `/api/v2/query` endpoint streams tokens as Groq generates them — sources arrive first, then the answer streams word by word.

---

## Tech Stack

| Layer | Technology |
|---|---|
| API framework | FastAPI (async) |
| Database | PostgreSQL 16 + pgvector (HNSW index) |
| ORM + migrations | SQLAlchemy 2.0 async + Alembic |
| Vector search | pgvector cosine similarity |
| Keyword search | BM25 (rank-bm25) |
| Embeddings | sentence-transformers (all-MiniLM-L6-v2, local) |
| Reranking | CrossEncoder (ms-marco-MiniLM, local) |
| Code parsing | tree-sitter |
| LLM | Groq API (llama-3.1-8b-instant) |
| Task queue | Celery + Redis |
| Frontend | React + Vite |
| Package manager | uv |
| Containerization | Docker + docker-compose |

---

## Project Structure

```
codesync/
├── app/
│   ├── api/routes/          # HTTP layer — ingest, query, query_v2
│   ├── core/
│   │   ├── ingestion/       # cloner, file_walker, chunker, embedder, tasks
│   │   └── retrieval/       # searcher (hybrid+rerank), generator (stream)
│   ├── db/
│   │   ├── models.py        # SQLAlchemy table definitions
│   │   ├── session.py       # async connection pool
│   │   └── repositories/    # all SQL — repository pattern
│   ├── config.py            # pydantic-settings, all config from env vars
│   └── main.py              # FastAPI app, router registration
├── frontend/                # React + Vite UI
├── alembic/                 # database migrations
├── docker/postgres/         # pgvector extension setup
└── docker-compose.yml       # postgres + redis
```

---

## API Endpoints

```
POST /api/v1/ingest                    Queue a repo for indexing
GET  /api/v1/ingest/{job_id}/status   Poll ingestion progress
POST /api/v1/query                     Query (full JSON response)
POST /api/v2/query                     Query (SSE streaming)
GET  /health                           Health check
```

---

## Running Locally

**Prerequisites:** Docker Desktop, Python 3.11+, Node.js 18+, uv

```bash
# Clone
git clone https://github.com/lavkesh1709/codesync.git
cd codesync

# Install Python dependencies
uv sync

# Copy env and fill in your Groq API key
cp .env.example .env

# Start infrastructure
docker-compose up -d

# Run database migrations
uv run alembic upgrade head

# Start API server
uv run uvicorn app.main:app --reload --port 8000

# Start Celery worker (new terminal)
uv run celery -A app.core.ingestion.tasks.celery_app worker --loglevel=info --pool=solo

# Start frontend (new terminal)
cd frontend && npm install && npm run dev
```

Open http://localhost:5173

**Get a free Groq API key at:** https://console.groq.com

---

## Usage

**Index a repository:**
```bash
curl -X POST http://localhost:8000/api/v1/ingest \
  -H "Content-Type: application/json" \
  -d '{"repo_url": "https://github.com/tiangolo/fastapi", "repo_id": "fastapi"}'
```

**Query it:**
```bash
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"repo_id": "fastapi", "question": "How does routing work?"}'
```

---

## What I learned building this

The quality of a RAG system is entirely determined by retrieval quality — not the LLM. Improving the prompt had almost no effect. Improving what gets retrieved made answers dramatically better.

Key insights:

- **Pure vector search is insufficient for code** — it finds semantically similar text but misses exact matches. Hybrid BM25+vector fixed the case where a question about `solve_dependencies` returned French documentation instead of the function definition.

- **Chunking strategy matters more than model choice** — line-based chunking cut functions in half, making embeddings meaningless. AST-aware chunking with tree-sitter made each chunk a semantically complete unit.

- **The repository pattern pays off** — separating SQL into `db/repositories/` meant swapping pgvector configurations required changing one file. Nothing else broke.

- **Async from day one** — retrofitting async into sync FastAPI is painful. The decision to use `async def` everywhere from the first file saved significant refactoring.

---

## Roadmap

- [ ] Semantic caching — similar questions return cached answers in ~50ms
- [ ] Circuit breaker — auto-failover from Groq to Gemini
- [ ] HyDE (Hypothetical Document Embeddings) — embed a hypothetical answer instead of the raw question for better retrieval
- [ ] Hierarchical index — directory and file summaries for large repo navigation
- [ ] Deploy to Render

---

## Known Limitations

- Ingestion is slow on CPU (~8 min for FastAPI repo) — embeddings are CPU-bound
- The `all-MiniLM-L6-v2` model has a 256 token input limit — very long functions get truncated
- BM25 index is rebuilt in memory per query for the first request — subsequent queries use cached index
- Private repositories not yet supported (Phase 2+ enhancement)