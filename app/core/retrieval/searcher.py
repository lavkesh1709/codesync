import structlog
from rank_bm25 import BM25Okapi
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ingestion.embedder import embed_text
from app.db.models import Chunk
from app.db.repositories.chunks import (
    get_all_chunks_for_repo,
    get_chunks_by_ids,
    search_similar,
)

log = structlog.get_logger()

from rank_bm25 import BM25Okapi

# In-memory BM25 cache: repo_id → (BM25Okapi index, list of chunks)
# Built once per repo on first query, reused after
_bm25_cache: dict[str, tuple[BM25Okapi, list]] = {}

def _tokenize(text: str) -> list[str]:
    """
    Simple tokenizer for BM25.
    Lowercases and splits on whitespace and common code punctuation.
    Keeps identifiers intact — 'verify_token' stays as one token.
    """
    import re
    tokens = re.split(r"[\s\(\)\[\]{},.:;\"'=<>!@#$%^&*+-/\\|`~]+", text.lower())
    return [t for t in tokens if len(t) > 1]


def _reciprocal_rank_fusion(
    vector_chunks: list[Chunk],
    bm25_chunks: list[Chunk],
    k: int = 60,
) -> list[Chunk]:
    """
    Combine two ranked lists using Reciprocal Rank Fusion.

    RRF score for a chunk = sum of 1/(k + rank) across all lists.
    k=60 is the standard constant — dampens the impact of very high ranks.

    Higher RRF score = more relevant.
    A chunk that appears high in both lists scores highest.
    A chunk only in one list still gets credit but scores lower.
    """
    scores: dict[str, float] = {}
    chunk_map: dict[str, Chunk] = {}

    # Score from vector search list
    for rank, chunk in enumerate(vector_chunks):
        chunk_id = str(chunk.id)
        scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + rank + 1)
        chunk_map[chunk_id] = chunk

    # Score from BM25 list
    for rank, chunk in enumerate(bm25_chunks):
        chunk_id = str(chunk.id)
        scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + rank + 1)
        chunk_map[chunk_id] = chunk

    # Sort by combined RRF score descending
    sorted_ids = sorted(scores.keys(), key=lambda cid: scores[cid], reverse=True)
    return [chunk_map[cid] for cid in sorted_ids]


async def _bm25_search(
    db: AsyncSession,
    repo_id: str,
    question: str,
    top_k: int,
) -> list[Chunk]:
    """
    BM25 search with in-memory index caching per repo.
    First query builds the index (~1-2s). Subsequent queries
    use cached index (~10ms).
    Cache is invalidated when repo is re-ingested — handled
    by clearing _bm25_cache on ingest (phase 2 step 6).
    """
    import numpy as np

    if repo_id not in _bm25_cache:
        log.info("bm25_cache_miss_building_index", repo_id=repo_id)
        all_chunks = list(await get_all_chunks_for_repo(db, repo_id))

        if not all_chunks:
            return []

        tokenized_corpus = [
            _tokenize(chunk.file_path.replace("\\", "/") + " " + chunk.content)
            for chunk in all_chunks
        ]
        bm25 = BM25Okapi(tokenized_corpus)
        _bm25_cache[repo_id] = (bm25, all_chunks)
        log.info("bm25_index_built", repo_id=repo_id, chunks=len(all_chunks))
    else:
        log.info("bm25_cache_hit", repo_id=repo_id)

    bm25, all_chunks = _bm25_cache[repo_id]
    query_tokens = _tokenize(question)
    scores = bm25.get_scores(query_tokens)

    top_indices = np.argsort(scores)[::-1][:top_k]
    return [all_chunks[i] for i in top_indices if scores[i] > 0]


async def search(
    db: AsyncSession,
    repo_id: str,
    question: str,
    top_k: int = 5,
) -> list[Chunk]:
    """
    Hybrid search: run vector search and BM25 in parallel,
    combine results with Reciprocal Rank Fusion.

    Retrieves top_k*8 candidates from each method before fusion
    so RRF has enough candidates to rerank from.
    Final result is top_k chunks.
    """
    log.info("search_started", repo_id=repo_id, question=question[:80])

    candidate_k = top_k * 8  # retrieve more candidates before RRF

    # Embed the question for vector search
    query_embedding = embed_text(question)

    # Run both searches
    vector_chunks = list(await search_similar(
        db=db,
        repo_id=repo_id,
        query_embedding=query_embedding,
        top_k=candidate_k,
    ))

    bm25_chunks = await _bm25_search(
        db=db,
        repo_id=repo_id,
        question=question,
        top_k=candidate_k,
    )

    log.info(
        "search_candidates",
        vector_count=len(vector_chunks),
        bm25_count=len(bm25_chunks),
    )

    # Combine with RRF and return top_k
    fused = _reciprocal_rank_fusion(vector_chunks, bm25_chunks)
    result = fused[:top_k]

    log.info("search_complete", chunks_returned=len(result))
    return result

def invalidate_bm25_cache(repo_id: str) -> None:
    """
    Remove cached BM25 index for a repo.
    Called by the ingest route after successful re-indexing.
    """
    if repo_id in _bm25_cache:
        del _bm25_cache[repo_id]
        log.info("bm25_cache_invalidated", repo_id=repo_id)