import json
import uuid
from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import select, update, Float
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ingestion.embedder import embed_text
from app.db.models import CacheEntry

log = structlog.get_logger()

# Similarity threshold — questions must be this similar
# to return a cached answer. 0.92 = 92% similar.
# Too low: wrong answers returned from cache
# Too high: cache never hits
SIMILARITY_THRESHOLD = 0.92

# Cache TTL — answers expire after this many hours
CACHE_TTL_HOURS = 24


async def get_cached_answer(
    db: AsyncSession,
    repo_id: str,
    question: str,
) -> dict | None:
    """
    Check if a similar question has been answered before.
    Returns the cached response dict if found, None if miss.

    Flow:
        1. Embed the incoming question
        2. Search cache_entries for similar embeddings
        3. If similarity > threshold and not expired → cache hit
        4. Increment hit_count for analytics
    """
    query_embedding = embed_text(question)
    now = datetime.now(timezone.utc)

    # Find most similar cached question for this repo
    # Uses pgvector cosine distance operator <=>
    # ORDER BY distance ASC = most similar first
    stmt = (
        select(CacheEntry)
        .where(CacheEntry.repo_id == repo_id)
        .where(CacheEntry.expires_at > now)
        .order_by(CacheEntry.question_embedding.op("<=>")(query_embedding))
        .limit(1)
    )
    result = await db.execute(stmt)
    entry = result.scalar_one_or_none()

    if entry is None:
        log.info("cache_miss", repo_id=repo_id, reason="no_entries")
        return None

    # Calculate actual similarity score
    # pgvector <=> returns cosine DISTANCE (0=identical, 2=opposite)
    # Convert to similarity: 1 - distance
    # We fetch the distance separately for the threshold check
    dist_stmt = select(
        CacheEntry.question_embedding.op("<=>", return_type=Float)(query_embedding)
    ).where(CacheEntry.id == entry.id)
    dist_result = await db.execute(dist_stmt)
    distance = dist_result.scalar()
    similarity = 1 - distance

    if similarity < SIMILARITY_THRESHOLD:
        log.info(
            "cache_miss",
            repo_id=repo_id,
            similarity=round(similarity, 3),
            threshold=SIMILARITY_THRESHOLD,
        )
        return None

    # Cache hit — increment hit counter
    await db.execute(
        update(CacheEntry)
        .where(CacheEntry.id == entry.id)
        .values(hit_count=entry.hit_count + 1)
    )

    log.info(
        "cache_hit",
        repo_id=repo_id,
        similarity=round(similarity, 3),
        hit_count=entry.hit_count + 1,
        question=question[:80],
    )

    return {
        "answer": entry.answer,
        "sources": json.loads(entry.sources),
        "cached": True,
        "similarity_score": round(similarity, 3),
    }


async def store_cached_answer(
    db: AsyncSession,
    repo_id: str,
    question: str,
    answer: str,
    sources: list[dict],
) -> None:
    """
    Store a question-answer pair in the cache.
    Called after a successful query so future similar
    questions can be served from cache.
    """
    question_embedding = embed_text(question)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=CACHE_TTL_HOURS)

    entry = CacheEntry(
        id=uuid.uuid4(),
        repo_id=repo_id,
        question_embedding=question_embedding,
        question_text=question,
        answer=answer,
        sources=json.dumps(sources),
        hit_count=0,
        expires_at=expires_at,
    )
    db.add(entry)
    await db.flush()

    log.info(
        "cache_stored",
        repo_id=repo_id,
        question=question[:80],
        expires_at=expires_at.isoformat(),
    )


async def invalidate_cache(
    db: AsyncSession,
    repo_id: str,
) -> int:
    """
    Delete all cache entries for a repo.
    Called when a repo is re-ingested — old answers
    may no longer be accurate after re-indexing.
    """
    from sqlalchemy import delete

    stmt = delete(CacheEntry).where(CacheEntry.repo_id == repo_id)
    result = await db.execute(stmt)
    count = result.rowcount

    log.info("cache_invalidated", repo_id=repo_id, entries_deleted=count)
    return count