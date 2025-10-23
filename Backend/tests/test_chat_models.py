import json

import pytest
from pydantic import ValidationError

from models.schemas import ChatRequest


def test_chat_request_parses_json_string() -> None:
    payload = ChatRequest(
        analysisData=json.dumps({"metadata": {"company_name": "Acme"}}),
        history=[{"role": "user", "content": "Hello"}],
    )

    assert payload.analysis_data["metadata"]["company_name"] == "Acme"
    assert payload.history[0].role == "user"


def test_chat_request_invalid_json() -> None:
    with pytest.raises(ValidationError):
        ChatRequest(analysisData="not-json", history=[])
