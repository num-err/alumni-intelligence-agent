"""Builds the human-readable evidence trail stored alongside each record.

Combines Claude's own evidence bullets with validation rejections and the
confidence-tier decision, so a reviewer can see exactly why a field was
(or wasn't) written without re-running the pipeline.
"""

from app.services.claude_types import ClaudeEnrichment
from app.services.validation_service import ValidatedEnrichment


def build_evidence(
    enrichment: ClaudeEnrichment,
    validated: ValidatedEnrichment,
    tier: str,
    should_write: bool,
) -> list[str]:
    evidence = list(enrichment.evidence)

    for rejection in validated.rejections:
        evidence.append(f"Validation rejected: {rejection}")

    evidence.append(f"Confidence {validated.confidence} classified as '{tier}' tier")

    if not should_write:
        evidence.append("Existing data kept: fields were already filled and not confidently corrected")

    return evidence
