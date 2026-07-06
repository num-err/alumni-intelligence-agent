"""Validates a full Claude enrichment response, field by field.

Delegates to the per-field rules in `validators.py` and collects the
rejection reasons so they can be surfaced in the record's evidence trail.
"""

from dataclasses import dataclass

from app.services.claude_types import ClaudeEnrichment
from app.services.validators import (
    validate_confidence,
    validate_email,
    validate_employer,
    validate_graduation_year,
    validate_linkedin,
    validate_location,
)


@dataclass
class ValidatedEnrichment:
    linkedin: str | None
    email: str | None
    graduation_year: str | None
    country_origin: str | None
    current_location: str | None
    current_employer: str | None
    confidence: int
    rejections: list[str]


def validate_enrichment(enrichment: ClaudeEnrichment) -> ValidatedEnrichment:
    linkedin = validate_linkedin(enrichment.linkedin)
    email = validate_email(enrichment.email)
    graduation_year = validate_graduation_year(enrichment.graduation_year)
    country_origin = validate_location(enrichment.country_origin, "country_origin")
    current_location = validate_location(enrichment.current_location, "current_location")
    current_employer = validate_employer(enrichment.current_employer)

    rejections = [
        field.reason
        for field in (linkedin, email, graduation_year, country_origin, current_location, current_employer)
        if field.rejected and field.reason
    ]

    return ValidatedEnrichment(
        linkedin=linkedin.value,
        email=email.value,
        graduation_year=graduation_year.value,
        country_origin=country_origin.value,
        current_location=current_location.value,
        current_employer=current_employer.value,
        confidence=validate_confidence(enrichment.confidence),
        rejections=rejections,
    )
