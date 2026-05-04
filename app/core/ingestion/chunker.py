from dataclasses import dataclass

import structlog
from tree_sitter import Language, Parser
import tree_sitter_python as tspython

log = structlog.get_logger()

PY_LANGUAGE = Language(tspython.language())
_parser = Parser(PY_LANGUAGE)

EXTRACT_NODE_TYPES = {
    "function_definition",
    "class_definition",
}


@dataclass
class ChunkData:
    file_path: str
    start_line: int
    end_line: int
    content: str


def _chunk_python_ast(
    file_path: str,
    content: str,
    min_lines: int = 2,
) -> list[ChunkData]:
    try:
        tree = _parser.parse(content.encode("utf-8"))
    except Exception as e:
        log.warning("ast_parse_failed", file=file_path, error=str(e))
        return _chunk_lines(file_path, content)

    chunks: list[ChunkData] = []
    lines = content.splitlines()

    def visit(node) -> None:
        # print(f"visiting: {node.type} lines {node.start_point[0]+1}-{node.end_point[0]+1}")
        if node.type in EXTRACT_NODE_TYPES:
            start_line = node.start_point[0]
            end_line = node.end_point[0]

            if (end_line - start_line + 1) < min_lines:
                return

            chunk_content = "\n".join(lines[start_line:end_line + 1])

            if chunk_content.strip():
                chunks.append(ChunkData(
                    file_path=file_path,
                    start_line=start_line + 1,
                    end_line=end_line + 1,
                    content=chunk_content,
                ))
            return

        for child in node.children:
            visit(child)

    visit(tree.root_node)

    if not chunks:
        log.info("ast_no_chunks_fallback", file=file_path)
        return _chunk_lines(file_path, content)

    return chunks


def _chunk_lines(
    file_path: str,
    content: str,
    chunk_size: int = 40,
    overlap: int = 5,
) -> list[ChunkData]:
    lines = content.splitlines()
    total_lines = len(lines)

    if total_lines <= chunk_size:
        return [ChunkData(
            file_path=file_path,
            start_line=1,
            end_line=total_lines,
            content=content,
        )]

    chunks: list[ChunkData] = []
    start = 0

    while start < total_lines:
        end = min(start + chunk_size, total_lines)
        chunk_content = "\n".join(lines[start:end])

        if chunk_content.strip():
            chunks.append(ChunkData(
                file_path=file_path,
                start_line=start + 1,
                end_line=end,
                content=chunk_content,
            ))

        step = chunk_size - overlap
        start += step

        if start >= total_lines:
            break

    return chunks


def chunk_file(
    file_path: str,
    content: str,
    chunk_size: int = 40,
    overlap: int = 5,
) -> list[ChunkData]:
    if file_path.endswith(".py"):
        return _chunk_python_ast(file_path, content)
    return _chunk_lines(file_path, content, chunk_size, overlap)


def chunk_files(
    files: list[dict[str, str]],
    chunk_size: int = 40,
    overlap: int = 5,
) -> list[ChunkData]:
    all_chunks: list[ChunkData] = []

    for file in files:
        file_chunks = chunk_file(
            file_path=file["file_path"],
            content=file["content"],
            chunk_size=chunk_size,
            overlap=overlap,
        )
        all_chunks.extend(file_chunks)

    log.info(
        "chunking_complete",
        total_files=len(files),
        total_chunks=len(all_chunks),
    )

    return all_chunks