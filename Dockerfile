# Use Python 3.11 slim — smaller image than full Python
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
# git: for cloning repos during ingestion
# build-essential: for compiling some Python packages
RUN apt-get update && apt-get install -y \
    git \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files first (better Docker layer caching)
COPY pyproject.toml .
COPY uv.lock .

# Install Python dependencies
RUN uv sync --frozen --no-dev

# Fix cache path so build-time download and runtime both use the same location.
# Without this fastembed defaults to ~/.cache/fastembed/ which can resolve differently
# between build and runtime, causing a re-download on the 512MB Render instance (OOM).
ENV FASTEMBED_CACHE_PATH=/app/.fastembed_cache

# Pre-download the fastembed model during build so it's baked into the image.
# This avoids a ~130MB download at runtime on a 512MB instance (which causes OOM).
RUN uv run python3 -c "from fastembed import TextEmbedding; TextEmbedding('BAAI/bge-small-en-v1.5')"

# Copy application code
COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini .
COPY static/ ./static/

# Expose port
EXPOSE 8000

# Start command — uvicorn
CMD ["sh", "-c", "uv run uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]