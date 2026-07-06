"""Maps arbitrary spreadsheet header text to canonical alumni-record fields.

Spreadsheets arrive with inconsistent header spelling ("Grad Year" vs
"Graduation Year" vs "Class Year"). This module is the single place that
knows the alias vocabulary, so the reader and any future re-import logic
stay in sync.
"""

import re

# Columns expected to already exist on the incoming spreadsheet.
EXISTING_FIELDS = [
    "first_name",
    "last_name",
    "email",
    "linkedin",
    "graduation_year",
    "country",
    "city",
]

# Columns the enrichment pipeline is responsible for populating.
NEW_FIELDS = [
    "public_email",
    "country_origin",
    "current_location",
    "confidence",
    "evidence",
    "processing_status",
    "review_required",
    "last_updated",
]

CANONICAL_FIELDS = EXISTING_FIELDS + NEW_FIELDS

_ALIASES: dict[str, str] = {
    "first name": "first_name",
    "firstname": "first_name",
    "given name": "first_name",
    "last name": "last_name",
    "lastname": "last_name",
    "surname": "last_name",
    "family name": "last_name",
    "email": "email",
    "e mail": "email",
    "email address": "email",
    "linkedin": "linkedin",
    "linkedin url": "linkedin",
    "linkedin profile": "linkedin",
    "graduation year": "graduation_year",
    "grad year": "graduation_year",
    "class year": "graduation_year",
    "year": "graduation_year",
    "country": "country",
    "home country": "country",
    "city": "city",
    "home city": "city",
    "public email": "public_email",
    "public email address": "public_email",
    "country of origin": "country_origin",
    "current location": "current_location",
    "location": "current_location",
    "city/location": "current_location",
    "city location": "current_location",
    "confidence": "confidence",
    "evidence": "evidence",
    "processing status": "processing_status",
    "status": "processing_status",
    "review required": "review_required",
    "needs review": "review_required",
    "last updated": "last_updated",
    "updated at": "last_updated",
}


def normalize_header(header: str) -> str:
    """Lowercase and collapse whitespace/underscores/dashes for alias lookup."""
    header = header.strip().lower()
    return re.sub(r"[\s_\-]+", " ", header)


def detect_column(header: str) -> str | None:
    """Return the canonical field name for a spreadsheet header, or None."""
    return _ALIASES.get(normalize_header(header))
