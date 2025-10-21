from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List

import vertexai
from vertexai.preview.generative_models import GenerationConfig, GenerativeModel

from config.settings import settings

logger = logging.getLogger(__name__)


class GeminiSummarizer:
    """Wrapper around Gemini with deterministic defaults and parsing helpers."""

    def __init__(self) -> None:
        vertexai.init(project=settings.GCP_PROJECT_ID, location=settings.GCP_LOCATION)
        self.model = GenerativeModel("gemini-2.5-pro")
        # Force deterministic behaviour so repeated uploads stay consistent.
        self._generation_config = GenerationConfig(
            temperature=0.0,
            top_p=1.0,
            top_k=1,
        )

    def _generate_text(self, prompt: str) -> str:
        response = self.model.generate_content(
            prompt,
            generation_config=self._generation_config,
        )
        text = getattr(response, "text", "")
        return text.strip() if isinstance(text, str) else ""

    def generate_text(self, prompt: str) -> str:
        """Public wrapper for deterministic text generation."""
        return self._generate_text(prompt)

    @staticmethod
    def _coerce_string_list(value: Any) -> List[str]:
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if isinstance(value, str) and value.strip():
            try:
                parsed = json.loads(value)
            except json.JSONDecodeError:
                return [part.strip("-• \t") for part in value.splitlines() if part.strip("-• \t")]
            return GeminiSummarizer._coerce_string_list(parsed)
        return []

    async def summarize_pitch_deck(self, full_text: str) -> Dict[str, Any]:
        """Summarize pitch deck into structured sections."""
        try:
            prompt = f"""
            Analyze the following pitch deck content and extract information for these sections:
            - problem: What problem is being solved?
            - solution: What is the proposed solution?
            - market: Market size, opportunity, and target customers
            - team: Information about the founding team and key personnel
            - traction: Current progress, metrics, customers, revenue
            - financials: Financial projections, funding requirements, revenue model

            Pitch deck content:
            {full_text}

            Return the analysis as a JSON object with the above keys. Be concise but comprehensive.
            If a section is not clearly addressed in the pitch deck, indicate "Not specified" for that key.
            """

            summary_text = self._generate_text(prompt)

            founder_prompt = f"""
            Analyze the following pitch deck content and extract list of founders in array:

            Pitch deck content:
            {full_text}

            Return the analysis as an array.
            If no data found send empty array.
            """

            founder_raw = self._generate_text(founder_prompt)
            founder_clean = re.sub(r"^```json\s*|\s*```$", "", founder_raw, flags=re.MULTILINE)
            try:
                founder_data = json.loads(founder_clean) if founder_clean else []
            except json.JSONDecodeError:
                founder_data = founder_clean
            founder_response = self._coerce_string_list(founder_data)

            sector_prompt = f"""
            Analyze the following pitch deck content and extract name of sector in which this startup fall in:

            Pitch deck content:
            {full_text}

            Return specific sector name only no extra word.
            If no data found send empty string "".
            """

            sector_response = re.sub(
                r"^```[a-zA-Z]*\s*|\s*```$",
                "",
                self._generate_text(sector_prompt),
                flags=re.MULTILINE,
            ).strip()

            company_name_prompt = f"""
            Analyze the following pitch deck content and extract name of the startup/company this pitch is for:

            Pitch deck content:
            {full_text}

            Return specific name only no extra words.
            If no data found send empty string "".
            """

            company_name_response = re.sub(
                r"^```[a-zA-Z]*\s*|\s*```$",
                "",
                self._generate_text(company_name_prompt),
                flags=re.MULTILINE,
            ).strip()

            return {
                "summary_res": summary_text,
                "founder_response": founder_response,
                "sector_response": sector_response,
                "company_name_response": company_name_response,
            }

        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error("Pitch deck summarization error: %s", exc)
            return {
                "problem": "Error in processing",
                "solution": "Error in processing",
                "market": "Error in processing",
                "team": "Error in processing",
                "traction": "Error in processing",
                "financials": "Error in processing",
                "founder_response": [],
                "sector_response": "",
                "company_name_response": "",
                "summary_res": "",
            }

    async def summarize_audio_transcript(self, transcript: str) -> str:
        """Summarize audio transcript."""
        try:
            prompt = f"""
            Summarize the following pitch transcript into key points:
            - Main value proposition
            - Key business metrics mentioned
            - Important insights about market or competition
            - Notable quotes from the founder

            Transcript:
            {transcript}

            Provide a concise summary in bullet points.
            """

            return self._generate_text(prompt)

        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error("Audio summarization error: %s", exc)
            return "Error processing audio transcript"

    async def generate_memo(self, deal_data: Dict[str, Any], weightage: Dict[str, Any]) -> Dict[str, Any]:
        """Generate complete investment memo."""
        try:
            metadata = deal_data.get("metadata", {})
            extracted_text = deal_data.get("extracted_text", {})
            public_data = deal_data.get("public_data", {})
            user_input = deal_data.get("user_input", {})

            context = self._build_memo_context(metadata, extracted_text, public_data, user_input)

            prompt = f"""
                You are an investment analyst. Your task is to generate a structured investment memo for the startup under review.

                Instructions:
                1. The output MUST be in strict JSON format. Do not include text outside the JSON.
                2. Always follow the schema below exactly. Every key and subkey MUST appear, even if data is missing (use "Not available" or [] for empty).
                3. The response must be deterministic and stable across runs — always yielding the same result unless the input data itself changes.
                4. Use the provided company data first, then enrich with reliable internet sources about competitors, market size, and industry trends.
                5. For probabilistic forecasting of company claims, follow these rules:
                   - Dataset length 6–12 months → ETS or Bayesian log-linear regression
                   - Dataset length 12–18 months → ARIMA or Holt-Winters
                   - Dataset length 18+ months → Prophet or Bayesian Structural Time Series
                   - If historical time-series is unavailable, run Monte Carlo simulations on pipeline data
                6. Construct a composite risk metric by combining:
                   - Burn rate
                   - Runway
                   - Gross margins
                   - ARR growth
                   - CAC/LTV ratios
                   - Credibility of claims (based on probabilistic analysis)
                   The risk metric should output a numeric score (0–100) and a narrative justification.
                7. Keep analysis fact-based and consistent. Do not invent competitors or valuations without attribution.
                8. All financial projections, probabilities, and risk metrics must be deterministic and stable.

                Schema to follow exactly:
                {{
                  "company_overview": {{
                    "name": "string",
                    "sector": "string",
                    "founders": [
                      {{
                        "name": "string",
                        "education": "string",
                        "professional_background": "string",
                        "previous_ventures": "string"
                      }}
                    ],
                    "technology": "string"
                  }},
                  "market_analysis": {{
                    "industry_size_and_growth": {{
                      "total_addressable_market": {{
                        "name": "string",
                        "value": "string",
                        "cagr": "string",
                        "source": "string"
                      }},
                      "serviceable_obtainable_market": {{
                        "name": "string",
                        "value": "string",
                        "cagr": "string",
                        "source": "string"
                      }},
                      "commentary": "string"
                    }},
                    "recent_news": "string",
                    "competitor_details": [{{
                      "name": "string",
                      "business_model": "string",
                      "funding": "string",
                      "margins": "string",
                      "commentary": "string",
                      "category": "string"
                    }}],
                    "sub_segment_opportunities": ["string"]
                  }},
                  "business_model": {{
                    "revenue_streams": "string",
                    "pricing": "string",
                    "scalability": "string",
                    "unit_economics": {{
                      "customer_lifetime_value_ltv": "string",
                      "customer_acquisition_cost_cac": "string"
                    }}
                  }},
                  "financials": {{
                    "funding_history": "string",
                    "projections": [{{
                      "year": "string",
                      "revenue": "string"
                    }}],
                    "valuation_rationale": "string",
                    "srr_mrr": {{
                      "current_booked_arr": "string",
                      "current_mrr": "string"
                    }},
                    "burn_and_runway": {{
                      "funding_ask": "string",
                      "stated_runway": "string",
                      "implied_net_burn": "string"
                    }}
                  }},
                  "claims_analysis": [{{
                    "claim": "string",
                    "analysis_method": "string",
                    "input_dataset_length": "string",
                    "simulated_probability": "string",
                    "result": "string",
                    "simulation_assumptions": {{"assumptions": "string"}}
                  }}],
                  "risk_metrics": {{
                    "composite_risk_score": 0,
                    "score_interpretation": "string",
                    "narrative_justification": "string"
                  }},
                  "conclusion": {{
                    "overall_attractiveness": "string"
                  }}
                }}

                Weighting preferences:
                {weightage}

                Source information:
                {context}
            """

            raw_response = self._generate_text(prompt)
            clean = re.sub(r"^```json\s*|\s*```$", "", raw_response, flags=re.MULTILINE).strip()
            try:
                return json.loads(clean) if clean else {}
            except json.JSONDecodeError:
                logger.warning("Gemini memo response was not valid JSON; storing raw payload under 'raw_text'")
                return {"raw_text": clean}

        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error("Memo generation error: %s", exc)
            return {"error": "Error generating memo"}

    def _build_memo_context(
        self,
        metadata: Dict[str, Any],
        extracted_text: Dict[str, Any],
        public_data: Dict[str, Any],
        user_input: Dict[str, Any],
    ) -> str:
        """Build context string for memo generation."""

        context_parts: List[str] = []

        # Company information
        context_parts.append(f"Company: {metadata.get('company_name', 'N/A')}")
        context_parts.append(f"Founders: {', '.join(metadata.get('founder_names', [])) or 'N/A'}")
        context_parts.append(f"Sector: {metadata.get('sector', 'N/A')}")

        # Pitch deck insights
        pitch_deck = extracted_text.get("pitch_deck") if isinstance(extracted_text, dict) else None
        if isinstance(pitch_deck, dict):
            concise = pitch_deck.get("concise")
            if concise:
                context_parts.append("Pitch Deck Analysis:")
                context_parts.append(str(concise))

        # Media summaries
        for media_type in ("voice_pitch", "video_pitch"):
            media_data = extracted_text.get(media_type) if isinstance(extracted_text, dict) else None
            if isinstance(media_data, dict):
                summary = media_data.get("concise", {}).get("summary")
                if summary:
                    context_parts.append(f"{media_type.replace('_', ' ').title()} Summary:")
                    context_parts.append(str(summary))

        # Public data
        if isinstance(public_data, dict) and public_data:
            context_parts.append("Public Information:")
            for key, value in public_data.items():
                if isinstance(value, list):
                    context_parts.append(f"{key.replace('_', ' ').title()}: {', '.join(map(str, value))}")
                else:
                    context_parts.append(f"{key.replace('_', ' ').title()}: {value}")

        # User input (Q&A / weightages)
        if isinstance(user_input, dict) and user_input:
            qna = user_input.get("qna")
            if isinstance(qna, dict):
                context_parts.append("Additional Q&A:")
                for question, answer in qna.items():
                    context_parts.append(f"Q: {question}")
                    context_parts.append(f"A: {answer}")

            if "weightages" in user_input:
                context_parts.append(f"Evaluation Weightages: {user_input['weightages']}")

        return "\n".join(context_parts)
