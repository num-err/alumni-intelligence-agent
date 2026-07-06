import json

import pytest

from app.services.claude_types import ClaudeEnrichment, parse_enrichment
from app.services.errors import ClaudeReasoningError

VALID_PAYLOAD = {
    "linkedin": "https://linkedin.com/in/janedoe",
    "email": None,
    "graduation_year": "2020",
    "country_origin": None,
    "current_location": "New York, NY",
    "confidence": 92,
    "evidence": ["LinkedIn profile matches name and State University"],
    "review_required": False,
    "reason": "High-confidence LinkedIn match.",
}


def test_parses_valid_json_into_dataclass():
    result = parse_enrichment(json.dumps(VALID_PAYLOAD))

    assert isinstance(result, ClaudeEnrichment)
    assert result.linkedin == "https://linkedin.com/in/janedoe"
    assert result.email is None
    assert result.confidence == 92
    assert result.evidence == ["LinkedIn profile matches name and State University"]
    assert result.review_required is False


def test_invalid_json_raises_claude_reasoning_error():
    with pytest.raises(ClaudeReasoningError):
        parse_enrichment("not json")


def test_to_dict_and_from_dict_round_trip():
    result = parse_enrichment(json.dumps(VALID_PAYLOAD))
    round_tripped = ClaudeEnrichment.from_dict(result.to_dict())

    assert round_tripped == result
