import time

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ingestion.chunker import chunk_files
from app.core.ingestion.cloner import cleanup_repo, clone_repo
from app.core.ingestion.embedder import embed_chunks
from app.core.ingestion.file_walker import walk_files
from app.db.repositories.chunks import (
    delete_repo,
    insert_chunks,
    insert_repo,
    update_repo,
)
from app.db.session import get_db
from app.config import settings

log = structlog.get_logger()

router = APIRouter()


class IngestRequest(BaseModel):
    repo_url: str
    repo_id: str


class IngestResponse(BaseModel):
    repo_id: str
    status: str
    files_processed: int
    chunks_created: int
    duration_seconds: float


@router.post("/ingest", response_model=IngestResponse)
async def ingest(
    request: IngestRequest,
    db: AsyncSession = Depends(get_db),
) -> IngestResponse:
    """
    Clone a repository, chunk it, embed it, and store in Postgres.

    Idempotent: if repo_id already exists, old data is deleted first.
    The API waits until indexing is complete before responding (phase 1).
    Phase 2 will make this async with a job_id pattern.
    """
    start = time.monotonic()
    log.info("ingest_request", repo_id=request.repo_id, repo_url=request.repo_url)

    # Idempotency — delete existing data for this repo_id before re-indexing
    # ON DELETE CASCADE in the schema removes all chunks automatically
    await delete_repo(db, request.repo_id)

    # Create repo record with status 'indexing'
    await insert_repo(db, request.repo_id, request.repo_url)

    repo_path = None
    try:
        # Step 1 — Clone
        repo_path = await clone_repo(request.repo_url, request.repo_id)

        # Step 2 — Walk files
        files = walk_files(repo_path, settings.max_file_size_mb)

        # Step 3 — Chunk
        chunks = chunk_files(
            files,
            chunk_size=settings.chunk_size_lines,
            overlap=settings.chunk_overlap_lines,
        )

        # Step 4 — Embed
        embedded = embed_chunks(chunks)

        # Step 5 — Store
        chunks_created = await insert_chunks(db, request.repo_id, embedded)

        # Update repo record to completed
        await update_repo(
            db,
            request.repo_id,
            status="completed",
            files_processed=len(files),
            chunks_created=chunks_created,
        )

        duration = round(time.monotonic() - start, 2)
        log.info(
            "ingest_complete",
            repo_id=request.repo_id,
            files=len(files),
            chunks=chunks_created,
            duration_seconds=duration,
        )

        return IngestResponse(
            repo_id=request.repo_id,
            status="completed",
            files_processed=len(files),
            chunks_created=chunks_created,
            duration_seconds=duration,
        )

    except Exception as e:
        # Mark repo as failed so the user knows something went wrong
        await update_repo(db, request.repo_id, status="failed")
        log.error("ingest_failed", repo_id=request.repo_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        # Always clean up the temp clone — even if something failed
        if repo_path is not None:
            cleanup_repo(repo_path)