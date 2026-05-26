import asyncio
import ssl
import time

import structlog
from celery import Celery

from app.config import settings
from app.core.cache import invalidate_cache
from app.db.session import AsyncSessionLocal


log = structlog.get_logger()

# Create Celery app
# broker: where tasks are queued (Redis)
# backend: where results are stored (Redis)
celery_app = Celery(
    "codesync",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_config = {
    "task_serializer": "json",
    "result_serializer": "json",
    "accept_content": ["json"],
    "task_track_started": True,   # lets us see "started" status
    "result_expires": 3600,       # results expire after 1 hour
}

# Handle secure Redis connections (like Upstash)
if settings.celery_broker_url.startswith("rediss://"):
    celery_config["broker_use_ssl"] = {"ssl_cert_reqs": ssl.CERT_NONE}
    celery_config["redis_backend_use_ssl"] = {"ssl_cert_reqs": ssl.CERT_NONE}

celery_app.conf.update(**celery_config)


@celery_app.task(bind=True, name="ingest_repo")
def ingest_repo_task(self, repo_url: str, repo_id: str) -> dict:
    """
    Celery task that runs the full ingestion pipeline.
    Runs in a worker process, not in the API process.

    bind=True gives us access to self — the task instance.
    We use self.update_state() to report progress.
    """
    from app.core.ingestion.chunker import chunk_files
    from app.core.ingestion.cloner import cleanup_repo, clone_repo
    from app.core.ingestion.embedder import embed_chunks
    from app.core.ingestion.file_walker import walk_files
    from app.core.retrieval.searcher import invalidate_bm25_cache
    from app.db.repositories.chunks import (
        delete_repo,
        insert_chunks,
        insert_repo,
        update_repo,
    )
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from app.config import settings

    # Celery tasks are sync — we run async code with asyncio.run()
    async def _run():
        # Create a completely fresh engine for this task's event loop
        # This prevents asyncio Lock/Queue corruption across multiple task runs
        task_engine = create_async_engine(settings.database_url, pool_pre_ping=True)
        TaskSessionLocal = async_sessionmaker(task_engine, expire_on_commit=False)

        start = time.monotonic()

        async with TaskSessionLocal() as db:
            # Idempotency — delete existing data
            await delete_repo(db, repo_id)
            await insert_repo(db, repo_id, repo_url)
            await db.commit()

        repo_path = None
        try:
            self.update_state(state="PROGRESS", meta={"step": "cloning"})
            repo_path = await clone_repo(repo_url, repo_id)

            self.update_state(state="PROGRESS", meta={"step": "walking"})
            files = walk_files(repo_path, settings.max_file_size_mb)

            self.update_state(state="PROGRESS", meta={"step": "chunking"})
            chunks = chunk_files(
                files,
                chunk_size=settings.chunk_size_lines,
                overlap=settings.chunk_overlap_lines,
            )

            self.update_state(state="PROGRESS", meta={"step": "embedding"})
            embedded = embed_chunks(chunks)

            self.update_state(state="PROGRESS", meta={"step": "storing"})
            async with TaskSessionLocal() as db:
                chunks_created = await insert_chunks(db, repo_id, embedded)
                await db.commit()

            self.update_state(state="PROGRESS", meta={"step": "parsing_imports"})
            from app.core.ingestion.import_parser import parse_all_imports
            from app.db.repositories.chunks import insert_file_imports

            adjacency = parse_all_imports(files, repo_path)
            async with TaskSessionLocal() as db:
                imports_stored = await insert_file_imports(db, repo_id, adjacency)
                await update_repo(
                    db,
                    repo_id,
                    status="completed",
                    files_processed=len(files),
                    chunks_created=chunks_created,
                )
                await db.commit()

            log.info(
                "import_graph_stored",
                repo_id=repo_id,
                import_relationships=imports_stored,
            )

            invalidate_bm25_cache(repo_id)

            # Invalidate semantic cache — old answers may be wrong after re-index
            async with AsyncSessionLocal() as db:
                await invalidate_cache(db, repo_id)

            duration = round(time.monotonic() - start, 2)
            log.info(
                "ingest_task_complete",
                repo_id=repo_id,
                chunks=chunks_created,
                duration_seconds=duration,
            )

            return {
                "repo_id": repo_id,
                "status": "completed",
                "files_processed": len(files),
                "chunks_created": chunks_created,
                "duration_seconds": duration,
            }

        except Exception as e:
            async with TaskSessionLocal() as db:
                await update_repo(db, repo_id, status="failed")
                await db.commit()
            
            # Truncate the error message so it doesn't send 8MB of chunk data to the UI
            error_msg = str(e)
            if len(error_msg) > 500:
                error_msg = error_msg[:500] + " ... [error truncated]"
                
            log.error("ingest_task_failed", repo_id=repo_id, error=error_msg)
            raise ValueError(f"Pipeline error: {error_msg}")

        finally:
            if repo_path is not None:
                cleanup_repo(repo_path)
                
            # Safely dispose of this task's specific engine
            await task_engine.dispose()

    return asyncio.run(_run())