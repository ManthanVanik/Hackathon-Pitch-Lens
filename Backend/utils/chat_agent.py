"""Startup chat agent powered by Gemini for contextual Q&A."""

from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, Iterable, List, Optional

import vertexai
from vertexai.preview.generative_models import GenerationConfig, GenerativeModel

from config.settings import settings


class StartupChatAgent:
    """Generate conversational answers using memo context."""

    def __init__(self, model: Optional[GenerativeModel] = None) -> None:
        vertexai.init(project=settings.GCP_PROJECT_ID, location=settings.GCP_LOCATION)
        self._model = model or GenerativeModel("gemini-2.5-pro")
        self._config = GenerationConfig(
            temperature=0.35,
            top_p=0.9,
            top_k=64,
            max_output_tokens=2048,
        )

    async def generate_response(self, analysis: Dict[str, Any], history: List[Dict[str, Any]]) -> str:
        """Generate a response to the latest user message."""

        return await asyncio.to_thread(self._generate_sync, analysis, history)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _generate_sync(self, analysis: Dict[str, Any], history: List[Dict[str, Any]]) -> str:
        context = self._build_context(analysis)
        cleaned_history = self._normalise_history(history)
        last_user_message = next((msg["content"] for msg in reversed(cleaned_history) if msg["role"] == "user"), None)

        if last_user_message is None:
            prompt = self._build_intro_prompt(context)
        else:
            prompt = self._build_chat_prompt(context, cleaned_history, last_user_message)

        response = self._model.generate_content(prompt, generation_config=self._config)
        text = self._extract_text(response)
        cleaned = text.strip()
        if not cleaned:
            return (
                "I wasn't able to retrieve an answer from the memo context just yet. "
                "Please try asking again in a moment or review the memo details manually."
            )
        return self._post_process(cleaned)

    def _build_intro_prompt(self, context: str) -> str:
        return (
            "You are an AI venture analyst assisting investors.\n"
            "Offer a natural welcome that surfaces the most material diligence insights without artificial brevity.\n"
            "Ensure the greeting feels complete and resolves every idea before finishing.\n"
            "Respond in fluid prose, using paragraphs when appropriate, and ensure critical metrics, financial figures, or traction numbers are wrapped in **_double-emphasis_** markdown.\n"
            "Close by suggesting one diligence avenue the investor could pursue next.\n\n"
            f"Startup dossier:\n{context if context else 'No structured memo available.'}"
        )

    def _build_chat_prompt(
        self, context: str, history: List[Dict[str, str]], last_user_message: str
    ) -> str:
        formatted_history = self._format_history(history)
        return (
            "You are an AI venture analyst assisting investors."
            " Answer the user's latest question using only the provided startup dossier."
            " Treat the user as an investor completing diligence; do not address them as the founder or a member of the startup team."
            " If the dossier lacks the requested data, state that it is unavailable instead of guessing."
            " Deliver a natural, thorough reply that stays focused on the user's request without enforcing a strict length limit."
            " Provide full context rather than partial lists, and complete your final sentence."
            " Highlight critical metrics or numbers by wrapping them in **_double-emphasis_** markdown."
            " You may end with one succinct follow-up question when helpful.\n\n"
            f"Startup dossier:\n{context if context else 'No structured memo available.'}\n\n"
            "Conversation so far (oldest to newest):\n"
            f"{formatted_history if formatted_history else 'No prior dialogue.'}\n\n"
            f"Respond to the final user question: {last_user_message}"
        )

    def _normalise_history(self, history: Iterable[Dict[str, Any]]) -> List[Dict[str, str]]:
        normalised: List[Dict[str, str]] = []
        for raw in history:
            role = str(raw.get("role", "user"))
            content = str(raw.get("content", "")).strip()
            if not content:
                continue
            if role not in {"user", "assistant"}:
                role = "assistant" if role != "user" else "user"
            normalised.append({"role": role, "content": content})
        # Only keep the last 12 turns to control prompt size
        return normalised[-12:]

    def _format_history(self, history: Iterable[Dict[str, str]]) -> str:
        lines: List[str] = []
        for item in history:
            prefix = "USER" if item["role"] == "user" else "ANALYST"
            lines.append(f"{prefix}: {item['content']}")
        return "\n".join(lines)

    def _build_context(self, analysis: Dict[str, Any]) -> str:
        sections: List[str] = []

        metadata = analysis.get("metadata") or {}
        if isinstance(metadata, dict) and metadata:
            summaries = []
            name = metadata.get("display_name") or metadata.get("company_name")
            if name:
                summaries.append(f"Name: {name}")
            if metadata.get("product_name"):
                summaries.append(f"Product: {metadata['product_name']}")
            if metadata.get("sector"):
                summaries.append(f"Sector: {metadata['sector']}")
            founders = metadata.get("founder_names")
            if isinstance(founders, list) and founders:
                summaries.append(f"Founders: {', '.join(str(item) for item in founders)}")
            if summaries:
                sections.append("Metadata:\n" + "\n".join(summaries))

        memo = analysis.get("memo") or {}
        if isinstance(memo, dict):
            memo_payload = memo.get("draft_v1") if isinstance(memo.get("draft_v1"), dict) else memo
            sections.extend(self._extract_memo_sections(memo_payload))

        public_data = analysis.get("public_data")
        if isinstance(public_data, dict) and public_data:
            sections.append("Public data insights:\n" + self._stringify(public_data))

        risk = analysis.get("risk_assessment") or analysis.get("risk_metrics")
        if isinstance(risk, dict) and risk:
            sections.append("Risk assessment:\n" + self._stringify(risk))

        return "\n\n".join(sections)

    def _post_process(self, text: str) -> str:
        """Lightly normalise model output and ensure important numbers are highlighted."""

        stripped = text.strip()
        if not stripped:
            return text

        return self._ensure_highlight(stripped)

    def _extract_text(self, response: Any) -> str:
        """Extract raw text from a Vertex AI response object."""

        text = getattr(response, "text", "")
        if isinstance(text, str) and text.strip():
            return text

        candidates = getattr(response, "candidates", None)
        if not candidates:
            return text if isinstance(text, str) else ""

        chunks: List[str] = []
        for candidate in candidates:
            content = getattr(candidate, "content", None)
            parts = getattr(content, "parts", []) if content else []
            for part in parts:
                part_text = getattr(part, "text", None)
                if isinstance(part_text, str):
                    chunks.append(part_text)
        joined = "".join(chunks)
        return joined or (text if isinstance(text, str) else "")

    @staticmethod
    def _ensure_highlight(text: str) -> str:
        if "**_" in text:
            return text

        lines = text.split("\n")
        for line_index, line in enumerate(lines):
            tokens = line.split()
            for token_index, token in enumerate(tokens):
                cleaned = token.strip(",;:.")
                if any(ch.isdigit() for ch in cleaned):
                    tokens[token_index] = token.replace(cleaned, f"**_{cleaned}_**")
                    lines[line_index] = " ".join(tokens)
                    return "\n".join(lines)
        return text

    def _extract_memo_sections(self, memo: Optional[Dict[str, Any]]) -> List[str]:
        if not isinstance(memo, dict):
            return []

        ordered_keys = [
            ("company_overview", "Company overview"),
            ("market_analysis", "Market analysis"),
            ("business_model", "Business model"),
            ("financials", "Financials"),
            ("claims_analysis", "Claims analysis"),
            ("risk_metrics", "Risk metrics"),
        ]
        sections: List[str] = []
        for key, label in ordered_keys:
            value = memo.get(key)
            if value:
                sections.append(f"{label}:\n{self._stringify(value)}")
        return sections

    @staticmethod
    def _stringify(value: Any) -> str:
        if isinstance(value, str):
            return value
        try:
            return json.dumps(value, ensure_ascii=False, indent=2, default=str)
        except TypeError:
            return str(value)
