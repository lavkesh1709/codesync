import numpy as np
import structlog
from sentence_transformers import SentenceTransformer

from app.config import settings
from app.core.ingestion.chunker import ChunkData

log = structlog.get_logger()

# Load model once at module import time
# This runs when the application starts — not per request
# Loading takes 2-5 seconds and uses ~90MB RAM
# Every subsequent embed call reuses this same model instance
log.info("embedding_model_loading", model=settings.embedding_model)
_model = SentenceTransformer(settings.embedding_model)
log.info("embedding_model_ready", model=settings.embedding_model)


def embed_chunks(chunks: list[ChunkData]) -> list[dict]:
    """
    Convert a list of ChunkData objects into dicts ready
    for database insertion. Each dict contains all chunk
    fields plus the embedding vector.

    Processes in batches of 32 to avoid loading all chunks
    into memory at once.

    Returns list of dicts with keys:
        file_path, start_line, end_line, content, embedding
    """
    if not chunks:
        return []

    texts = [chunk.content for chunk in chunks]
    batch_size = 32
    total_batches = (len(texts) + batch_size - 1) // batch_size

    log.info(
        "embedding_started",
        total_chunks=len(chunks),
        total_batches=total_batches,
    )

    # encode() handles batching internally when we pass batch_size
    # normalize_embeddings=True ensures vectors have L2 norm of 1
    # This makes cosine similarity equivalent to dot product
    # and keeps all scores in the range [0, 1]
    embeddings = _model.encode(
        texts,
        batch_size=batch_size,
        show_progress_bar=True,
        normalize_embeddings=True,
        convert_to_numpy=True,
    )

    log.info("embedding_complete", total_chunks=len(chunks))

    # Combine chunk metadata with its embedding
    result = []
    for chunk, embedding in zip(chunks, embeddings):
        result.append({
            "file_path": chunk.file_path,
            "start_line": chunk.start_line,
            "end_line": chunk.end_line,
            "content": chunk.content,
            "embedding": embedding.tolist(),  # convert numpy array to list
        })

    return result


def embed_text(text: str) -> list[float]:
    """
    Embed a single text string.
    Used at query time to embed the user's question.
    Same model, same vector space as embed_chunks.
    """
    embedding = _model.encode(
        text,
        normalize_embeddings=True,
        convert_to_numpy=True,
    )
    return embedding.tolist()