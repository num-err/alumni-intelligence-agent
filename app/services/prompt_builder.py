"""Builds the prompt Claude uses to reason over search evidence for one student.

Claude never searches -- it only reasons over evidence already gathered by
`search_engine.py`. This module is the single place that knows how that
evidence is formatted into a prompt.
"""

from app.models.alumni import AlumniRecord
from app.services.search_types import SearchResult
from config import get_settings


def build_system_prompt() -> str:
    institution = get_settings().institution_name
    return f"""You are a careful research analyst verifying facts about a {institution} \
alumnus using web search evidence that has already been gathered for you.

Rules:
- You do not search the web yourself. Only reason over the evidence provided below.
- Never hallucinate. If the evidence does not clearly support a field, set it to null.
- Only report a fact as fitting if the evidence specifically supports it for this \
exact person (matching name AND context, e.g. {institution}, graduation year, \
or location) -- not a same-named person at a different school or company.
- confidence is an integer 0-100 reflecting how certain you are that every non-null \
field is correct for this specific person.
- evidence must list short quotes or paraphrases, in your own words, from the \
provided search results that justify your answer.
- review_required must be true whenever confidence is below 80, or whenever you are \
not confident this is the same person as the one in the spreadsheet.
- If the known Email is already something other than a stale/missing address, treat \
it as already correct: set email to that same known value rather than searching for a \
replacement. Only report a different email when the known one is missing or is at the \
institution's own domain (those often stop working after graduation).
- current_employer is the name of the organization/company this person currently works \
for, if the evidence clearly supports one -- this is used to look up a work email, so \
report the employer even if you cannot find an email yourself.
- reason is a one-sentence explanation of your overall conclusion.
- Respond with JSON only, matching the required schema exactly."""


def _known_values(record: AlumniRecord) -> str:
    fields = {
        "First Name": record.first_name,
        "Last Name": record.last_name,
        "Email": record.email,
        "LinkedIn": record.linkedin,
        "Graduation Year": record.graduation_year,
        "Country": record.country,
        "City": record.city,
    }
    return "\n".join(f"- {label}: {value or 'unknown'}" for label, value in fields.items())


def _evidence_block(results: list[SearchResult]) -> str:
    if not results:
        return "(no search results were found)"

    blocks = [
        f"[{index}] {result.title}\nURL: {result.url}\nSnippet: {result.content}"
        for index, result in enumerate(results, start=1)
    ]
    return "\n\n".join(blocks)


def build_user_prompt(record: AlumniRecord, results: list[SearchResult]) -> str:
    """Assemble the user-turn prompt: student identity, known data, evidence."""
    name = " ".join(part for part in (record.first_name, record.last_name) if part).strip()
    return (
        f"Student name: {name}\n\n"
        f"Known spreadsheet values:\n{_known_values(record)}\n\n"
        f"Top search results (ranked by relevance):\n{_evidence_block(results)}\n\n"
        "Based only on the evidence above, fill in the JSON schema for this student."
    )
