from pathlib import Path

import structlog

log = structlog.get_logger()

# Extensions we index — source code, docs, config
INCLUDE_EXTENSIONS = {
    # Source code
    ".py", ".js", ".ts", ".jsx", ".tsx",
    ".java", ".go", ".rb", ".rs",
    ".cpp", ".c", ".h", ".cs", ".php",
    ".swift", ".kt", ".sh",
    # Documentation
    ".md", ".rst", ".txt",
    # Configuration
    ".yaml", ".yml", ".toml", ".json",
    ".env.example", ".dockerfile",
}

# Exact filenames to include even without a matching extension
INCLUDE_FILENAMES = {
    "Dockerfile",
    "Makefile",
    ".env.example",
}

# Directories to skip entirely
SKIP_DIRS = {
    ".git",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    "dist",
    "build",
    ".mypy_cache",
    ".ruff_cache",
    ".pytest_cache",
    ".agents",       # ← add this
    ".github",
    # Skip translated docs — they duplicate content and pollute retrieval
    # Only keep English docs
    "docs/de", "docs/fr", "docs/ja", "docs/ko", "docs/zh",
    "docs/pt", "docs/es", "docs/ru", "docs/it", "docs/tr",
    "docs/pl", "docs/uk", "docs/nl", "docs/fa", "docs/bn",
    "docs/vi", "docs/id", "docs/az", "docs/he", "docs/hy",
    "docs/ka", "docs/lo", "docs/mn", "docs/sq", "docs/sv",
    "docs/ta", "docs/th", "docs/yo",
}


def walk_files(
    repo_path: Path,
    max_file_size_mb: int = 1,
) -> list[dict[str, str]]:
    """
    Walk a cloned repository and return eligible files.
    Each returned dict has:
        file_path: str  — relative path from repo root
        content:   str  — UTF-8 decoded file content
    Files are skipped if:
        - They are in an excluded directory
        - Their extension is not in INCLUDE_EXTENSIONS
        - They exceed max_file_size_mb
        - They cannot be decoded as UTF-8
    """
    max_bytes = max_file_size_mb * 1024 * 1024
    results: list[dict[str, str]] = []
    skipped = 0

    log.info("file_walk_started", repo_path=str(repo_path))

    for file_path in repo_path.rglob("*"):
        # Skip directories themselves — we only want files
        if not file_path.is_file():
            continue

        # Skip if any parent directory is in SKIP_DIRS
        if any(part in SKIP_DIRS for part in file_path.parts):
            continue

        # Check if this file should be included
        # Either by extension or by exact filename
        is_included = (
            file_path.suffix.lower() in INCLUDE_EXTENSIONS
            or file_path.name in INCLUDE_FILENAMES
        )
        if not is_included:
            skipped += 1
            continue

        # Skip files that are too large
        try:
            file_size = file_path.stat().st_size
        except OSError:
            skipped += 1
            continue

        if file_size > max_bytes:
            log.info(
                "file_skipped_too_large",
                file=str(file_path),
                size_mb=round(file_size / 1024 / 1024, 2),
            )
            skipped += 1
            continue

        # Try to read and decode as UTF-8
        # Skip binary files that pass extension filtering
        try:
            content = file_path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            skipped += 1
            continue

        # Skip empty files — nothing to embed
        if not content.strip():
            skipped += 1
            continue

        # Store relative path — not absolute
        # Relative path is cleaner for display in citations
        relative_path = str(file_path.relative_to(repo_path))

        results.append({
            "file_path": relative_path,
            "content": content,
        })

    log.info(
        "file_walk_complete",
        total_included=len(results),
        total_skipped=skipped,
    )

    return results