from __future__ import annotations

import logging
from typing import Dict

from fastapi import APIRouter, HTTPException, Response

from app.core.fuzzy import (
    blend_financials_score,
    financials_base_score,
    go_to_market_score,
    market_opportunity_score,
    product_moat_score,
    team_strength_score,
)
from app.core.mcs import simulate_financials
from app.core.wsm import aggregate_scores, normalize_weights
from app.models.risk import (
    FactorBreakdown,
    MCSSummary,
    RiskAssessmentRequest,
    RiskAssessmentResponse,
)
from app.utils.text import build_narrative

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/risk", tags=["risk"])


@router.post("/assess", response_model=RiskAssessmentResponse)
async def assess_risk(request: RiskAssessmentRequest, response: Response) -> RiskAssessmentResponse:
    weights_input = request.weights.materialized()
    weights, normalized = normalize_weights(weights_input)

    if normalized:
        response.headers["X-Weights-Normalized"] = "true"
    else:
        response.headers["X-Weights-Normalized"] = "false"

    analysis = request.analysisData

    team_score, team_rationale = team_strength_score(analysis.team)
    market_score, market_rationale = market_opportunity_score(analysis.market)
    product_score, product_rationale = product_moat_score(analysis.product)
    gtm_score, gtm_rationale = go_to_market_score(analysis.gtm)

    if analysis.financials is None:
        logger.warning("Financial data missing from analysis; using conservative defaults for MCS")
        raise HTTPException(status_code=400, detail="Financial signals are required for risk assessment")

    base_financial_score, financial_rationale, _ = financials_base_score(analysis.financials)
    mcs_result = simulate_financials(analysis.financials, request.mcs)
    financial_score = blend_financials_score(base_financial_score, mcs_result.success_prob_vs_claim)
    financial_rationale["signal"] += f"; MCS success {mcs_result.success_prob_vs_claim:.0%}"
    financial_rationale["caveat"] = (
        "Bridge plan needed to reach claimed revenue" if mcs_result.success_prob_vs_claim < 0.5 else "Track execution to convert modeled upside"
    )

    breakdown_dict: Dict[str, int] = {
        "teamStrength": team_score,
        "marketOpportunity": market_score,
        "productMoat": product_score,
        "goToMarket": gtm_score,
        "financials": financial_score,
    }

    rationales = {
        "teamStrength": team_rationale,
        "marketOpportunity": market_rationale,
        "productMoat": product_rationale,
        "goToMarket": gtm_rationale,
        "financials": financial_rationale,
    }

    composite = aggregate_scores(weights, breakdown_dict)

    mcs_summary = MCSSummary(**mcs_result.to_dict())
    narrative = build_narrative(breakdown_dict, rationales, mcs_summary.model_dump())

    response_payload = RiskAssessmentResponse(
        composite_investment_safety_score=round(composite, 1),
        factor_breakdown=FactorBreakdown(**breakdown_dict),
        narrative_justification=narrative,
        mcs=mcs_summary,
    )
    return response_payload
