"""Turns a validated Claude enrichment into a concrete write decision.

Applies the confidence-tier rules (95+ auto-write, [confidence_threshold,95)
medium-confidence write, below confidence_threshold review queue) and the
never-downgrade rule: a field that already holds a value (whether from the
original spreadsheet or a prior enrichment pass) is only overwritten by a
95+-confidence ("auto" tier) result. Empty fields are always written per the
usual tier rules, even at low confidence -- they land in the review queue
flagged for a human rather than being silently skipped. The review threshold
(default 80) is the one exposed as a Setting; the 95+ auto-write bar is a
fixed rule.

Email is a special case: an address at the institution's own domain
(`settings.stale_email_domain`, e.g. alumni accounts) often stops working
after graduation, so a missing email or one at that domain is treated as
needing enrichment, but any other existing email is assumed to already be
the "better" one and is left alone regardless of confidence.

When a `hunter_email_service.EmailResolution` is supplied (Hunter.io was
consulted because the email needed enrichment), its verified email bypasses
the usual "already filled" tier gate -- Hunter's deliverability check is an
independent signal about the email specifically, decoupled from Claude's
overall confidence about the rest of the record. If Hunter was consulted
but couldn't verify anything, the email field is dropped entirely rather
than falling back to an unverified Claude guess.
"""

import datetime
from dataclasses import dataclass

from app.models.alumni import AlumniRecord
from app.services.claude_types import ClaudeEnrichment
from app.services.evidence_service import build_evidence
from app.services.hunter_email_service import EmailResolution
from app.services.validation_service import validate_enrichment
from config import get_settings

AUTO_WRITE_THRESHOLD = 95

# validated-enrichment field name -> AlumniRecord field name
FIELD_MAP = {
    "linkedin": "linkedin",
    "email": "public_email",
    "graduation_year": "graduation_year",
    "country_origin": "country_origin",
    "current_location": "current_location",
    "current_employer": "current_employer",
}


def _email_needs_enrichment(current_email: str | None) -> bool:
    """A missing email, or one at the configured stale domain, is worth replacing."""
    normalized = (current_email or "").strip().lower()
    if not normalized:
        return True
    stale_domain = get_settings().stale_email_domain.strip().lower().lstrip("@")
    if not stale_domain:
        return False
    return normalized.endswith(f"@{stale_domain}") or normalized.endswith(f".{stale_domain}")


@dataclass
class EnrichmentDecision:
    should_write: bool
    fields: dict[str, str]
    confidence: int
    review_required: bool
    confidence_tier: str
    evidence: list[str]


def _confidence_tier(confidence: int) -> tuple[str, bool]:
    review_threshold = get_settings().confidence_threshold
    if confidence >= AUTO_WRITE_THRESHOLD:
        return "auto", False
    if confidence >= review_threshold:
        return "medium", False
    return "review", True


def decide(
    record: AlumniRecord,
    enrichment: ClaudeEnrichment,
    email_resolution: EmailResolution | None = None,
) -> EnrichmentDecision:
    """Validate `enrichment` and decide what (if anything) to write to `record`."""
    validated = validate_enrichment(enrichment)
    tier, below_review_threshold = _confidence_tier(validated.confidence)
    review_required = below_review_threshold or enrichment.review_required

    email_needs_enrichment = _email_needs_enrichment(record.email)
    hunter_consulted = email_needs_enrichment and email_resolution is not None
    email_value = email_resolution.email if hunter_consulted else validated.email
    # Hunter's own deliverability check is an independent signal about the
    # email specifically -- let a verified result through regardless of
    # Claude's confidence about the rest of the record.
    email_bypasses_tier = hunter_consulted and email_resolution.hunter_verified

    source = {
        "linkedin": validated.linkedin,
        "email": email_value,
        "graduation_year": validated.graduation_year,
        "country_origin": validated.country_origin,
        "current_location": validated.current_location,
        "current_employer": validated.current_employer,
    }

    fields: dict[str, str] = {}
    for source_field, record_field in FIELD_MAP.items():
        new_value = source[source_field]
        if new_value is None:
            continue

        if source_field == "email" and not email_needs_enrichment:
            # Known email isn't missing or at the stale domain --
            # treat it as already correct and never replace it.
            continue

        existing_value = getattr(record, record_field)
        if existing_value and validated.confidence < AUTO_WRITE_THRESHOLD:
            if source_field == "email" and email_bypasses_tier:
                pass  # Hunter-verified email may still replace it
            else:
                # Field is already filled -- only a near-certain result may
                # correct it, otherwise leave existing data alone.
                continue

        fields[record_field] = new_value

    should_write = bool(fields)
    evidence = build_evidence(enrichment, validated, tier, should_write)

    return EnrichmentDecision(
        should_write=should_write,
        fields=fields,
        confidence=validated.confidence,
        review_required=review_required,
        confidence_tier=tier,
        evidence=evidence,
    )


def apply_decision(record: AlumniRecord, decision: EnrichmentDecision) -> None:
    """Mutate `record` in place according to a previously computed decision."""
    if decision.should_write:
        for field, value in decision.fields.items():
            setattr(record, field, value)
        record.confidence = decision.confidence
        record.last_updated = datetime.datetime.now(datetime.timezone.utc)

    record.evidence = decision.evidence
    record.review_required = decision.review_required
    record.processing_status = "completed"
