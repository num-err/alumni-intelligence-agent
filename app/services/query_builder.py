"""Builds the set of search queries used to research one alumnus.

A single search is never enough to confidently identify a person, so this
module fans a student out into several differently-angled queries. Results
from all of them are merged and ranked later in `search_engine.py`.
"""

from app.models.alumni import AlumniRecord
from app.services.decision_engine import _email_needs_enrichment
from config import get_settings


def build_queries(record: AlumniRecord) -> list[str]:
    """Return an ordered, deduplicated list of search queries for a student.

    Queries always include the core identity searches (name + institution,
    LinkedIn). Queries that depend on optional spreadsheet data (graduation
    year, country) are only added when that data is known.
    """
    name = " ".join(part for part in (record.first_name, record.last_name) if part).strip()
    if not name:
        return []

    school_name = get_settings().institution_name

    queries = [
        f"{name} {school_name}",
        f"{name} LinkedIn",
        f"{name} {school_name} Alumni",
        f"{name} site:linkedin.com",
        f"{name} professional profile",
    ]

    if record.graduation_year:
        queries.append(f"{name} {school_name} {record.graduation_year}")

    if record.country:
        queries.append(f"{name} {record.country}")

    # Only spend a query hunting for an email when the known one needs it
    # (missing, or at the institution's stale/alumni domain).
    if _email_needs_enrichment(record.email):
        queries.append(f"{name} {school_name} email contact")

    # de-duplicate while preserving order (case-insensitive)
    seen: set[str] = set()
    unique_queries: list[str] = []
    for query in queries:
        key = query.lower()
        if key not in seen:
            seen.add(key)
            unique_queries.append(query)

    return unique_queries
