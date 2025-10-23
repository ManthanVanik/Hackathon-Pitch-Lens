from pydantic import BaseModel, Field, field_validator
from typing import Optional, Dict, Any, List, Literal
import json
from datetime import datetime

class DealMetadata(BaseModel):
    deal_id: str
    # company_name: str
    status: str = "pending"
    created_at: datetime
    processed_at: Optional[datetime] = None
    error: Optional[str] = None
    company_name: Optional[str] = None
    company_legal_name: Optional[str] = None
    product_name: Optional[str] = None
    display_name: Optional[str] = None
    deck_hash: Optional[str] = None

class UserInput(BaseModel):
    qna: Optional[Dict[str, str]] = {}
    weightages: Optional[Dict[str, float]] = {
        "market": 0.4,
        "founder": 0.3,
        "team": 0.2,
        "traction": 0.1
    }
    
class Weightage(BaseModel):
    team_strength: int
    market_opportunity: int
    traction: int
    claim_credibility: int
    financial_health: int

class ProcessingStatus(BaseModel):
    deal_id: str
    status: str
    progress: Optional[str] = None
    error: Optional[str] = None

class MemoResponse(BaseModel):
    deal_id: str
    memo_text: Dict[str, Any]
    docx_url: str
    all_data: Optional[Dict[str, Any]] = None


class ChatMessage(BaseModel):
    role: Literal["user", "model", "assistant"]
    content: str


class ChatRequest(BaseModel):
    analysis_data: Dict[str, Any] = Field(default_factory=dict, alias="analysisData")
    history: List[ChatMessage] = Field(default_factory=list)

    model_config = {
        "populate_by_name": True,
        "extra": "ignore",
    }

    @field_validator("analysis_data", mode="before")
    @classmethod
    def _coerce_analysis_data(cls, value: Any) -> Dict[str, Any]:
        if value is None:
            return {}
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return {}
            try:
                parsed = json.loads(stripped)
            except json.JSONDecodeError as exc:  # pragma: no cover - pydantic will surface the error
                raise ValueError("analysisData must be valid JSON") from exc
            if isinstance(parsed, dict):
                return parsed
            raise ValueError("analysisData JSON must decode to an object")
        raise TypeError("analysisData must be a JSON object or string")


class ChatResponse(BaseModel):
    message: str
