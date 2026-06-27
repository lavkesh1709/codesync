import time

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.retrieval.generator import generate
from app.core.retrieval.searcher import search
from app.db.repositories.chunks import get_repo
from app.db.session import get_db
from app.core.cache import get_cached_answer, store_cached_answer

log = structlog.get_logger()

router = APIRouter()


class QueryRequest(BaseModel):
    repo_id: str
    question: str
    top_k: int = 5


class SourceReference(BaseModel):
    file: str
    start_line: int
    end_line: int
    similarity_score: float


class QueryResponse(BaseModel):
    answer: str
    sources: list[SourceReference]
    latency_ms: int


@router.post("/query", response_model=QueryResponse)
async def query(
    request: QueryRequest,
    db: AsyncSession = Depends(get_db),
) -> QueryResponse:
    """
    Embed the question, check cache, find relevant chunks,
    call Groq, return answer.
    Returns 404 if the repo_id has not been indexed.
    """
    import time
    start = time.monotonic()
    log.info("query_request", repo_id=request.repo_id, question=request.question[:80])

    # Verify repo exists
    repo = await get_repo(db, request.repo_id)
    if repo is None:
        raise HTTPException(
            status_code=404,
            detail=f"repo_id '{request.repo_id}' not found. Run /ingest first.",
        )
    if repo.status != "completed":
        raise HTTPException(
            status_code=400,
            detail=f"repo '{request.repo_id}' has status '{repo.status}'.",
        )

    # Check semantic cache first
    cached = await get_cached_answer(db, request.repo_id, request.question)
    if cached:
        latency_ms = int((time.monotonic() - start) * 1000)
        log.info("query_served_from_cache", latency_ms=latency_ms)
        return QueryResponse(
            answer=cached["answer"],
            sources=[
                SourceReference(**s) for s in cached["sources"]
            ],
            latency_ms=latency_ms,
        )

    # Cache miss — run full pipeline
    try:
        chunks = await search(
            db=db,
            repo_id=request.repo_id,
            question=request.question,
            top_k=request.top_k,
        )
    except Exception as exc:
        log.error("search_error", error=str(exc), repo_id=request.repo_id)
        raise HTTPException(status_code=500, detail=f"Search failed: {exc}") from exc

    try:
        answer = await generate(question=request.question, chunks=chunks)
    except Exception as exc:
        log.error("generate_error", error=str(exc), repo_id=request.repo_id)
        raise HTTPException(status_code=500, detail=f"Generation failed: {exc}") from exc

    latency_ms = int((time.monotonic() - start) * 1000)

    sources = [
        SourceReference(
            file=chunk.file_path,
            start_line=chunk.start_line,
            end_line=chunk.end_line,
            similarity_score=0.0,
        )
        for chunk in chunks
    ]

    # Store in cache for future similar questions
    await store_cached_answer(
        db=db,
        repo_id=request.repo_id,
        question=request.question,
        answer=answer,
        sources=[s.model_dump() for s in sources],
    )

    log.info(
        "query_complete",
        repo_id=request.repo_id,
        latency_ms=latency_ms,
        sources_returned=len(sources),
    )

    return QueryResponse(
        answer=answer,
        sources=sources,
        latency_ms=latency_ms,
    )