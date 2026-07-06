"""Business logic for the manual review queue.

Rows land here when the automated pipeline's confidence was too low, or
Claude itself asked for review (see `decision_engine.py`). A human
reviewer approves, rejects, or manually edits each one.
"""

import datetime

from app.models.alumni import AlumniRecord
from app.services.validators import (
    validate_email,
    validate_graduation_year,
    validate_linkedin,
    validate_location,
)


def approve(record: AlumniRecord) -> None:
    """Confirm the currently staged candidate data is correct."""
    record.confidence = 100
    record.review_required = False
    record.evidence = [*record.evidence, "Manually approved by reviewer."]
    record.last_updated = datetime.datetime.now(datetime.timezone.utc)


def reject(record: AlumniRecord) -> None:
    """Discard the staged enrichment data for this row."""
    record.linkedin = None
    record.public_email = None
    record.graduation_year = None
    record.country_origin = None
    record.current_location = None
    record.confidence = None
    record.review_required = False
    record.evidence = [*record.evidence, "Manually rejected by reviewer; enrichment data discarded."]
    record.last_updated = datetime.datetime.now(datetime.timezone.utc)


def edit(record: AlumniRecord, updates: dict[str, str]) -> list[str]:
    """Apply manually-entered field values, after validating each one.

    Returns a list of validation error messages. If empty, the edit was
    applied and the record marked resolved; otherwise `record` is left
    untouched so the caller can re-show the form with the errors.
    """
    validators = {
        "linkedin": validate_linkedin,
        "public_email": validate_email,
        "graduation_year": validate_graduation_year,
        "country_origin": lambda v: validate_location(v, "country_origin"),
        "current_location": lambda v: validate_location(v, "current_location"),
    }

    errors: list[str] = []
    cleaned: dict[str, str | None] = {}
    for field, raw_value in updates.items():
        result = validators[field](raw_value)
        if result.rejected:
            errors.append(result.reason or f"Invalid value for {field}")
        else:
            cleaned[field] = result.value

    if errors:
        return errors

    for field, value in cleaned.items():
        setattr(record, field, value)

    record.confidence = 100
    record.review_required = False
    record.evidence = [*record.evidence, "Manually edited by reviewer."]
    record.last_updated = datetime.datetime.now(datetime.timezone.utc)
    return []
