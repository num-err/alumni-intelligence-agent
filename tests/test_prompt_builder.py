from app.models.alumni import AlumniRecord
from app.services.prompt_builder import build_user_prompt
from app.services.search_types import SearchResult


def test_prompt_includes_student_name_and_known_values():
    record = AlumniRecord(
        first_name="Jane",
        last_name="Doe",
        email=None,
        linkedin=None,
        graduation_year="2020",
        country="Kenya",
        city=None,
    )

    prompt = build_user_prompt(record, [])

    assert "Student name: Jane Doe" in prompt
    assert "Graduation Year: 2020" in prompt
    assert "Country: Kenya" in prompt
    assert "Email: unknown" in prompt


def test_prompt_includes_evidence_snippets():
    record = AlumniRecord(first_name="Jane", last_name="Doe")
    results = [
        SearchResult(title="Jane Doe LinkedIn", url="https://linkedin.com/in/janedoe", content="CEO at Acme", score=0.9, source_query="q"),
    ]

    prompt = build_user_prompt(record, results)

    assert "Jane Doe LinkedIn" in prompt
    assert "https://linkedin.com/in/janedoe" in prompt
    assert "CEO at Acme" in prompt


def test_prompt_handles_no_evidence():
    record = AlumniRecord(first_name="Jane", last_name="Doe")

    prompt = build_user_prompt(record, [])

    assert "no search results were found" in prompt
