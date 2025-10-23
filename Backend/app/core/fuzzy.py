from __future__ import annotations

import logging
from math import exp
from typing import Dict, Optional, Tuple

from app.models.risk import (
    FinancialSignals,
    GTMSignals,
    MarketSignals,
    ProductSignals,
    TeamSignals,
)

logger = logging.getLogger(__name__)

ScoreResult = Tuple[int, Dict[str, str]]


def _clamp(value: float, lower: float = 0.0, upper: float = 100.0) -> float:
    return max(lower, min(upper, value))


def _triangular(value: float, left: float, peak: float, right: float) -> float:
    if value <= left or value >= right:
        return 0.0
    if value == peak:
        return 100.0
    if value < peak:
        return 100.0 * (value - left) / (peak - left)
    return 100.0 * (right - value) / (right - peak)


def _trapezoidal(value: float, left: float, left_top: float, right_top: float, right: float) -> float:
    if value <= left or value >= right:
        return 0.0
    if left_top <= value <= right_top:
        return 100.0
    if value < left_top:
        return 100.0 * (value - left) / (left_top - left)
    return 100.0 * (right - value) / (right - right_top)


def team_strength_score(team: Optional[TeamSignals]) -> ScoreResult:
    if team is None:
        logger.warning("Team signals missing; applying conservative defaults")
        return 45, {
            "signal": "Limited team data available",
            "caveat": "Provide founder history and team makeup to refine confidence",
        }

    founders = team.founders or []
    founder_count = max(len(founders), 1)
    avg_experience = sum(f.years_experience for f in founders) / founder_count
    domain_alignment = sum(1 for f in founders if f.domain_match) / founder_count
    prior_exits = sum(1 for f in founders if f.prior_exit)
    prior_exit_ratio = prior_exits / founder_count

    team_size = team.team_size if team.team_size is not None else 5
    senior_ratio = team.senior_ratio if team.senior_ratio is not None else 0.3

    experience_score = _clamp(min(avg_experience / 12.0, 1.2) * 22)
    domain_score = _clamp(domain_alignment * 18)
    exit_score = _clamp(min(prior_exit_ratio * 24, 12))
    size_score = _clamp(min(team_size / 30.0, 1.0) * 18)
    senior_score = _clamp(min(senior_ratio / 0.6, 1.2) * 18)

    blended = experience_score + domain_score + exit_score + size_score + senior_score + 12

    signal = (
        f"Avg {avg_experience:.1f} yrs experience with {domain_alignment:.0%} domain fit"
    )
    caveat = (
        "Increase senior leadership depth" if senior_ratio < 0.4 else "Continue scaling hiring pace"
    )
    return int(round(_clamp(blended))), {"signal": signal, "caveat": caveat}


def market_opportunity_score(market: Optional[MarketSignals]) -> ScoreResult:
    if market is None:
        logger.warning("Market signals missing; applying conservative defaults")
        return 50, {
            "signal": "Market size unknown",
            "caveat": "Clarify TAM, growth, and competition dynamics",
        }

    tam = market.TAM or 5e8
    sam = market.SAM or tam * 0.2
    growth_rate = market.growth_rate if market.growth_rate is not None else 0.05
    competition = (market.competition_intensity or "unknown").lower()

    import math

    tam_score = _clamp(((math.log10(max(tam, 1)) - 6) / 3) * 100)
    sam_ratio = sam / tam if tam else 0.0
    sam_score = _clamp(sam_ratio * 120)
    growth_score = _clamp((growth_rate * 400))

    competition_penalty = {
        "low": 0,
        "moderate": 3,
        "medium": 5,
        "high": 15,
        "crowded": 20,
    }.get(competition, 10)

    aggregate = _clamp(0.5 * tam_score + 0.2 * sam_score + 0.3 * growth_score - competition_penalty)

    signal = f"TAM ~${tam/1e9:.1f}B with {growth_rate:.0%} growth"
    caveat = "Competitive intensity requires differentiated positioning" if competition_penalty >= 10 else "Maintain momentum in capturing SAM"

    return int(round(aggregate)), {"signal": signal, "caveat": caveat}


def product_moat_score(product: Optional[ProductSignals]) -> ScoreResult:
    if product is None:
        logger.warning("Product signals missing; applying conservative defaults")
        return 48, {
            "signal": "Moat details sparse",
            "caveat": "Document IP, defensibility, and switching costs",
        }

    keywords = [kw.lower() for kw in product.defensibility_keywords]
    ip_terms = [claim.lower() for claim in product.ip_claims]

    base = 28 if product.ip_claims else 15
    patent_bonus = 12 if any("patent" in term for term in ip_terms) else 0

    strategic_tokens = {"network", "data", "proprietary", "regulation", "compliance", "ai", "automation"}
    keyword_hits = 0
    for phrase in keywords:
        phrase_tokens = {token for token in strategic_tokens if token in phrase}
        keyword_hits += len(phrase_tokens)
    keyword_bonus = min(keyword_hits * 6, 18)

    switching_map = {"high": 18, "medium": 12, "low": 6}
    switching_bonus = switching_map.get((product.switching_cost_signal or "low").lower(), 6)

    moat_depth = min(len(product.ip_claims) * 5, 15)

    score = _clamp(base + patent_bonus + keyword_bonus + switching_bonus + moat_depth)

    signal = "IP claims and defensibility signals present" if score >= 70 else "Emerging moat signals identified"
    caveat = "Expand patent coverage and deepen switching costs" if score < 80 else "Keep reinforcing data advantages"
    return int(round(score)), {"signal": signal, "caveat": caveat}


def go_to_market_score(gtm: Optional[GTMSignals]) -> ScoreResult:
    if gtm is None:
        logger.warning("GTM signals missing; applying conservative defaults")
        return 46, {
            "signal": "GTM details incomplete",
            "caveat": "Clarify ICP, channels, and traction milestones",
        }

    icp_score = 30 if gtm.icp_defined else 10
    channel_score = _clamp(len(gtm.channels) * 12)
    sales_cycle = gtm.sales_cycle_days if gtm.sales_cycle_days is not None else 90
    cycle_score = _clamp(100 - min(sales_cycle, 240) / 240 * 100)

    logos = gtm.early_traction.logos if gtm.early_traction and gtm.early_traction.logos is not None else 0
    pilots = gtm.early_traction.paid_pilots if gtm.early_traction and gtm.early_traction.paid_pilots is not None else 0
    traction_score = _clamp(min(logos * 5 + pilots * 8, 40))

    total = _clamp(0.25 * icp_score + 0.25 * channel_score + 0.25 * cycle_score + 0.25 * traction_score + 32)

    signal = f"ICP defined with {len(gtm.channels)} channels and {logos} logos"
    caveat = "Shorten sales cycle and expand reference wins" if cycle_score < 60 else "Systematize repeatable demand generation"
    return int(round(total)), {"signal": signal, "caveat": caveat}


def financials_base_score(financials: Optional[FinancialSignals]) -> Tuple[int, Dict[str, str], float]:
    if financials is None:
        logger.warning("Financial signals missing; applying conservative defaults")
        return 40, {
            "signal": "Financial runway unclear",
            "caveat": "Share revenue, burn, and efficiency metrics",
        }, 0.0

    revenue = financials.base_monthly_revenue or 0.0
    burn = abs(financials.burn or 0.0)
    cac_payback = financials.cac_payback_months if financials.cac_payback_months is not None else 18.0
    gross_margin = financials.gross_margin if financials.gross_margin is not None else 0.55

    arr = revenue * 12
    efficiency_ratio = (revenue / burn) if burn else 1.2
    efficiency_score = _clamp(_trapezoidal(efficiency_ratio, 0.2, 0.6, 1.5, 3.0))
    arr_score = _clamp(_trapezoidal(arr, 5e5, 1e6, 1e7, 3e7))
    payback_score = _clamp(_triangular(cac_payback, 24, 10, 6))
    margin_score = _clamp(_trapezoidal(gross_margin, 0.2, 0.45, 0.75, 0.9))

    base = _clamp(0.35 * efficiency_score + 0.35 * arr_score + 0.2 * payback_score + 0.1 * margin_score)

    signal = f"ARR ${arr/1e6:.2f}M with CAC payback ~{cac_payback:.0f}m"
    caveat = "Improve burn efficiency" if efficiency_ratio < 1 else "Sustain healthy margins"
    return int(round(base)), {"signal": signal, "caveat": caveat}, efficiency_ratio


def blend_financials_score(base_score: int, success_prob: float) -> int:
    scaled_prob = 1.0 / (1.0 + exp(-8 * (success_prob - 0.5)))
    mcs_component = _clamp(scaled_prob * 100.0)
    blended = _clamp(0.4 * base_score + 0.6 * mcs_component)
    return int(round(blended))
