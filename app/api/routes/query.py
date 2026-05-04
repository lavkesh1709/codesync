import time

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.retrieval.generator import generate
from app.core.retrieval.searcher import search
from app.db.repositories.chunks import get_repo
from app.db.session import get_db

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
    Embed the question, find relevant chunks, call Groq, return answer.
    Returns 404 if the repo_id has not been indexed.
    """
    start = time.monotonic()
    log.info("query_request", repo_id=request.repo_id, question=request.question[:80])

    # Verify repo exists and was indexed successfully
    repo = await get_repo(db, request.repo_id)
    if repo is None:
        raise HTTPException(
            status_code=404,
            detail=f"repo_id '{request.repo_id}' not found. Run /ingest first.",
        )
    if repo.status != "completed":
        raise HTTPException(
            status_code=400,
            detail=f"repo '{request.repo_id}' has status '{repo.status}'. "
                   "Only completed repos can be queried.",
        )

    # Find relevant chunks via vector similarity search
    chunks = await search(
        db=db,
        repo_id=request.repo_id,
        question=request.question,
        top_k=request.top_k,
    )

    # Generate answer from retrieved chunks
    answer = await generate(question=request.question, chunks=chunks)

    latency_ms = int((time.monotonic() - start) * 1000)

    # Build source references from retrieved chunks
    # Similarity score is not returned by pgvector in this query yet —
    # we use a placeholder. Phase 3 will add proper score retrieval.
    sources = [
        SourceReference(
            file=chunk.file_path,
            start_line=chunk.start_line,
            end_line=chunk.end_line,
            similarity_score=0.0,  # phase 3: retrieve actual cosine score
        )
        for chunk in chunks
    ]

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