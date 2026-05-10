import structlog
from celery.result import AsyncResult
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ingestion.tasks import celery_app, ingest_repo_task
from app.db.session import get_db

log = structlog.get_logger()

router = APIRouter()


class IngestRequest(BaseModel):
    repo_url: str
    repo_id: str


class IngestResponse(BaseModel):
    job_id: str
    repo_id: str
    status: str
    message: str


class StatusResponse(BaseModel):
    job_id: str
    repo_id: str
    status: str
    step: str | None = None
    files_processed: int | None = None
    chunks_created: int | None = None
    duration_seconds: float | None = None
    error: str | None = None


@router.post("/ingest", response_model=IngestResponse)
async def ingest(
    request: IngestRequest,
    db: AsyncSession = Depends(get_db),
) -> IngestResponse:
    """
    Queue a repository for ingestion.
    Returns a job_id immediately — use /ingest/{job_id}/status to poll.
    """
    log.info("ingest_queued", repo_id=request.repo_id, repo_url=request.repo_url)

    task = ingest_repo_task.delay(request.repo_url, request.repo_id)

    return IngestResponse(
        job_id=task.id,
        repo_id=request.repo_id,
        status="queued",
        message="Ingestion queued. Poll /api/v1/ingest/{job_id}/status for progress.",
    )


@router.get("/ingest/{job_id}/status", response_model=StatusResponse)
async def ingest_status(
    job_id: str,
    repo_id: str,
    db: AsyncSession = Depends(get_db),
) -> StatusResponse:
    """
    Poll the status of an ingestion job.
    Checks Celery for live progress, falls back to DB for final state.
    """
    from app.db.repositories.chunks import get_repo

    # Check Celery result first for live progress updates
    result = AsyncResult(job_id, app=celery_app)

    if result.state == "PROGRESS":
        meta = result.info or {}
        return StatusResponse(
            job_id=job_id,
            repo_id=repo_id,
            status="processing",
            step=meta.get("step"),
        )
        
    # If Celery explicitly failed, grab the exception message
    if result.state == "FAILURE":
        return StatusResponse(
            job_id=job_id,
            repo_id=repo_id,
            status="failed",
            error=str(result.result)  # Celery stores the exception in .result
        )

    # Fall back to database — always accurate for completed/failed
    repo = await get_repo(db, repo_id)
    if repo is None:
        return StatusResponse(job_id=job_id, repo_id=repo_id, status="queued")

    return StatusResponse(
        job_id=job_id,
        repo_id=repo_id,
        status=repo.status,
        files_processed=repo.files_processed,
        chunks_created=repo.chunks_created,
    )