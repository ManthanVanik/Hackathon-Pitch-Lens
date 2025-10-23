from __future__ import annotations

import os
import sys

from fastapi import FastAPI
from fastapi.testclient import TestClient

ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from app.api.risk import router as risk_router


def create_test_app() -> FastAPI:
    app = FastAPI()
    app.include_router(risk_router)
    return app


def test_risk_assessment_endpoint():
    app = create_test_app()
    client = TestClient(app)

    payload = {
        "weights": {"teamStrength": 0.2, "marketOpportunity": 0.2, "productMoat": 0.15, "goToMarket": 0.15, "financials": 0.3},
        "analysisData": {
            "team": {
                "founders": [
                    {"years_experience": 11, "domain_match": True, "prior_exit": True},
                    {"years_experience": 6, "domain_match": True, "prior_exit": False},
                ],
                "team_size": 18,
                "senior_ratio": 0.45,
            },
            "market": {
                "TAM": 2100000000,
                "SAM": 450000000,
                "growth_rate": 0.18,
                "competition_intensity": "moderate",
            },
            "product": {
                "ip_claims": ["provisional patent"],
                "switching_cost_signal": "medium",
                "defensibility_keywords": ["data network effects"],
            },
            "gtm": {
                "icp_defined": True,
                "channels": ["PLG", "Partnerships"],
                "sales_cycle_days": 45,
                "early_traction": {"logos": 6, "paid_pilots": 3},
            },
            "financials": {
                "base_monthly_revenue": 82000,
                "growth_mean": 0.06,
                "growth_sd": 0.03,
                "churn_mean": 0.01,
                "churn_sd": 0.005,
                "cac_payback_months": 10,
                "burn": 65000,
                "claimed_month12_revenue": 210000,
            },
        },
        "mcs": {"iterations": 5000, "target": "revenue", "horizon_months": 12},
    }

    response = client.post("/api/risk/assess", json=payload)
    assert response.status_code == 200, response.text

    body = response.json()
    assert body["factor_breakdown"] == {
        "teamStrength": 82,
        "marketOpportunity": 74,
        "productMoat": 69,
        "goToMarket": 76,
        "financials": 75,
    }
    assert abs(body["composite_investment_safety_score"] - 75.5) <= 0.1

    mcs_summary = body["mcs"]
    assert round(mcs_summary["p50"], 2) == 219275.51
    assert round(mcs_summary["success_prob_vs_claim"], 2) == 0.62
