from app.core.ingestion.chunker import _chunk_lines, chunk_file


def _lines(n: int) -> str:
    return "\n".join(f"line{i}" for i in range(n))


def test_short_file_produces_single_chunk():
    chunks = _chunk_lines("f.txt", _lines(10), chunk_size=40, overlap=5)
    assert len(chunks) == 1
    assert chunks[0].start_line == 1
    assert chunks[0].end_line == 10


def test_exact_chunk_size_is_single_chunk():
    chunks = _chunk_lines("f.txt", _lines(40), chunk_size=40, overlap=5)
    assert len(chunks) == 1


def test_file_larger_than_chunk_produces_multiple_chunks():
    chunks = _chunk_lines("f.txt", _lines(50), chunk_size=40, overlap=5)
    assert len(chunks) == 2


def test_overlap_content_shared_between_consecutive_chunks():
    content = _lines(50)
    chunks = _chunk_lines("f.txt", content, chunk_size=40, overlap=5)
    tail_of_first = set(chunks[0].content.splitlines()[-5:])
    head_of_second = set(chunks[1].content.splitlines()[:5])
    assert tail_of_first & head_of_second  # non-empty intersection


def test_line_numbers_start_at_one():
    chunks = _chunk_lines("f.txt", _lines(5), chunk_size=40)
    assert chunks[0].start_line == 1


def test_file_path_preserved():
    chunks = _chunk_lines("mydir/file.txt", _lines(5))
    assert chunks[0].file_path == "mydir/file.txt"


def test_chunk_file_py_uses_ast():
    src = "def foo():\n    return 42\n\ndef bar():\n    return 0\n"
    chunks = chunk_file("module.py", src)
    combined = " ".join(c.content for c in chunks)
    assert "def foo" in combined
    assert "def bar" in combined


def test_chunk_file_non_py_uses_line_strategy():
    content = _lines(10)
    chunks = chunk_file("readme.md", content)
    assert len(chunks) == 1
    assert "line0" in chunks[0].content
