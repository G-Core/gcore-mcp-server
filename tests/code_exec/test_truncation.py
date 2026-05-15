"""Tests for the runner's byte/value truncation helpers."""

from __future__ import annotations

from gcore_mcp_server.code_exec.runner import (
    MAX_RESULT_BYTES,
    MAX_STREAM_BYTES,
    _truncate_bytes,
    _truncate_for_return,
)


def test_truncate_bytes_short_string_passthrough():
    """Under-limit strings are returned unchanged."""
    s = "hello world"
    assert _truncate_bytes(s, max_bytes=MAX_STREAM_BYTES) == s


def test_truncate_bytes_long_string_truncated():
    """Oversized strings get suffix-truncated with a dropped-bytes marker."""
    s = "a" * 100_000
    out = _truncate_bytes(s, max_bytes=1000)

    assert len(out.encode("utf-8")) < len(s.encode("utf-8"))
    assert "truncated" in out
    assert "dropped" in out


def test_truncate_bytes_unicode_safe():
    """Multi-byte characters truncate at safe boundaries — no UnicodeDecodeError."""
    # Each emoji here is 4 bytes in UTF-8.
    s = "🐍" * 5000  # ~20 KB

    # Pick a max_bytes that almost certainly lands in the middle of an emoji.
    out = _truncate_bytes(s, max_bytes=1003)

    # If we reach this line, the helper did not raise UnicodeDecodeError.
    assert "truncated" in out
    # And the prefix portion must still be valid UTF-8.
    assert out.encode("utf-8").decode("utf-8") == out


def test_truncate_for_return_primitive_passthrough():
    """Scalars pass through unchanged when under limit and ``hit`` is False."""
    for v in (42, "hi", None, 3.14, True):
        trimmed, hit = _truncate_for_return(v, max_bytes=MAX_RESULT_BYTES)
        assert trimmed == v
        assert hit is False


def test_truncate_for_return_oversized_list():
    """A massively oversized list is truncated and signals via a ``_truncated`` marker."""
    big = [{"index": i, "payload": "x" * 200} for i in range(10_000)]

    trimmed, hit = _truncate_for_return(big, max_bytes=10_000)

    assert hit is True
    assert isinstance(trimmed, list)
    assert len(trimmed) < len(big)
    # Last element is the truncation marker.
    last = trimmed[-1]
    assert isinstance(last, dict)
    assert last.get("_truncated") is True
    assert isinstance(last.get("_dropped_items"), int)
    assert last["_dropped_items"] > 0


def test_truncate_for_return_oversized_dict():
    """A massively oversized dict is truncated and carries ``_truncated`` markers."""
    big = {f"key_{i:04d}": "x" * 200 for i in range(10_000)}

    trimmed, hit = _truncate_for_return(big, max_bytes=10_000)

    assert hit is True
    assert isinstance(trimmed, dict)
    assert trimmed.get("_truncated") is True
    assert isinstance(trimmed.get("_dropped_items"), int)
    assert trimmed["_dropped_items"] > 0
    # And some real keys made it through.
    real_keys = [k for k in trimmed if not str(k).startswith("_")]
    assert len(real_keys) > 0


def test_truncate_for_return_nested():
    """A nested structure overflows at the level where the budget runs out and
    leaves a truncation marker so the caller can see where the cut happened."""
    nested = [
        ["small"],
        [{"payload": "x" * 100} for _ in range(5_000)],
        ["small_tail"],
    ]

    trimmed, hit = _truncate_for_return(nested, max_bytes=10_000)

    assert hit is True
    assert isinstance(trimmed, list)
    # The first inner element survives intact.
    assert trimmed[0] == ["small"]
    # The big inner list (or its containing slot) is replaced by a marker
    # entry. Either the inner list got its own trailing marker, or the outer
    # list dropped it entirely with a marker dict; both are valid outcomes
    # for the depth-first walk.
    inner = trimmed[1]
    if isinstance(inner, list):
        assert any(
            isinstance(item, dict) and item.get("_truncated") is True for item in inner
        )
    else:
        assert isinstance(inner, dict)
        assert inner.get("_truncated") is True
        assert isinstance(inner.get("_dropped_items"), int)
        assert inner["_dropped_items"] >= 1
