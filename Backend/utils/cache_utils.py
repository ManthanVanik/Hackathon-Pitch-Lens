"""Utility helpers for deterministic memo caching."""
from __future__ import annotations

from typing import Any, Dict, Iterable


def build_weight_signature(weightage: Dict[str, Any]) -> str:
    """Create a deterministic signature string for a weightage mapping.

    The memo cache stores separate entries for different weighting preferences. To
    ensure consistent reuse, we sort keys alphabetically and normalise the values
    to strings so equivalent payloads produce the same signature regardless of
    ordering or numeric representation (e.g. 0.3 vs "0.3").
    """

    def _normalise_value(value: Any) -> str:
        if isinstance(value, (int, float)):
            return f"{float(value):.4f}".rstrip("0").rstrip(".")
        return str(value)

    items: Iterable[tuple[str, str]] = (
        (key, _normalise_value(weightage[key])) for key in sorted(weightage.keys())
    )
    return "|".join(f"{key}:{value}" for key, value in items)


def extract_cached_memo(cache_doc: Dict[str, Any], weight_signature: str) -> Dict[str, Any] | None:
    """Return a memo cache entry from a deck cache document if present."""

    if not cache_doc or not weight_signature:
        return None

    memos = cache_doc.get("memos")
    if not isinstance(memos, dict):
        return None

    entry = memos.get(weight_signature)
    if isinstance(entry, dict):
        return entry
    return None
