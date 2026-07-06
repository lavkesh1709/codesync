from unittest.mock import AsyncMock, MagicMock, patch

from app.core.ingestion.chunker import ChunkData
from app.core.ingestion.pipeline import run_ingestion

FAKE_FILES = [{"file_path": f"f{i}.py", "content": "x"} for i in range(5)]


class _FakeSession:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def commit(self):
        pass


def _make_chunks(n: int) -> list[ChunkData]:
    return [
        ChunkData(file_path="f.py", start_line=i, end_line=i + 1, content=f"line{i}")
        for i in range(n)
    ]


def _embed_side_effect(batch: list[ChunkData]) -> list[dict]:
    return [
        {
            "file_path": c.file_path,
            "start_line": c.start_line,
            "end_line": c.end_line,
            "content": c.content,
            "embedding": [0.0, 0.0],
        }
        for c in batch
    ]


def _start_patches(chunks_for_chunk_files, embed_chunks_mock):
    """Patch every collaborator run_ingestion touches. Returns (patchers, mocks)
    so the caller can inspect specific mocks and stop all patchers afterwards."""
    patchers = {
        "session": patch(
            "app.core.ingestion.pipeline.AsyncSessionLocal", new=_FakeSession
        ),
        "delete_repo": patch(
            "app.db.repositories.chunks.delete_repo", new=AsyncMock()
        ),
        "insert_repo": patch(
            "app.db.repositories.chunks.insert_repo", new=AsyncMock()
        ),
        "update_repo": patch(
            "app.db.repositories.chunks.update_repo", new=AsyncMock()
        ),
        "clone_repo": patch(
            "app.core.ingestion.cloner.clone_repo",
            new=AsyncMock(return_value="/tmp/fake-repo"),
        ),
        "cleanup_repo": patch(
            "app.core.ingestion.cloner.cleanup_repo", new=MagicMock()
        ),
        "walk_files": patch(
            "app.core.ingestion.file_walker.walk_files",
            new=MagicMock(return_value=FAKE_FILES),
        ),
        "chunk_files": patch(
            "app.core.ingestion.chunker.chunk_files",
            new=MagicMock(return_value=chunks_for_chunk_files),
        ),
        "embed_chunks": patch(
            "app.core.ingestion.embedder.embed_chunks", new=embed_chunks_mock
        ),
        "insert_chunks": patch(
            "app.db.repositories.chunks.insert_chunks",
            new=AsyncMock(side_effect=lambda db, repo_id, chunks: len(chunks)),
        ),
        "parse_all_imports": patch(
            "app.core.ingestion.import_parser.parse_all_imports",
            new=MagicMock(return_value={}),
        ),
        "insert_file_imports": patch(
            "app.db.repositories.chunks.insert_file_imports",
            new=AsyncMock(return_value=0),
        ),
        "invalidate_bm25_cache": patch(
            "app.core.retrieval.searcher.invalidate_bm25_cache", new=MagicMock()
        ),
        "invalidate_cache": patch(
            "app.core.cache.invalidate_cache", new=AsyncMock()
        ),
    }
    mocks = {name: p.start() for name, p in patchers.items()}
    return patchers, mocks


async def test_embeds_and_stores_in_batches():
    chunks = _make_chunks(250)  # > EMBED_BATCH_SIZE (200) -> batches of 200 + 50
    embed_mock = MagicMock(side_effect=_embed_side_effect)

    patchers, mocks = _start_patches(chunks, embed_mock)
    try:
        await run_ingestion("https://example.com/repo.git", "repo-1")
    finally:
        for p in patchers.values():
            p.stop()

    assert embed_mock.call_count == 2
    assert [len(c.args[0]) for c in embed_mock.call_args_list] == [200, 50]
    assert mocks["insert_chunks"].call_count == 2

    update_repo_mock = mocks["update_repo"]
    final_call = update_repo_mock.call_args_list[-1]
    assert final_call.kwargs["status"] == "completed"
    assert final_call.kwargs["chunks_created"] == 250
    assert final_call.kwargs["files_processed"] == len(FAKE_FILES)

    # Progress should be visible after the first batch, not just at the end.
    progress_calls = [
        c for c in update_repo_mock.call_args_list if c.kwargs.get("status") == "embedding"
    ]
    assert any(c.kwargs.get("chunks_created") == 200 for c in progress_calls)


async def test_partial_progress_survives_a_failure_mid_run():
    chunks = _make_chunks(450)  # three batches of 200, 200, 50 -> fail on the second

    call_count = {"n": 0}

    def flaky_embed(batch: list[ChunkData]) -> list[dict]:
        call_count["n"] += 1
        if call_count["n"] == 2:
            raise RuntimeError("cohere_boom")
        return _embed_side_effect(batch)

    embed_mock = MagicMock(side_effect=flaky_embed)

    patchers, mocks = _start_patches(chunks, embed_mock)
    try:
        await run_ingestion("https://example.com/repo.git", "repo-2")
    finally:
        for p in patchers.values():
            p.stop()

    # Only the first batch made it through embed + insert before the second batch raised.
    assert mocks["insert_chunks"].call_count == 1

    final_call = mocks["update_repo"].call_args_list[-1]
    assert final_call.kwargs["status"] == "failed"
    assert final_call.kwargs["chunks_created"] == 200  # first batch's progress, not wiped to 0
    assert final_call.kwargs["files_processed"] == len(FAKE_FILES)
    assert "cohere_boom" in final_call.kwargs["error_message"]
