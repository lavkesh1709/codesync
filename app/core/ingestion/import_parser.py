import ast
import os
from pathlib import Path

import structlog

log = structlog.get_logger()


def _resolve_import_to_path(
    module_path: str,
    repo_root: Path,
    source_file: str,
) -> str | None:
    """
    Convert a Python module path to a file path within the repo.

    Example:
      module_path: "app.auth.utils"
      repo_root:   /tmp/codesync_myrepo/
      returns:     "app/auth/utils.py"

    Returns None if the resolved path doesn't exist in the repo.
    This filters out third-party and stdlib imports automatically.
    """
    # Convert dot notation to file path
    # "app.auth.utils" → "app/auth/utils.py"
    relative_path = module_path.replace(".", "/") + ".py"
    full_path = repo_root / relative_path

    if full_path.exists():
        return relative_path

    # Also check if it's a package (directory with __init__.py)
    # "app.auth" → "app/auth/__init__.py"
    package_path = repo_root / module_path.replace(".", "/") / "__init__.py"
    if package_path.exists():
        return str(Path(module_path.replace(".", "/")) / "__init__.py")

    return None


def parse_imports(
    file_path: str,
    content: str,
    repo_root: Path,
) -> list[str]:
    """
    Parse all import statements from a Python file and resolve
    them to actual file paths within the repo.

    Uses Python's ast module — more reliable than regex because
    it understands Python syntax properly.

    Returns list of relative file paths that this file imports.
    Only includes files that actually exist in the repo.
    Third-party and stdlib imports are filtered out automatically.

    Example:
      file_path: "app/api/routes/ingest.py"
      content:   the file's source code
      returns:   ["app/core/ingestion/tasks.py",
                  "app/db/repositories/chunks.py",
                  "app/db/session.py"]
    """
    imports: list[str] = []

    try:
        tree = ast.parse(content)
    except SyntaxError:
        # File has syntax errors — skip import parsing
        log.warning("import_parse_syntax_error", file=file_path)
        return []

    for node in ast.walk(tree):

        # Handle: import app.auth.utils
        if isinstance(node, ast.Import):
            for alias in node.names:
                resolved = _resolve_import_to_path(alias.name, repo_root, file_path)
                if resolved and resolved != file_path:
                    imports.append(resolved)

        # Handle: from app.auth.utils import verify_password
        elif isinstance(node, ast.ImportFrom):
            if node.module is None:
                continue

            # Handle relative imports: from . import something
            # node.level > 0 means relative import
            if node.level > 0:
                # Resolve relative to current file's directory
                source_dir = str(Path(file_path).parent).replace("\\", "/")
                parts = source_dir.split("/")

                # Go up 'level' directories
                parts = parts[:len(parts) - (node.level - 1)]
                if node.module:
                    parts.append(node.module.replace(".", "/"))
                module_path = ".".join(
                    p for p in "/".join(parts).split("/") if p
                )
            else:
                module_path = node.module

            resolved = _resolve_import_to_path(module_path, repo_root, file_path)
            if resolved and resolved != file_path:
                imports.append(resolved)

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique_imports: list[str] = []
    for imp in imports:
        if imp not in seen:
            seen.add(imp)
            unique_imports.append(imp)

    return unique_imports


def parse_all_imports(
    files: list[dict[str, str]],
    repo_root: Path,
) -> dict[str, list[str]]:
    """
    Parse imports from all Python files in the repo.
    Returns adjacency list: {source_file: [imported_files]}

    Only processes .py files — other file types don't have imports.
    """
    adjacency: dict[str, list[str]] = {}

    python_files = [f for f in files if f["file_path"].endswith(".py")]

    for file in python_files:
        file_path = file["file_path"].replace("\\", "/")
        imports = parse_imports(
            file_path=file_path,
            content=file["content"],
            repo_root=repo_root,
        )
        if imports:
            adjacency[file_path] = imports

    log.info(
        "import_parsing_complete",
        python_files=len(python_files),
        files_with_imports=len(adjacency),
    )

    return adjacency