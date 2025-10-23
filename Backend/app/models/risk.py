from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


DEFAULT_WEIGHTS: Dict[str, float] = {
    "teamStrength": 0.2,
    "marketOpportunity": 0.2,
    "productMoat": 0.15,
    "goToMarket": 0.15,
    "financials": 0.3,
}


class WeightInputs(BaseModel):
    teamStrength: Optional[float] = Field(default=None, ge=0)
    marketOpportunity: Optional[float] = Field(default=None, ge=0)
    productMoat: Optional[float] = Field(default=None, ge=0)
    goToMarket: Optional[float] = Field(default=None, ge=0)
    financials: Optional[float] = Field(default=None, ge=0)

    def materialized(self) -> Dict[str, float]:
        weights = {}
        for key, default in DEFAULT_WEIGHTS.items():
            value = getattr(self, key, None)
            if value is None:
                weights[key] = default
            else:
                weights[key] = max(0.0, float(value))
        return weights


class FounderProfile(BaseModel):
    years_experience: float = Field(default=0, ge=0)
    domain_match: bool = False
    prior_exit: bool = False


class TeamSignals(BaseModel):
    founders: List[FounderProfile] = Field(default_factory=list)
    team_size: Optional[int] = Field(default=None, ge=0)
    senior_ratio: Optional[float] = Field(default=None, ge=0, le=1)


class MarketSignals(BaseModel):
    TAM: Optional[float] = Field(default=None, ge=0)
    SAM: Optional[float] = Field(default=None, ge=0)
    growth_rate: Optional[float] = None
    competition_intensity: Optional[str] = None


class ProductSignals(BaseModel):
    ip_claims: List[str] = Field(default_factory=list)
    switching_cost_signal: Optional[str] = None
    defensibility_keywords: List[str] = Field(default_factory=list)


class EarlyTraction(BaseModel):
    logos: Optional[int] = Field(default=None, ge=0)
    paid_pilots: Optional[int] = Field(default=None, ge=0)


class GTMSignals(BaseModel):
    icp_defined: Optional[bool] = None
    channels: List[str] = Field(default_factory=list)
    sales_cycle_days: Optional[int] = Field(default=None, ge=0)
    early_traction: Optional[EarlyTraction] = None


class FinancialSignals(BaseModel):
    base_monthly_revenue: Optional[float] = Field(default=None, ge=0)
    growth_mean: Optional[float] = None
    growth_sd: Optional[float] = Field(default=None, ge=0)
    churn_mean: Optional[float] = None
    churn_sd: Optional[float] = Field(default=None, ge=0)
    burn: Optional[float] = Field(default=None)
    claimed_month12_revenue: Optional[float] = Field(default=None, ge=0)
    cac_payback_months: Optional[float] = Field(default=None, ge=0)
    gross_margin: Optional[float] = Field(default=None)


class AnalysisData(BaseModel):
    team: Optional[TeamSignals] = None
    market: Optional[MarketSignals] = None
    product: Optional[ProductSignals] = None
    gtm: Optional[GTMSignals] = None
    financials: Optional[FinancialSignals] = None


class MCSConfig(BaseModel):
    iterations: int = Field(default=5000, ge=100, le=20000)
    target: str = Field(default="revenue")
    horizon_months: int = Field(default=12, ge=1, le=60)


class RiskAssessmentRequest(BaseModel):
    weights: WeightInputs = Field(default_factory=WeightInputs)
    analysisData: AnalysisData = Field(default_factory=AnalysisData)
    mcs: MCSConfig = Field(default_factory=MCSConfig)


class FactorBreakdown(BaseModel):
    teamStrength: int
    marketOpportunity: int
    productMoat: int
    goToMarket: int
    financials: int


class MCSSummary(BaseModel):
    metric: str
    iterations: int
    p10: float
    p50: float
    p90: float
    mean: float
    success_prob_vs_claim: float

    @field_validator("p10", "p50", "p90", "mean", "success_prob_vs_claim", mode="before")
    def ensure_float(cls, value: float) -> float:
        return float(value)


class RiskAssessmentResponse(BaseModel):
    composite_investment_safety_score: float
    factor_breakdown: FactorBreakdown
    narrative_justification: str
    mcs: MCSSummary

    @field_validator("composite_investment_safety_score", mode="before")
    def round_composite(cls, value: float) -> float:
        return round(float(value), 1)
