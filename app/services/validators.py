"""Field-level validators for Claude's enrichment output.

Claude's output is never trusted blindly -- each field must pass a
structural sanity check before it's allowed to reach the spreadsheet.
A field that fails validation is dropped (set to None) rather than
rejecting the whole response, so one bad field doesn't discard an
otherwise-good enrichment.
"""

import datetime
import re
from dataclasses import dataclass

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
LOCATION_PATTERN = re.compile(r"^[A-Za-z .,'\-]+$")
EMPLOYER_PATTERN = re.compile(r"^[A-Za-z0-9 .,'&\-]+$")

MIN_GRADUATION_YEAR = 1900
MAX_GRADUATION_YEAR_OFFSET = 10  # allow a bit into the future for current students


@dataclass
class FieldValidation:
    value: str | None
    rejected: bool
    reason: str | None = None


def validate_linkedin(value: str | None) -> FieldValidation:
    if not value:
        return FieldValidation(None, rejected=False)
    if "linkedin.com" not in value.lower():
        return FieldValidation(
            None, rejected=True, reason=f"linkedin value {value!r} does not contain linkedin.com"
        )
    return FieldValidation(value.strip(), rejected=False)


def validate_email(value: str | None) -> FieldValidation:
    if not value:
        return FieldValidation(None, rejected=False)
    if not EMAIL_PATTERN.match(value.strip()):
        return FieldValidation(None, rejected=True, reason=f"email value {value!r} is not a valid email address")
    return FieldValidation(value.strip(), rejected=False)


def validate_graduation_year(value: str | None) -> FieldValidation:
    if not value:
        return FieldValidation(None, rejected=False)
    text = str(value).strip()
    if not re.fullmatch(r"\d{4}", text):
        return FieldValidation(None, rejected=True, reason=f"graduation year {value!r} is not a 4-digit year")

    year = int(text)
    max_year = datetime.datetime.now().year + MAX_GRADUATION_YEAR_OFFSET
    if not (MIN_GRADUATION_YEAR <= year <= max_year):
        return FieldValidation(
            None,
            rejected=True,
            reason=f"graduation year {year} is outside the reasonable range {MIN_GRADUATION_YEAR}-{max_year}",
        )
    return FieldValidation(text, rejected=False)


def validate_location(value: str | None, field_name: str = "location") -> FieldValidation:
    if not value:
        return FieldValidation(None, rejected=False)
    text = value.strip()
    if not (1 < len(text) <= 100):
        return FieldValidation(None, rejected=True, reason=f"{field_name} {value!r} has an unreasonable length")
    if not LOCATION_PATTERN.match(text):
        return FieldValidation(
            None, rejected=True, reason=f"{field_name} {value!r} contains unexpected characters"
        )
    return FieldValidation(text, rejected=False)


def validate_employer(value: str | None) -> FieldValidation:
    if not value:
        return FieldValidation(None, rejected=False)
    text = value.strip()
    if not (1 < len(text) <= 100):
        return FieldValidation(None, rejected=True, reason=f"employer {value!r} has an unreasonable length")
    if not EMPLOYER_PATTERN.match(text):
        return FieldValidation(None, rejected=True, reason=f"employer {value!r} contains unexpected characters")
    return FieldValidation(text, rejected=False)


def validate_confidence(value: int) -> int:
    """Clamp confidence to the valid 0-100 range."""
    return max(0, min(100, int(value)))
