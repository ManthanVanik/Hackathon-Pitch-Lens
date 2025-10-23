from __future__ import annotations

from typing import Dict


def build_narrative(
    factor_breakdown: Dict[str, int],
    rationales: Dict[str, Dict[str, str]],
    mcs_summary: Dict[str, float],
) -> str:
    bullets = []

    factor_labels = {
        "teamStrength": "Team",
        "marketOpportunity": "Market",
        "productMoat": "Product",
        "goToMarket": "Go-To-Market",
        "financials": "Financials",
    }

    for key in ["teamStrength", "marketOpportunity", "productMoat", "goToMarket", "financials"]:
        rationale = rationales.get(key, {})
        signal = rationale.get("signal", "Signal unavailable")
        caveat = rationale.get("caveat", "No caveat provided")
        bullets.append(
            f"• {factor_labels[key]}: {signal}. Caveat: {caveat}."
        )

    mcs_line = (
        "• MCS: p50 ${p50:,.0f}, success vs claim {success:.0%}.".format(
            p50=mcs_summary.get("p50", 0.0),
            success=mcs_summary.get("success_prob_vs_claim", 0.0),
        )
    )
    bullets.append(mcs_line)

    narrative = " " .join(bullets)
    if len(narrative) > 900:
        narrative = narrative[:897] + "..."
    return narrative
