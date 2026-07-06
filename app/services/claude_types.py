"""Data structures and JSON schema for Claude's evidence-reasoning output.

Claude is forced to answer in exactly this shape via `output_config.format`
(a JSON-schema-constrained response), so parsing here is just `json.loads`
-- no free-text extraction or markdown-fence stripping needed.
"""

import json
from dataclasses import asdict, dataclass

from app.services.errors import ClaudeReasoningError

# Mirrors the schema in the project spec exactly: linkedin, email,
# graduation_year, country_origin, current_location, current_employer,
# confidence, evidence, review_required, reason. Unknown fields must be
# null, never omitted. current_employer is not written to the spreadsheet
# directly -- it exists so Hunter.io's Email Finder (which needs a company
# name/domain) has something to query when the known email needs replacing.
ENRICHMENT_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "linkedin": {"type": ["string", "null"]},
        "email": {"type": ["string", "null"]},
        "graduation_year": {"type": ["string", "null"]},
        "country_origin": {"type": ["string", "null"]},
        "current_location": {"type": ["string", "null"]},
        "current_employer": {"type": ["string", "null"]},
        "confidence": {"type": "integer"},
        "evidence": {"type": "array", "items": {"type": "string"}},
        "review_required": {"type": "boolean"},
        "reason": {"type": "string"},
    },
    "required": [
        "linkedin",
        "email",
        "graduation_year",
        "country_origin",
        "current_location",
        "current_employer",
        "confidence",
        "evidence",
        "review_required",
        "reason",
    ],
    "additionalProperties": False,
}


@dataclass
class ClaudeEnrichment:
    linkedin: str | None
    email: str | None
    graduation_year: str | None
    country_origin: str | None
    current_location: str | None
    current_employer: str | None
    confidence: int
    evidence: list[str]
    review_required: bool
    reason: str

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ClaudeEnrichment":
        return cls(
            linkedin=data.get("linkedin"),
            email=data.get("email"),
            graduation_year=data.get("graduation_year"),
            country_origin=data.get("country_origin"),
            current_location=data.get("current_location"),
            current_employer=data.get("current_employer"),
            confidence=int(data.get("confidence", 0)),
            evidence=list(data.get("evidence") or []),
            review_required=bool(data.get("review_required", False)),
            reason=data.get("reason", ""),
        )


def parse_enrichment(text: str) -> ClaudeEnrichment:
    """Parse Claude's JSON-schema-constrained text response."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ClaudeReasoningError(f"Claude response was not valid JSON: {exc}") from exc

    return ClaudeEnrichment.from_dict(data)
