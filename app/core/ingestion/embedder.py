import structlog

from app.config import settings
from app.core.ingestion.chunker import ChunkData

log = structlog.get_logger()

# Lazy singleton — fastembed uses ONNX runtime (~50MB) instead of PyTorch (~300MB)
# Import deferred to first use so startup memory stays low.
_model = None


FASTEMBED_MODEL = "BAAI/bge-small-en-v1.5"  # 384-dim, ONNX, ~50MB


def _get_model():
    global _model
    if _model is None:
        from fastembed import TextEmbedding
        log.info("embedding_model_loading", model=FASTEMBED_MODEL)
        _model = TextEmbedding(FASTEMBED_MODEL)
        log.info("embedding_model_ready", model=FASTEMBED_MODEL)
    return _model


def embed_chunks(chunks: list[ChunkData]) -> list[dict]:
    """
    Convert a list of ChunkData objects into dicts ready for database insertion.
    Each dict contains all chunk fields plus the embedding vector.
    """
    if not chunks:
        return []

    model = _get_model()
    texts = [chunk.content for chunk in chunks]

    log.info("embedding_started", total_chunks=len(chunks))

    # fastembed.embed() returns a generator of numpy arrays — materialise it
    embeddings = list(model.embed(texts, batch_size=32))

    log.info("embedding_complete", total_chunks=len(chunks))

    return [
        {
            "file_path": chunk.file_path,
            "start_line": chunk.start_line,
            "end_line": chunk.end_line,
            "content": chunk.content,
            "embedding": embedding.tolist(),
        }
        for chunk, embedding in zip(chunks, embeddings)
    ]


def embed_text(text: str) -> list[float]:
    """
    Embed a single string. Used at query time.
    Same model and vector space as embed_chunks.
    """
    model = _get_model()
    embeddings = list(model.embed([text]))
    return embeddings[0].tolist()
