import json
import time

import structlog
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.retrieval.generator import generate_stream
from app.core.retrieval.searcher import search
from app.db.repositories.chunks import get_repo
from app.db.session import get_db

log = structlog.get_logger()

router = APIRouter()


class QueryV2Request(BaseModel):
    repo_id: str
    question: str
    top_k: int = 5


@router.post("/query")
async def query_stream(
    request: QueryV2Request,
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """
    Streaming query endpoint.
    Returns SSE stream — answer appears word by word.
    Sources sent as first SSE event, then answer tokens stream.
    """
    # Verify repo exists
    repo = await get_repo(db, request.repo_id)
    if repo is None:
        raise HTTPException(
            status_code=404,
            detail=f"repo_id '{request.repo_id}' not found.",
        )
    if repo.status != "completed":
        raise HTTPException(
            status_code=400,
            detail=f"repo '{request.repo_id}' status is '{repo.status}'.",
        )

    # Retrieve and rerank chunks
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

    # Build sources list for the client
    sources = [
        {
            "file": chunk.file_path,
            "start_line": chunk.start_line,
            "end_line": chunk.end_line,
        }
        for chunk in chunks
    ]

    async def event_stream():
        # First event — send sources so client can display them immediately
        yield f"data: {json.dumps({'type': 'sources', 'sources': sources})}\n\n"

        # Stream answer tokens
        async for token in generate_stream(request.question, chunks):
            yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"

        # Final event — signals stream is complete
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )