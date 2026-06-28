from pathlib import Path

from app.core.ingestion.import_parser import parse_imports


def test_from_import_resolved(tmp_path):
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "utils.py").write_text("def helper(): pass")
    result = parse_imports("app/main.py", "from app.utils import helper", tmp_path)
    assert "app/utils.py" in result


def test_regular_import_resolved(tmp_path):
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "config.py").write_text("X = 1")
    result = parse_imports("app/main.py", "import app.config", tmp_path)
    assert "app/config.py" in result


def test_package_init_resolved(tmp_path):
    pkg = tmp_path / "mypackage"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    result = parse_imports("main.py", "import mypackage", tmp_path)
    # Normalize separators: Windows returns backslash, Linux/CI returns forward slash
    normalized = [p.replace("\\", "/") for p in result]
    assert "mypackage/__init__.py" in normalized


def test_nonexistent_import_filtered(tmp_path):
    # requests and os don't exist in tmp_path, so nothing should be returned
    result = parse_imports("app/main.py", "import requests\nimport os", tmp_path)
    assert result == []


def test_syntax_error_returns_empty(tmp_path):
    result = parse_imports("app/main.py", "def broken(:\n    pass", tmp_path)
    assert result == []


def test_deduplication(tmp_path):
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "utils.py").write_text("def foo(): pass\ndef bar(): pass")
    content = "from app.utils import foo\nfrom app.utils import bar"
    result = parse_imports("app/main.py", content, tmp_path)
    assert result.count("app/utils.py") == 1


def test_multiple_imports_all_resolved(tmp_path):
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "auth.py").write_text("")
    (tmp_path / "app" / "db.py").write_text("")
    content = "from app.auth import login\nfrom app.db import session"
    result = parse_imports("app/main.py", content, tmp_path)
    assert "app/auth.py" in result
    assert "app/db.py" in result
