import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ingestion.pipeline import run_ingestion
from app.db.repositories.chunks import get_repo
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
    background_tasks: BackgroundTasks,
) -> IngestResponse:
    """
    Queue a repository for ingestion.
    Ingestion runs as a background task in the same process —
    no Celery worker required. Poll /ingest/{repo_id}/status for progress.
    """
    log.info("ingest_queued", repo_id=request.repo_id, repo_url=request.repo_url)
    background_tasks.add_task(run_ingestion, request.repo_url, request.repo_id)
    return IngestResponse(
        job_id=request.repo_id,
        repo_id=request.repo_id,
        status="queued",
        message="Ingestion started. Poll /api/v1/ingest/{repo_id}/status for progress.",
    )


@router.get("/ingest/{job_id}/status", response_model=StatusResponse)
async def ingest_status(
    job_id: str,
    repo_id: str,
    db: AsyncSession = Depends(get_db),
) -> StatusResponse:
    """
    Poll the status of an ingestion job.
    Status is read directly from the database — updated at each pipeline step.
    """
    repo = await get_repo(db, repo_id)
    if repo is None:
        return StatusResponse(job_id=job_id, repo_id=repo_id, status="queued")

    return StatusResponse(
        job_id=job_id,
        repo_id=repo_id,
        status=repo.status,
        files_processed=repo.files_processed,
        chunks_created=repo.chunks_created,
        error=repo.error_message,
    )
