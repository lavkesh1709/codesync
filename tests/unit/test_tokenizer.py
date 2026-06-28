from app.core.retrieval.searcher import _tokenize


def test_lowercases_tokens():
    assert "hello" in _tokenize("Hello")
    assert "world" in _tokenize("WORLD")


def test_splits_on_whitespace():
    assert _tokenize("foo bar baz") == ["foo", "bar", "baz"]


def test_splits_on_parens():
    tokens = _tokenize("foo(bar)")
    assert "foo" in tokens
    assert "bar" in tokens


def test_splits_on_dot():
    tokens = _tokenize("obj.method")
    assert "obj" in tokens
    assert "method" in tokens


def test_keeps_snake_case_intact():
    # Underscores are not in the split pattern, so snake_case stays as one token
    tokens = _tokenize("verify_token")
    assert "verify_token" in tokens


def test_filters_single_char_tokens():
    tokens = _tokenize("x = 1")
    assert "x" not in tokens
    assert "=" not in tokens


def test_empty_string_returns_empty_list():
    assert _tokenize("") == []


def test_code_line_extracts_identifiers():
    tokens = _tokenize("def my_function(arg1, arg2):")
    assert "def" in tokens
    assert "my_function" in tokens
    assert "arg1" in tokens
    assert "arg2" in tokens


def test_handles_numeric_only_tokens():
    # Numerics of length 1 filtered; length >= 2 kept
    tokens = _tokenize("var 10 x")
    assert "10" in tokens
    assert "var" in tokens
    assert "x" not in tokens
