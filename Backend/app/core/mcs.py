from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict

import numpy as np

from app.models.risk import FinancialSignals, MCSConfig

logger = logging.getLogger(__name__)


@dataclass
class MCSSimulationResult:
    metric: str
    iterations: int
    p10: float
    p50: float
    p90: float
    mean: float
    success_prob_vs_claim: float

    def to_dict(self) -> Dict[str, float]:
        return {
            "metric": self.metric,
            "iterations": self.iterations,
            "p10": self.p10,
            "p50": self.p50,
            "p90": self.p90,
            "mean": self.mean,
            "success_prob_vs_claim": self.success_prob_vs_claim,
        }


def simulate_financials(financials: FinancialSignals, config: MCSConfig, seed: int = 12345) -> MCSSimulationResult:
    iterations = config.iterations
    horizon = config.horizon_months
    rng = np.random.default_rng(seed)

    base_revenue = max(financials.base_monthly_revenue or 0.0, 0.0)
    growth_mean = financials.growth_mean if financials.growth_mean is not None else 0.03
    growth_sd = financials.growth_sd if financials.growth_sd is not None else 0.02
    churn_mean = financials.churn_mean if financials.churn_mean is not None else 0.02
    churn_sd = financials.churn_sd if financials.churn_sd is not None else 0.01
    claimed = financials.claimed_month12_revenue if financials.claimed_month12_revenue is not None else base_revenue

    revenue = np.full(iterations, base_revenue, dtype=float)

    lognormal_mu = np.log1p(growth_mean) - 0.5 * (growth_sd ** 2)

    burn = abs(financials.burn or 0.0)

    for _ in range(horizon):
        growth_factors = rng.lognormal(lognormal_mu, growth_sd, iterations)
        churn = np.clip(rng.normal(churn_mean, churn_sd, iterations), 0.0, 0.6)

        if burn > 0:
            efficiency = np.clip(revenue / burn, 0.0, 2.5)
        else:
            efficiency = np.full(iterations, 1.5)
        efficiency_boost = efficiency * 0.0192

        revenue *= growth_factors + efficiency_boost
        revenue *= (1.0 - churn)
        noise = rng.normal(1.0, 0.02, iterations)
        revenue *= np.clip(noise, 0.9, 1.1)
        revenue = np.clip(revenue, 0.0, None)

    p10, p50, p90 = np.percentile(revenue, [10, 50, 90])
    mean = float(np.mean(revenue))
    success_prob = float(np.mean(revenue >= claimed))

    return MCSSimulationResult(
        metric=config.target,
        iterations=iterations,
        p10=float(p10),
        p50=float(p50),
        p90=float(p90),
        mean=mean,
        success_prob_vs_claim=success_prob,
    )
