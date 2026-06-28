# CodeSync — Complete Project Specification

**Version:** 6.0
**Status:** Phase 5 Complete — Live on Render
**Last updated:** June 2026
**Live URL:** https://codesync-cee8.onrender.com
**GitHub:** https://github.com/lavkesh1709/codesync

---

## 1. What Is CodeSync

CodeSync is a self-hosted codebase intelligence tool. You point it at a GitHub
repository, ask questions in plain English, and get accurate answers with exact
file and line number citations.

**One line pitch:**
"Ask any question about any codebase and get answers with exact file citations —
like having a senior engineer who has read every line of code."

**Existing products doing this:** Cursor, GitHub Copilot Chat, Sourcegraph Cody,
Greptile. We are not competing with them. We are building our own implementation
to learn the stack deeply and demonstrate the skills those teams need to hire.

---

## 2. The Problem It Solves

Every developer has faced this:
- Joining a new team with 100,000 lines of undocumented code
- Needing to understand how a feature works before touching it
- Wanting to know which files handle a specific concern
- Trying to understand an open source library from its source

Current solutions are bad:
- Grep/search: finds text but not meaning
- Reading code manually: takes hours
- Asking teammates: blocks other people
- ChatGPT: does not know your codebase, hallucinates file names

CodeSync indexes your codebase once and lets you query it semantically.

---

## 3. Who Uses It

Primary user: A developer who needs to understand an unfamiliar codebase.

Concrete scenarios:
- New joiner understanding how auth works before their first PR
- Developer finding where a concept is implemented while debugging
- Open source contributor understanding a library before submitting a fix
- Tech lead auditing code before a security review

---

## 4. What CodeSync Can and Cannot Answer

Answers well:
- "How does authentication work?" — explains mechanism with file citations
- "Where is payment processing handled?" — finds exact files and functions
- "How do I set up this project locally?" — reads README, Makefile, docker-compose
- "What are the coding conventions?" — reads CONTRIBUTING.md, linter config
- "What does OrderService do?" — explains class from source code

Answers poorly or not at all:
- "Why did the team choose Postgres over MongoDB?" — undocumented decisions
- "What happens under high load?" — runtime behavior not written in code
- "Is this codebase well architected?" — requires judgment, not retrieval

Rule: CodeSync only knows what is written in the indexed files.

---

## 5. What CodeSync Does NOT Build

- No user authentication system
- No billing or usage limits
- No GCS/S3/MinIO staging (temp directory sufficient at this scale)
- No microservices (monolith through all phases)
- No fine-tuning of any model

---

## 6. Complete Phase Breakdown

### Phase 1 — Core pipeline ✅ COMPLETE
Proven results on FastAPI repo:
- 2,554 files processed, 11,413 chunks created
- Query latency: ~1,250ms
- Working end-to-end: ingest → chunk → embed → search → answer

Known issue identified: Pure vector search returns docs over source code.

---

### Phase 2 — Better retrieval and async ingestion ✅ COMPLETE
What was built:
- tree-sitter AST chunking — functions extracted as complete units
- BM25 + vector hybrid search with Reciprocal Rank Fusion
- Celery background workers — ingest returns job_id immediately
- GET /api/v1/ingest/{job_id}/status — polls from Postgres (reliable)
- Dependency graph — 1,572 import relationships mapped for FastAPI repo
- BM25 in-memory cache per repo (built on first query, reused after)

Results:
- 12,614 chunks (better quality than 11,413 line-based chunks)
- fastapi/routing.py now appearing in results
- No more French/German/Korean docs in results
- Ingest returns job_id in ~1 second instead of blocking 7 minutes

---

### Phase 3 — Reranking, streaming, UI ✅ COMPLETE
What was built:
- Cross-encoder reranking (ms-marco-MiniLM-L-6-v2)
  Retrieve top 20 candidates, rerank to true top 5
  fastapi/params.py now ranks FIRST for "How does Depends work?"
- Streaming endpoint POST /api/v2/query
  SSE stream: sources event → token events → done event
  Answer appears word by word
- React + Vite frontend
  IngestPage: repo URL input, presets, live log terminal, progress bar
  QueryPage: streaming answer, sources panel, quick questions
  Persistent state across tab switches (lifted to App.jsx)
- Error handling chain: cloner → ingest route → React UI

Quality milestone:
- Phase 1: French docs first for "How does Depends work?"
- Phase 3: fastapi/params.py FIRST — source code over docs ✓

---

### Phase 4 — Caching and observability — PARTIAL ✅
What was built:
- Semantic cache (cache_entries table + pgvector similarity search)
  Similarity threshold: 0.92, TTL: 24 hours
  Proven: ~50ms cache hit vs ~4,000ms full pipeline
  Cache invalidated on re-ingest
- file_walker.py: added .agents and .github to skip dirs

Skipped — planned for Phase 6:
- Circuit breaker (Groq → Gemini failover)
- Request ID tracing
- Cost tracking
- HyDE (Hypothetical Document Embeddings)
- Hierarchical index
- BM25 cache moved to Redis
- Rate limiting (Redis token buckets)

---

### Phase 5 — Deploy to Render ✅ COMPLETE

**Live at:** https://codesync-cee8.onrender.com

What was built:
- Dockerfile (Python 3.11-slim, uv, git, build-essential)
- render.yaml (web service config)
- React frontend built into static/ and served by FastAPI in production
- Synchronous ingestion fallback for APP_ENV=production (no Celery needed)
- Switched embedding backend from local sentence-transformers to Cohere HTTP API
  — local models OOM'd on Render's 512MB free tier
  — Cohere embed-english-light-v3.0 gives same 384-dim vectors via API call
  — Rate limit handling: 2s inter-batch delay + exponential backoff on 429
- Reranker made safe: _get_reranker() catches ImportError and returns None
  gracefully instead of crashing when sentence_transformers is not installed
- UI redesigned: Inter font, zinc/indigo palette, clean professional components
  Removed: macOS dots, amber scheme, shimmer animations, forced monospace
- README rewritten: live URL, Cohere stack, updated setup (no Docker needed),
  accurate roadmap with completed items checked

Infrastructure deployed:
- App: Render Web Service (Docker, free tier, 512MB RAM)
- Database: Neon (cloud Postgres, pgvector enabled, free tier)
- Redis: Upstash (cloud Redis, TLS, free tier)
- Worker: Not deployed (free tier limitation — sync fallback used instead)

Known production constraints:
- Render free tier cold starts after 15min idle (~30–60s first request)
- Cohere free key: ~30 embed calls/min → large repos take 8–10 min to index
- No Celery worker → ingestion blocks web request in production
- ENABLE_RERANKING=false → cross-encoder disabled to stay under 512MB RAM
- No rate limiting on API endpoints → Groq/Cohere keys unprotected

---

### Phase 6 — Quality and resilience improvements ← NEXT

Priority order based on interview value and implementation effort:

1. **HyDE (Hypothetical Document Embeddings)** — HIGH PRIORITY
   Generate a hypothetical answer to the question, embed that instead of
   the raw question. Hypothesis: embeddings of answers are closer to
   real answer chunks than embeddings of questions.
   ~20 lines in searcher.py. One extra Groq call per query.
   Strong differentiator — almost nobody at junior level knows about this.

2. **Hierarchical index** — HIGH PRIORITY
   Directory → file → chunk three-level index.
   New table: file_summaries. LLM generates one-paragraph summary per file
   at ingest time. Query first narrows to relevant files, then retrieves chunks.
   Solves large repo navigation problem. Greptile uses this approach.

3. **Rate limiting** — MEDIUM PRIORITY
   Redis token buckets per IP. Protects Groq and Cohere API keys in production.
   Without this, a single user can exhaust the free tier quota.

4. **Circuit breaker** — MEDIUM PRIORITY
   Auto-failover from Groq to Gemini (free tier) when Groq returns 429 or 5xx.
   Removes single point of failure on LLM provider.

5. **Cross-encoder reranking re-enabled** — REQUIRES PAID RENDER TIER
   ms-marco-MiniLM needs ~400MB RAM. Cannot run alongside the app on 512MB.
   Set ENABLE_RERANKING=true when upgrading to Render Starter ($7/month, 1GB RAM).

6. **BM25 cache to Redis** — LOW PRIORITY
   Current per-process in-memory BM25 cache is inconsistent across workers.
   Serializing to Redis fixes this. Only matters when running multiple workers.

7. **Multi-query retrieval** — LOW PRIORITY
   Generate 3 paraphrased variants of the question, retrieve for each, merge
   with deduplication. Improves recall on ambiguously-phrased questions.

8. **Private repository support** — LOW PRIORITY
   Accept GitHub PAT in request. Pass to git clone. Enables private repos.
   ~10 lines in cloner.py.

---

## 7. System Diagrams

### Architecture

```
┌─────────────────────────────────────────────────────────┐
│                        Frontend                          │
│              React + Vite  (Render static/)              │
│   IngestPage            QueryPage           App Shell    │
└──────────────────────┬──────────────────────────────────┘
                       │ HTTP
┌──────────────────────▼──────────────────────────────────┐
│                     FastAPI Backend                      │
│              https://codesync-cee8.onrender.com          │
│   /api/v1/ingest     /api/v1/ingest/{id}/status          │
│   /api/v1/query      /api/v2/query (SSE streaming)       │
│   /health                                                │
└──────┬───────────────────────────┬───────────────────────┘
       │                           │
┌──────▼──────┐           ┌────────▼────────┐
│    Redis     │           │    Postgres      │
│  Upstash     │           │    Neon          │
│  Task queue  │           │  repos           │
│  (dev only)  │           │  chunks          │
└──────┬───────┘           │  file_imports    │
       │                   │  cache_entries   │
┌──────▼──────┐            └─────────────────┘
│Celery Worker│
│  (dev only) │
│  Ingestion  │
│  Pipeline   │
└─────────────┘
```

---

### Ingestion Flow

```
POST /api/v1/ingest  { repo_url, repo_id }
        │
        ▼
  APP_ENV=production?
  ┌──── yes ──────────────────────────────────────────────┐
  │  run pipeline synchronously in web process            │
  └───────────────────────────────────────────────────────┘
  ┌──── no (development) ─────────────────────────────────┐
  │  ingest_repo_task.delay() → Redis → Celery worker     │
  │  returns job_id instantly                             │
  └───────────────────────────────────────────────────────┘
        │
        ▼
┌───────────────────────┐
│  1. clone_repo()      │  git clone --depth=1
├───────────────────────┤
│  2. walk_files()      │  filter by ext, skip dirs, max 1MB
├───────────────────────┤
│  3. chunk_files()     │  tree-sitter AST → whole functions
│                       │  fallback: 40 lines, 5 line overlap
├───────────────────────┤
│  4. embed_chunks()    │  Cohere embed-english-light-v3.0
│                       │  384-dim, batch=96, 2s delay/batch
│                       │  retry + backoff on 429
├───────────────────────┤
│  5. insert_chunks()   │  pgvector storage
├───────────────────────┤
│  6. parse_imports()   │  Python ast module → adjacency list
├───────────────────────┤
│  7. insert_imports()  │  file_imports table
├───────────────────────┤
│  8. update_repo()     │  status=completed
└───────────────────────┘
```

---

### Query Flow

```
POST /api/v2/query  { repo_id, question, top_k }
        │
        ▼
  verify repo exists + status=completed
        │
        ▼
  check semantic cache (cache_entries)
  cosine similarity > 0.92 → return cached answer (~50ms)
        │ cache miss
        ▼
  embed_text(question)  ← Cohere API, input_type=search_query
        │
        ├──────────────────────────────────┐
        ▼                                  ▼
  search_similar()                   _bm25_search()
  pgvector cosine distance           in-memory BM25 index
  top_k * 8 candidates               top_k * 8 candidates
        │                                  │
        └──────────────┬───────────────────┘
                       ▼
          _reciprocal_rank_fusion()
          score = Σ 1/(60 + rank)
                       │
                       ▼
          ENABLE_RERANKING=true?  (false in production)
          ┌── yes → CrossEncoder ms-marco-MiniLM (dev only)
          └── no  → candidates[:top_k]  (production)
                       │
                       ▼
          dependency graph expansion (Python repos only)
          get_imported_files() → fetch chunks from imports
          max 5 expansion files, 2 chunks each
                       │
                       ▼
          hard cap: max 10 chunks total
                       │
                       ▼
          generate_stream()
          Groq API — llama-3.1-8b-instant
          system prompt forces file citations
          temperature=0.1 (factual)
                       │
                       ▼
          SSE stream: sources → tokens → done
          store answer in cache_entries
```

---

### Database Schema

```
┌─────────────────────────────────┐
│             repos                │
├─────────────────────────────────┤
│ id              UUID  PK         │
│ repo_id         TEXT  UNIQUE     │
│ repo_url        TEXT             │
│ status          TEXT             │
│   cloning│walking│chunking       │
│   embedding│storing              │
│   completed│failed               │
│ files_processed  INTEGER         │
│ chunks_created   INTEGER         │
│ error_message    TEXT            │
│ created_at  TIMESTAMPTZ          │
│ updated_at  TIMESTAMPTZ          │
└──────────────┬──────────────────┘
               │ ON DELETE CASCADE
    ┌──────────┼──────────────────────────┐
    │          │                          │
┌───▼──────────────────┐  ┌──────────────▼──────────┐
│        chunks         │  │      file_imports        │
├──────────────────────┤  ├─────────────────────────┤
│ id         UUID  PK   │  │ id          UUID  PK     │
│ repo_id    TEXT  FK   │  │ repo_id     TEXT  FK     │
│ file_path  TEXT       │  │ source_file TEXT         │
│ start_line INTEGER    │  │ imported_file TEXT       │
│ end_line   INTEGER    │  │ created_at  TIMESTAMPTZ  │
│ content    TEXT       │  └─────────────────────────┘
│ embedding  VECTOR(384)│
│ created_at TIMESTAMPTZ│  ┌─────────────────────────┐
└──────────────────────┘  │     cache_entries        │
                           ├─────────────────────────┤
                           │ id          UUID  PK     │
                           │ repo_id     TEXT  FK     │
                           │ question_embedding       │
                           │             VECTOR(384)  │
                           │ question_text TEXT       │
                           │ answer      TEXT         │
                           │ sources     TEXT (JSON)  │
                           │ hit_count   INTEGER      │
                           │ created_at  TIMESTAMPTZ  │
                           │ expires_at  TIMESTAMPTZ  │
                           └─────────────────────────┘
```

---

## 9. Infrastructure

### Development (local)
```
Postgres:  Neon (cloud) — no Docker needed
Redis:     Upstash (cloud) — no Docker needed
uvicorn:   local (uv run uvicorn app.main:app --reload --port 8000)
Celery:    local (uv run celery -A ... worker --pool=solo)
Vite:      local (cd frontend && npm run dev)
```

### Production (Render)
```
Postgres:  Neon (same instance as dev)
Redis:     Upstash (same instance as dev)
App:       Render Web Service (Docker, free tier, 512MB RAM)
Worker:    Not deployed — synchronous fallback used in APP_ENV=production
Embedding: Cohere HTTP API (no local model loaded)
Frontend:  Built React in static/, served by FastAPI
```

### Why Cohere API instead of local sentence-transformers
sentence-transformers loads PyTorch + model weights (~400MB). Combined with
FastAPI and pgvector, this exceeds Render's 512MB free tier limit. The process
OOM-killed at startup. Cohere's embed-english-light-v3.0 produces identical
384-dim embeddings via a lightweight HTTP call. Zero RAM overhead. Switching
only required changing embedder.py — nothing else in the pipeline changed.

### Why Neon + Upstash instead of Docker Desktop
Docker Desktop + Postgres + Redis containers caused laptop overheating.
Neon and Upstash are free cloud services. Additional benefit: production
deployment requires no database setup — Render connects to the same cloud
instances already running. Zero migration at deploy time.

---

## 10. Endpoints

### Phase 1
- POST /api/v1/ingest — sync in production, async (Celery) in development
- POST /api/v1/query — hybrid search + semantic cache + Groq answer

### Phase 2
- GET /api/v1/ingest/{job_id}/status?repo_id=X — polls Postgres

### Phase 3
- POST /api/v2/query — streaming SSE response

### Health
- GET /health — returns status and env

---

## 11. Complete Tech Stack

### Backend
| Tool | Purpose | Phase | Status |
|---|---|---|---|
| FastAPI | API framework | 1 | ✅ active |
| SQLAlchemy 2.0 async | ORM | 1 | ✅ active |
| asyncpg | Async Postgres driver | 1 | ✅ active |
| Alembic | Database migrations | 1 | ✅ active |
| pgvector | Vector similarity search | 1 | ✅ active |
| Cohere API | Embeddings (embed-english-light-v3.0, 384-dim) | 5 | ✅ active |
| Groq API | LLM calls (llama-3.1-8b-instant) | 1 | ✅ active |
| gitpython | Clone repositories | 1 | ✅ active |
| tree-sitter | AST chunking | 2 | ✅ active |
| rank-bm25 | BM25 keyword search | 2 | ✅ active |
| celery | Background task queue | 2 | ✅ dev only |
| redis | Celery broker (Upstash in prod) | 2 | ✅ active |
| structlog | Structured logging | 1 | ✅ active |
| pydantic-settings | Config from env vars | 1 | ✅ active |
| httpx | HTTP client (Cohere API calls) | 5 | ✅ active |
| uv | Package manager | 1 | ✅ active |
| sentence-transformers | Embeddings (local) | 1 | ❌ removed — OOM |
| CrossEncoder | Reranking (local) | 3 | ⏸ disabled prod |

### Frontend
| Tool | Purpose | Phase |
|---|---|---|
| React 19 | UI framework | 3 |
| Vite 8 | Dev server and build | 3 |
| React Router 7 | Navigation | 3 |
| Inter (Google Fonts) | UI typography | 5 |
| JetBrains Mono | Terminal/code typography | 3 |

### Infrastructure
| Service | Purpose | Cost |
|---|---|---|
| Neon | Cloud Postgres + pgvector | Free |
| Upstash | Cloud Redis (TLS) | Free |
| Render | App hosting (Docker) | Free |
| Cohere | Embeddings API | Free trial |
| Groq | LLM API | Free tier |
| GitHub | Code hosting | Free |

---

## 12. Architecture Decisions

Decision 1: Async throughout — bottleneck is I/O not CPU

Decision 2: Layered architecture — api/ core/ db/ separation

Decision 3: Repository pattern — all SQL in db/repositories/

Decision 4: Config from environment variables only — 12-factor app

Decision 5: API versioned from day one — /api/v1/ and /api/v2/

Decision 6: Same embedding model for ingestion and query
Changing the model requires full re-indexing of all repos.

Decision 7: Temp directory over object storage
Object storage solves distribution across machines. We run on one machine.

Decision 8: Index source code + docs + config
Answers to "how do I set up locally?" live in README not source code.

Decision 9: Model loaded as lazy singleton
Load on first use not at import time.
Critical for Render free tier (512MB RAM limit).

Decision 10: Idempotent ingest endpoint
Re-ingest deletes old chunks via ON DELETE CASCADE then re-indexes.

Decision 11: Python over Go or Rust
Bottleneck is I/O. ML ecosystem is Python. Correct at this scale.

Decision 12: Monolith over microservices
Solves a distribution problem we do not have.

Decision 13: Celery result backend unreliable for final state
Status endpoint reads from Postgres repos table instead.

Decision 14: React + Vite over single HTML file
Better state management for streaming. Builds to static/ for production.

Decision 15: Neon + Upstash over local Docker
Eliminates Docker Desktop overhead. Laptop runs cooler.
Same cloud services used in production — zero migration at deploy time.

Decision 16: Disable reranker in production (Render free tier)
Cross-encoder + FastAPI exceeds 512MB RAM on startup.
ENABLE_RERANKING=false in production. Re-enable on paid tier.
Reranker also fails gracefully — ImportError returns None instead of crashing,
so even if the env var is misconfigured the search still works.

Decision 17: Synchronous ingest fallback in production
Render free tier has no background worker support.
APP_ENV=production triggers synchronous ingestion path.
Celery async used in development only.

Decision 18: Cohere HTTP API over local embedding models
sentence-transformers loads PyTorch (~400MB) — OOM on 512MB Render instance.
Cohere embed-english-light-v3.0 produces identical 384-dim vectors via HTTP.
Free trial key sufficient for a portfolio project.
Rate limit handling: 2s inter-batch delay + exponential backoff on 429.
Downside: ingestion requires internet connectivity and a Cohere API key.

Decision 19: Professional UI with standard design system
Replaced amber/brown palette and macOS-style decorations with a neutral
zinc + indigo design system (Inter font, standard cards/chips/badges).
Goal: look like a real tool, not a side project.

---

## 13. Database Schema

```sql
-- repos: tracks indexed repositories
CREATE TABLE repos (
    id UUID PRIMARY KEY,
    repo_id TEXT UNIQUE NOT NULL,
    repo_url TEXT NOT NULL,
    status TEXT NOT NULL,           -- cloning | walking | chunking | embedding | storing | completed | failed
    files_processed INTEGER DEFAULT 0,
    chunks_created INTEGER DEFAULT 0,
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- chunks: code chunks with embeddings
CREATE TABLE chunks (
    id UUID PRIMARY KEY,
    repo_id TEXT NOT NULL REFERENCES repos(repo_id) ON DELETE CASCADE,
    file_path TEXT NOT NULL,
    start_line INTEGER NOT NULL,
    end_line INTEGER NOT NULL,
    content TEXT NOT NULL,
    embedding VECTOR(384) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX chunks_embedding_idx ON chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX chunks_repo_id_idx ON chunks (repo_id);

-- file_imports: dependency graph adjacency list
CREATE TABLE file_imports (
    id UUID PRIMARY KEY,
    repo_id TEXT NOT NULL REFERENCES repos(repo_id) ON DELETE CASCADE,
    source_file TEXT NOT NULL,
    imported_file TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- cache_entries: semantic cache for repeated/similar questions
CREATE TABLE cache_entries (
    id UUID PRIMARY KEY,
    repo_id TEXT NOT NULL REFERENCES repos(repo_id) ON DELETE CASCADE,
    question_embedding VECTOR(384) NOT NULL,
    question_text TEXT NOT NULL,
    answer TEXT NOT NULL,
    sources TEXT NOT NULL,          -- JSON serialized
    hit_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT now(),
    expires_at TIMESTAMPTZ NOT NULL
);
```

---

## 14. Environment Variables

```bash
# Database — Neon cloud Postgres
DATABASE_URL=postgresql+asyncpg://user:pass@host/neondb?sslmode=require

# Redis — Upstash cloud Redis (TLS required — rediss:// not redis://)
REDIS_URL=rediss://default:token@host:6379
CELERY_BROKER_URL=rediss://default:token@host:6379
CELERY_RESULT_BACKEND=rediss://default:token@host:6379

# LLM
GROQ_API_KEY=your_key_here
GROQ_MODEL=llama-3.1-8b-instant

# Embeddings — Cohere HTTP API (replaces local sentence-transformers)
COHERE_API_KEY=your_key_here

# App
APP_ENV=development          # development | production
LOG_LEVEL=INFO
MAX_FILE_SIZE_MB=1
CHUNK_SIZE_LINES=40
CHUNK_OVERLAP_LINES=5
ENABLE_RERANKING=false       # false in production (RAM limit), true only if >512MB available
```

---

## 15. Folder Structure

```
codesync/
├── app/
│   ├── api/
│   │   ├── routes/
│   │   │   ├── ingest.py        ✅ sync (prod) + async/Celery (dev)
│   │   │   ├── query.py         ✅ v1 + semantic cache
│   │   │   └── query_v2.py      ✅ v2 SSE streaming
│   │   └── dependencies.py
│   ├── core/
│   │   ├── ingestion/
│   │   │   ├── cloner.py        ✅ clean error messages
│   │   │   ├── file_walker.py   ✅ skips .agents .github node_modules
│   │   │   ├── chunker.py       ✅ tree-sitter AST + line fallback
│   │   │   ├── embedder.py      ✅ Cohere HTTP API, retry + backoff
│   │   │   ├── import_parser.py ✅ Python AST dependency graph
│   │   │   └── tasks.py         ✅ Celery (dev only)
│   │   ├── retrieval/
│   │   │   ├── searcher.py      ✅ hybrid BM25+vector+RRF, graceful reranker
│   │   │   └── generator.py     ✅ sync + streaming Groq
│   │   └── cache.py             ✅ pgvector semantic cache
│   ├── db/
│   │   ├── models.py            ✅ repos chunks file_imports cache_entries
│   │   ├── session.py           ✅ async connection pool
│   │   └── repositories/
│   │       └── chunks.py        ✅ all SQL here
│   ├── config.py                ✅ enable_reranking defaults False
│   └── main.py                  ✅ static serving + lifespan migrations
├── frontend/
│   ├── src/
│   │   ├── App.jsx              ✅ clean header, simple nav, persistent state
│   │   ├── index.css            ✅ Inter font, zinc/indigo design tokens
│   │   ├── api/codesync.js      ✅
│   │   └── components/
│   │       ├── IngestPage.jsx   ✅ clean cards, pipeline stepper, terminal
│   │       ├── QueryPage.jsx    ✅ streaming answer, sources sidebar
│   │       └── styles.css       ✅ professional component library
│   ├── vite.config.js
│   └── package.json
├── static/                      ✅ built React (committed, served in production)
├── alembic/versions/            ✅ 4 migrations
│   ├── 985e6970_create_repos_and_chunks_tables.py
│   ├── 9ff893b2_add_file_imports_table.py
│   ├── 92ac5b8f_add_cache_entries_table.py
│   └── cf4fa4ee_add_error_message_to_repos.py
├── Dockerfile                   ✅
├── render.yaml                  ✅
├── pyproject.toml               ✅
├── uv.lock                      ✅ committed
├── .env.example                 ✅ no real keys
└── README.md                    ✅ live URL, Cohere stack, clean setup guide
```

---

## 16. Dev Session Startup

```bash
# Terminal 1 — API server
uv run uvicorn app.main:app --reload --port 8000

# Terminal 2 — Celery worker (development only — not needed in production)
uv run celery -A app.core.ingestion.tasks.celery_app worker --loglevel=info --pool=solo

# Terminal 3 — Frontend
cd frontend && npm run dev
```

No docker-compose needed. Neon and Upstash run in the cloud.
Open http://localhost:5173

---

## 17. Current Production State

| Component | Status | Notes |
|---|---|---|
| Live URL | ✅ https://codesync-cee8.onrender.com | Render free tier |
| Ingest endpoint | ✅ working | Synchronous, ~8–10 min for large repos |
| Query endpoint | ✅ working | Hybrid BM25+vector, streaming SSE |
| Semantic cache | ✅ working | ~50ms hit vs ~4s miss |
| Embeddings | ✅ Cohere API | Free trial key, rate-limited |
| Reranking | ⏸ disabled | ENABLE_RERANKING=false, RAM limit |
| Celery worker | ❌ not deployed | Free tier limitation |
| Cold start | ⚠ 30–60s | Render spins down after 15min idle |
| Rate limiting | ❌ not built | API keys unprotected |

---

## 18. Known Limitations

**Cold starts**
Render free tier spins the container down after 15 minutes of inactivity.
First request after idle takes 30–60 seconds. Subsequent requests are fast.

**Slow ingestion on free Cohere key**
~30 embed calls/minute. Large repos (10,000+ chunks) take 8–10 minutes.
Pipeline retries automatically on 429s and waits for Retry-After header.

**Ingestion blocks the web process in production**
No Celery worker on Render free tier. Ingestion runs synchronously.
The browser tab must stay open. The server continues if the tab closes,
but the UI won't receive the completion event.

**No cross-encoder reranking in production**
ms-marco-MiniLM needs ~400MB RAM. Disabled to stay under 512MB limit.
Search quality is still good (BM25 + vector + RRF) but lacks the final
precision pass. Re-enable on a 1GB+ instance.

**Import graph is Python-only**
Dependency graph expansion uses Python's ast module. JS/TS/Go repos are
indexed and searchable but get no import-chain context in answers.

**No API rate limiting**
Anyone with the URL can exhaust the Groq and Cohere free-tier keys.

**Public repos only**
GitHub PAT support not yet implemented.

**BM25 cache is per-process**
In-memory, rebuilt on first query per process. Multiple workers would
have inconsistent indexes. Not an issue on single-worker free tier.

---

## 19. RAG Advancements — Evaluation Log

### Pinecone DB — Not adopting
pgvector handles our scale with zero cost. Switching adds vendor
dependency for no measurable benefit at 12,614 chunks.
Interview answer: "I chose pgvector deliberately. I'd evaluate Pinecone
at 10M+ vectors or if I needed a managed service without a Postgres dependency."

### LLM-based Chunking — Not adopting
tree-sitter gives semantically meaningful splits at zero cost.
LLM chunking costs money per chunk, is 10x slower, non-deterministic.

### sentence-transformers (local embedding) — Removed
Originally used all-MiniLM-L6-v2. OOM'd on Render 512MB free tier.
Replaced with Cohere HTTP API. Same 384-dim output. Zero RAM overhead.
Interview answer: "I evaluated the tradeoff — local models give you
independence from API providers, but at this scale the RAM cost outweighs
the benefit. I'd bring them back on a paid instance with more memory."

### HyDE (Hypothetical Document Embeddings) — HIGH PRIORITY, Phase 6
Generate a hypothetical answer to the question, embed that instead of
the raw question. Hypothesis: answer embeddings are geometrically closer
to real answer chunks than question embeddings are.
~20 lines in searcher.py. One extra Groq call per query.
Strong differentiator — very few junior candidates know about this.

### Hierarchical Index — HIGH PRIORITY, Phase 6
Directory → file → chunk three-level index.
New table: file_summaries. LLM generates one-paragraph summary per file
at ingest time. Query first narrows to relevant files, then retrieves chunks.
Greptile uses this approach for large codebases.

### Multi-query Retrieval — Phase 6
Generate 3 question variants, retrieve for each, merge with deduplication.
Low effort, good recall improvement for ambiguous questions.

### Query Decomposition — Future
Break compound questions into sub-questions, retrieve for each separately.

### Cross-encoder Reranking — Re-enable on paid tier
Already implemented (searcher.py). Set ENABLE_RERANKING=true.
Requires >512MB RAM. Render Starter plan is $7/month, 1GB RAM.

---

## 20. Phase 6 — Priority Order

1. **HyDE** — lowest effort, highest interview value, next improvement
2. **Hierarchical index** — solves large repo navigation, Greptile-level feature
3. **Rate limiting** — Redis token buckets, protects API keys in production
4. **Circuit breaker** — Groq → Gemini failover, removes LLM single point of failure
5. **Re-enable reranking** — upgrade Render tier to 1GB, set ENABLE_RERANKING=true
6. **BM25 cache to Redis** — consistency across workers, low priority at free tier
7. **Private repo support** — GitHub PAT, ~10 lines in cloner.py
8. **Architecture diagram** — visual for README and portfolio
9. **Demo GIF in README** — record 20s clip: index repo → stream a query answer

---

## 21. Change Log

| Version | Change |
|---|---|
| 1.0 | Initial specification |
| 1.1 | File walker expanded to include docs and config files |
| 1.2 | Decision 7: temp directory over GCS/S3 |
| 2.0 | Complete rewrite — all phases, tech stack, decisions |
| 3.0 | Phase 1 complete. Phase 2 defined. |
| 4.0 | Phase 2 complete. Phase 3 active. React+Vite decision. |
| 5.0 | Phase 3 complete. Phase 4 partial (semantic cache). Phase 5 active. |
|     | Infrastructure: Neon + Upstash replacing Docker. |
|     | Decisions 15–17 added. |
| 6.0 | Phase 5 complete. Live at https://codesync-cee8.onrender.com |
|     | Embedding backend: sentence-transformers → Cohere HTTP API (OOM fix) |
|     | Reranker made fail-safe (graceful ImportError handling) |
|     | UI redesigned: Inter font, zinc/indigo palette, professional components |
|     | README rewritten: live URL, Cohere stack, no-Docker setup |
|     | Phase 6 defined with priority order |
|     | Decisions 18–19 added |
|     | Current production state table added |
|     | Known limitations updated to reflect live deployment |
