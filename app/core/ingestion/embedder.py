import httpx
import structlog

from app.config import settings
from app.core.ingestion.chunker import ChunkData

log = structlog.get_logger()

COHERE_EMBED_URL = "https://api.cohere.com/v2/embed"
COHERE_MODEL = "embed-english-light-v3.0"  # 384-dim, free tier
COHERE_BATCH_SIZE = 96  # Cohere's max texts per request


def _call_cohere(texts: list[str], input_type: str) -> list[list[float]]:
    results: list[list[float]] = []
    for i in range(0, len(texts), COHERE_BATCH_SIZE):
        batch = texts[i : i + COHERE_BATCH_SIZE]
        r = httpx.post(
            COHERE_EMBED_URL,
            headers={"Authorization": f"Bearer {settings.cohere_api_key}"},
            json={
                "texts": batch,
                "model": COHERE_MODEL,
                "input_type": input_type,
                "embedding_types": ["float"],
            },
            timeout=60,
        )
        r.raise_for_status()
        results.extend(r.json()["embeddings"]["float"])
    return results


def embed_chunks(chunks: list[ChunkData]) -> list[dict]:
    if not chunks:
        return []

    texts = [chunk.content for chunk in chunks]
    log.info("embedding_started", total_chunks=len(chunks))

    embeddings = _call_cohere(texts, input_type="search_document")

    log.info("embedding_complete", total_chunks=len(chunks))
    return [
        {
            "file_path": chunk.file_path,
            "start_line": chunk.start_line,
            "end_line": chunk.end_line,
            "content": chunk.content,
            "embedding": embedding,
        }
        for chunk, embedding in zip(chunks, embeddings)
    ]


def embed_text(text: str) -> list[float]:
    # input_type="search_query" tells Cohere this is a query, not a document
    return _call_cohere([text], input_type="search_query")[0]
