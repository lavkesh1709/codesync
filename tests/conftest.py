import os

# Set required env vars before any app module is imported.
# Unit tests don't touch the database or external APIs, but pydantic-settings
# validates these fields at import time, so we provide dummy values here.
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/codesync_test")
os.environ.setdefault("GROQ_API_KEY", "ci-test-key")
os.environ.setdefault("COHERE_API_KEY", "ci-test-key")
