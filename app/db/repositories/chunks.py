import uuid
from collections.abc import Sequence

from pgvector.sqlalchemy import Vector
from sqlalchemy import delete, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Chunk, Repo


async def insert_repo(
    db: AsyncSession,
    repo_id: str,
    repo_url: str,
) -> Repo:
    """
    Create a new repo record with status 'indexing'.
    Called at the start of ingestion.
    """
    repo = Repo(
        repo_id=repo_id,
        repo_url=repo_url,
        status="indexing",
    )
    db.add(repo)
    await db.flush()  # sends INSERT to DB but doesn't commit yet
    return repo


async def update_repo(
    db: AsyncSession,
    repo_id: str,
    status: str,
    files_processed: int = 0,
    chunks_created: int = 0,
) -> None:
    """
    Update repo status and counts after ingestion completes or fails.
    """
    stmt = (
        update(Repo)
        .where(Repo.repo_id == repo_id)
        .values(
            status=status,
            files_processed=files_processed,
            chunks_created=chunks_created,
        )
    )
    await db.execute(stmt)


async def insert_chunks(
    db: AsyncSession,
    repo_id: str,
    chunks: list[dict],
) -> int:
    """
    Bulk insert all chunks for a repo in one database round trip.
    Each chunk dict must have: file_path, start_line, end_line,
    content, embedding.
    Returns the number of chunks inserted.
    """
    chunk_objects = [
        Chunk(
            id=uuid.uuid4(),
            repo_id=repo_id,
            file_path=chunk["file_path"],
            start_line=chunk["start_line"],
            end_line=chunk["end_line"],
            content=chunk["content"],
            embedding=chunk["embedding"],
        )
        for chunk in chunks
    ]
    db.add_all(chunk_objects)
    await db.flush()
    return len(chunk_objects)


async def search_similar(
    db: AsyncSession,
    repo_id: str,
    query_embedding: list[float],
    top_k: int = 5,
) -> Sequence[Chunk]:
    """
    Find top_k chunks most similar to query_embedding using
    cosine similarity. Scoped to a specific repo_id so results
    never mix between different indexed repos.

    The <=> operator is pgvector's cosine distance operator.
    ORDER BY distance ASC means smallest distance = most similar.
    """
    stmt = (
        select(Chunk)
        .where(Chunk.repo_id == repo_id)
        .order_by(Chunk.embedding.op("<=>")(query_embedding))
        .limit(top_k)
    )
    result = await db.execute(stmt)
    return result.scalars().all()


async def delete_repo(
    db: AsyncSession,
    repo_id: str,
) -> bool:
    """
    Delete a repo record. Chunks cascade delete automatically
    because of ON DELETE CASCADE on the foreign key.
    Returns True if a repo was found and deleted, False if
    repo_id didn't exist.
    """
    stmt = delete(Repo).where(Repo.repo_id == repo_id)
    result = await db.execute(stmt)
    return result.rowcount > 0


async def get_repo(
    db: AsyncSession,
    repo_id: str,
) -> Repo | None:
    """
    Fetch a repo record by repo_id.
    Returns None if not found.
    Used by the query endpoint to verify the repo exists
    before attempting to search it.
    """
    stmt = select(Repo).where(Repo.repo_id == repo_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()