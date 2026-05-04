from dataclasses import dataclass

import structlog

log = structlog.get_logger()


@dataclass
class ChunkData:
    """
    Represents one chunk of a file.
    Dataclass gives us a clean object with typed fields
    instead of passing dicts everywhere.
    """
    file_path: str
    start_line: int
    end_line: int
    content: str


def chunk_file(
    file_path: str,
    content: str,
    chunk_size: int = 40,
    overlap: int = 5,
) -> list[ChunkData]:
    """
    Split file content into overlapping chunks.

    Example with chunk_size=5, overlap=2 on a 12-line file:
        Chunk 1: lines 1-5
        Chunk 2: lines 4-8   (overlaps 2 lines with chunk 1)
        Chunk 3: lines 7-11  (overlaps 2 lines with chunk 2)
        Chunk 4: lines 10-12 (last chunk, may be smaller)

    Overlap preserves context at chunk boundaries — a function
    call at line 40 and its definition at line 41 won't be
    split into completely separate chunks.
    """
    lines = content.splitlines()
    total_lines = len(lines)

    # Single chunk if file is smaller than chunk_size
    if total_lines <= chunk_size:
        return [
            ChunkData(
                file_path=file_path,
                start_line=1,
                end_line=total_lines,
                content=content,
            )
        ]

    chunks: list[ChunkData] = []
    start = 0  # 0-indexed line position

    while start < total_lines:
        end = min(start + chunk_size, total_lines)

        chunk_lines = lines[start:end]
        chunk_content = "\n".join(chunk_lines)

        # Only add non-empty chunks
        if chunk_content.strip():
            chunks.append(
                ChunkData(
                    file_path=file_path,
                    start_line=start + 1,   # convert to 1-indexed
                    end_line=end,            # end is already 1-indexed
                    content=chunk_content,
                )
            )

        # Move forward by chunk_size minus overlap
        # This is what creates the sliding window effect
        step = chunk_size - overlap
        start += step

        # If we're near the end and the remaining lines
        # are smaller than overlap, stop — we already
        # covered those lines in the previous chunk
        if start >= total_lines:
            break

    return chunks


def chunk_files(
    files: list[dict[str, str]],
    chunk_size: int = 40,
    overlap: int = 5,
) -> list[ChunkData]:
    """
    Chunk all files from the file walker.
    Accepts the list of dicts returned by walk_files().
    Returns a flat list of all chunks across all files.
    """
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