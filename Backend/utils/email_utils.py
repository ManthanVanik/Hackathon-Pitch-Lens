"""Utilities for extracting contact emails from nested analysis payloads."""
from __future__ import annotations

import re
from typing import Any, Iterator, List, Set

_EMAIL_PATTERN = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)


def _iter_strings(value: Any) -> Iterator[str]:
    """Yield all string fragments inside arbitrarily nested structures."""
    if isinstance(value, str):
        stripped = value.strip()
        if stripped:
            yield stripped
        return

    if isinstance(value, (list, tuple, set)):
        for item in value:
            yield from _iter_strings(item)
        return

    if isinstance(value, dict):
        for item in value.values():
            yield from _iter_strings(item)
        return

    if hasattr(value, "dict") and callable(getattr(value, "dict")):
        try:
            yield from _iter_strings(value.dict())
        except Exception:
            return


def extract_emails(*sources: Any) -> List[str]:
    """Return a de-duplicated list of emails discovered across the provided sources."""
    seen: Set[str] = set()
    ordered: List[str] = []

    for source in sources:
        for segment in _iter_strings(source):
            for match in _EMAIL_PATTERN.findall(segment):
                normalised = match.lower()
                if normalised in seen:
                    continue
                seen.add(normalised)
                ordered.append(match)

    return ordered


__all__ = ["extract_emails"]
