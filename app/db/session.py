from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

# Create the async engine — one per application lifetime
# pool_pre_ping=True means SQLAlchemy checks the connection
# is alive before using it — handles database restarts gracefully
engine = create_async_engine(
    settings.database_url,
    pool_pre_ping=True,
    echo=settings.is_development,  # logs all SQL in development only
)

# Session factory — creates new sessions from the engine
# expire_on_commit=False means objects stay usable after commit
# without this you'd get DetachedInstanceError when accessing
# attributes after a commit
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency — yields a database session per request.
    Automatically closes the session when the request finishes.
    Used as: db: AsyncSession = Depends(get_db)
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise