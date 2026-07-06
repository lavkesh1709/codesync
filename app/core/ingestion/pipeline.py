import asyncio
import time

import structlog

from app.config import settings
from app.db.session import AsyncSessionLocal

log = structlog.get_logger()


async def run_ingestion(repo_url: str, repo_id: str) -> None:
    """
    Full ingestion pipeline as an async function.
    Runs as a FastAPI BackgroundTask — no Celery worker required.

    Status is written to the database at each step so the
    /ingest/{repo_id}/status endpoint can report live progress.
    """
    from app.db.repositories.chunks import (
        delete_repo,
        insert_repo,
        update_repo,
    )

    start = time.monotonic()

    async def set_status(status: str, **extra) -> None:
        async with AsyncSessionLocal() as db:
            await update_repo(db, repo_id, status=status, **extra)
            await db.commit()

    # Reset any previous state for this repo
    async with AsyncSessionLocal() as db:
        await delete_repo(db, repo_id)
        await insert_repo(db, repo_id, repo_url)
        await db.commit()

    files_processed = 0
    chunks_created = 0
    repo_path = None
    try:
        # Imports deferred inside try so any ImportError is caught and stored
        from app.core.ingestion.chunker import chunk_files
        from app.core.ingestion.cloner import cleanup_repo, clone_repo
        from app.core.ingestion.embedder import embed_chunks
        from app.core.ingestion.file_walker import walk_files
        from app.core.ingestion.import_parser import parse_all_imports
        from app.core.retrieval.searcher import invalidate_bm25_cache
        from app.db.repositories.chunks import insert_chunks, insert_file_imports
        from app.core.cache import invalidate_cache

        await set_status("cloning")
        repo_path = await clone_repo(repo_url, repo_id)

        await set_status("walking")
        files = walk_files(repo_path, settings.max_file_size_mb)
        files_processed = len(files)

        await set_status("chunking")
        chunks = chunk_files(
            files,
            chunk_size=settings.chunk_size_lines,
            overlap=settings.chunk_overlap_lines,
        )

        await set_status("embedding", files_processed=files_processed)

        # Embed and store in batches so a failure partway through a long run
        # (large repos need 100+ Cohere calls) keeps everything embedded so
        # far instead of discarding it. embed_chunks is sync and CPU-bound —
        # run each batch in a thread pool so the event loop stays responsive.
        EMBED_BATCH_SIZE = 200
        loop = asyncio.get_event_loop()

        for batch_start in range(0, len(chunks), EMBED_BATCH_SIZE):
            batch = chunks[batch_start : batch_start + EMBED_BATCH_SIZE]
            embedded_batch = await loop.run_in_executor(None, embed_chunks, batch)

            async with AsyncSessionLocal() as db:
                chunks_created += await insert_chunks(db, repo_id, embedded_batch)
                await update_repo(
                    db,
                    repo_id,
                    status="embedding",
                    files_processed=files_processed,
                    chunks_created=chunks_created,
                )
                await db.commit()

        adjacency = parse_all_imports(files, repo_path)
        async with AsyncSessionLocal() as db:
            await insert_file_imports(db, repo_id, adjacency)
            await update_repo(
                db,
                repo_id,
                status="completed",
                files_processed=len(files),
                chunks_created=chunks_created,
            )
            await db.commit()

        invalidate_bm25_cache(repo_id)

        async with AsyncSessionLocal() as db:
            await invalidate_cache(db, repo_id)

        duration = round(time.monotonic() - start, 2)
        log.info(
            "ingest_complete",
            repo_id=repo_id,
            chunks=chunks_created,
            duration_seconds=duration,
        )

    except Exception as e:
        error_msg = str(e)
        if len(error_msg) > 500:
            error_msg = error_msg[:500] + " ... [truncated]"
        log.error("ingest_failed", repo_id=repo_id, error=error_msg)
        async with AsyncSessionLocal() as db:
            await update_repo(
                db,
                repo_id,
                status="failed",
                files_processed=files_processed,
                chunks_created=chunks_created,
                error_message=error_msg,
            )
            await db.commit()

    finally:
        if repo_path is not None:
            try:
                from app.core.ingestion.cloner import cleanup_repo
                cleanup_repo(repo_path)
            except Exception:
                pass
