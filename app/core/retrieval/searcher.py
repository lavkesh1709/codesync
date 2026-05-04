import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ingestion.embedder import embed_text
from app.db.repositories.chunks import search_similar
from app.db.models import Chunk

log = structlog.get_logger()


async def search(
    db: AsyncSession,
    repo_id: str,
    question: str,
    top_k: int = 5,
) -> list[Chunk]:
    """
    Embed the question and find top_k most similar chunks
    in the database for the given repo_id.

    This function bridges the ML layer (embedder) and the
    database layer (repository). It knows about both but
    neither layer knows about each other.
    """
    log.info("search_started", repo_id=repo_id, question=question[:80])

    # Embed the question into the same vector space as the chunks
    # CRITICAL: must use the same model used during ingestion
    # If the models differ, the vectors are incomparable
    query_embedding = embed_text(question)

    # Find top_k chunks whose embeddings are closest to the query
    chunks = await search_similar(
        db=db,
        repo_id=repo_id,
        query_embedding=query_embedding,
        top_k=top_k,
    )

    log.info(
        "search_complete",
        repo_id=repo_id,
        chunks_found=len(chunks),
    )

    return list(chunks)