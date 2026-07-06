import pytest

from app.models.alumni import AlumniRecord
from app.services.query_builder import build_queries
from config import get_settings


@pytest.fixture(autouse=True)
def _institution_name(monkeypatch):
    """Pin the institution name so query assertions don't depend on the
    local .env file's real-world configuration."""
    get_settings.cache_clear()
    monkeypatch.setenv("INSTITUTION_NAME", "Test University")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_builds_core_queries_from_name_only():
    record = AlumniRecord(first_name="Jane", last_name="Doe")

    queries = build_queries(record)

    assert "Jane Doe Test University" in queries
    assert "Jane Doe LinkedIn" in queries
    assert "Jane Doe Test University Alumni" in queries
    assert "Jane Doe site:linkedin.com" in queries
    # no year/country supplied, so those variants shouldn't appear
    assert not any("2020" in q for q in queries)


def test_adds_year_and_country_queries_when_known():
    record = AlumniRecord(first_name="Jane", last_name="Doe", graduation_year="2020", country="Kenya")

    queries = build_queries(record)

    assert "Jane Doe Test University 2020" in queries
    assert "Jane Doe Kenya" in queries


def test_no_duplicate_queries():
    record = AlumniRecord(first_name="Jane", last_name="Doe")

    queries = build_queries(record)

    assert len(queries) == len(set(q.lower() for q in queries))


def test_empty_name_produces_no_queries():
    record = AlumniRecord(first_name=None, last_name=None)

    assert build_queries(record) == []


def test_adds_email_query_when_missing():
    record = AlumniRecord(first_name="Jane", last_name="Doe")

    queries = build_queries(record)

    assert "Jane Doe Test University email contact" in queries


def test_adds_email_query_when_known_email_is_stale_domain(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("STALE_EMAIL_DOMAIN", "test.edu")
    get_settings.cache_clear()
    try:
        record = AlumniRecord(first_name="Jane", last_name="Doe", email="jdoe1@test.edu")

        queries = build_queries(record)

        assert "Jane Doe Test University email contact" in queries
    finally:
        get_settings.cache_clear()


def test_skips_email_query_when_known_email_is_not_stale():
    record = AlumniRecord(first_name="Jane", last_name="Doe", email="jane@company.com")

    queries = build_queries(record)

    assert not any("email contact" in q for q in queries)
