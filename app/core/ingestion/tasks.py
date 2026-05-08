import asyncio
import time

import structlog
from celery import Celery

from app.config import settings

log = structlog.get_logger()

# Create Celery app
# broker: where tasks are queued (Redis)
# backend: where results are stored (Redis)
celery_app = Celery(
    "codesync",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,   # lets us see "started" status
    result_expires=3600,       # results expire after 1 hour
)


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
    from app.db.session import AsyncSessionLocal
    from app.config import settings

    # Celery tasks are sync — we run async code with asyncio.run()
    async def _run():
        start = time.monotonic()

        async with AsyncSessionLocal() as db:
            # Idempotency — delete existing data
            await delete_repo(db, repo_id)
            await insert_repo(db, repo_id, repo_url)

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
            async with AsyncSessionLocal() as db:
                chunks_created = await insert_chunks(db, repo_id, embedded)

            self.update_state(state="PROGRESS", meta={"step": "parsing_imports"})
            from app.core.ingestion.import_parser import parse_all_imports
            from app.db.repositories.chunks import insert_file_imports

            adjacency = parse_all_imports(files, repo_path)
            async with AsyncSessionLocal() as db:
                imports_stored = await insert_file_imports(db, repo_id, adjacency)
                await update_repo(
                    db,
                    repo_id,
                    status="completed",
                    files_processed=len(files),
                    chunks_created=chunks_created,
                )

            log.info(
                "import_graph_stored",
                repo_id=repo_id,
                import_relationships=imports_stored,
            )

            invalidate_bm25_cache(repo_id)

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
            async with AsyncSessionLocal() as db:
                await update_repo(db, repo_id, status="failed")
            log.error("ingest_task_failed", repo_id=repo_id, error=str(e))
            raise

        finally:
            if repo_path is not None:
                cleanup_repo(repo_path)

    return asyncio.run(_run())