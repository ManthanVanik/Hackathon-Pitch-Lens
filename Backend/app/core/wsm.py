from __future__ import annotations

from typing import Dict, Tuple

from app.models.risk import DEFAULT_WEIGHTS


def normalize_weights(raw_weights: Dict[str, float]) -> Tuple[Dict[str, float], bool]:
    cleaned = {key: max(0.0, float(value)) for key, value in raw_weights.items()}
    total = sum(cleaned.values())

    if total <= 0.0:
        return DEFAULT_WEIGHTS.copy(), True

    normalized = {key: value / total for key, value in cleaned.items()}
    diff = abs(sum(normalized.values()) - 1.0)

    if diff <= 0.05:
        return normalized, False

    renormalized = {key: value / total for key, value in cleaned.items()}
    return renormalized, True


def aggregate_scores(weights: Dict[str, float], scores: Dict[str, float]) -> float:
    return sum(weights[key] * scores.get(key, 0.0) for key in weights)
