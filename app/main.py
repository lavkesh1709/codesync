import subprocess
import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.routing import APIRoute

from app.api.routes.ingest import router as ingest_router
from app.api.routes.query import router as query_router
from app.config import settings
from app.api.routes.query_v2 import router as query_v2_router



def custom_generate_unique_id(route: APIRoute) -> str:
    if route.tags:
        return f"{route.tags[0]}-{route.name}"
    return route.name


structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(),
    ]
)

log = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("running_migrations")
    subprocess.run(["uv", "run", "alembic", "upgrade", "head"], check=True)
    log.info("migrations_complete")
    yield


app = FastAPI(
    title="CodeSync",
    lifespan=lifespan,
    description="Self-hosted codebase intelligence — ask questions, get answers with file citations.",
    version="0.1.0",
    generate_unique_id_function=custom_generate_unique_id,
)

app.include_router(ingest_router, prefix="/api/v1", tags=["ingestion"])
app.include_router(query_router, prefix="/api/v1", tags=["retrieval"])
app.include_router(query_v2_router, prefix="/api/v2", tags=["retrieval-v2"])



@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "env": settings.app_env}


log.info("codesync_started", env=settings.app_env)

from fastapi.staticfiles import StaticFiles
import os

# Serve React frontend if static folder exists
if os.path.exists("static"):
    app.mount("/", StaticFiles(directory="static", html=True), name="static")