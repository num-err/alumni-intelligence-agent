import datetime

from app.models.cache import SearchResultCache
from app.services.search_cache_service import get_cached_results, store_results
from app.services.search_types import SearchResult


def _result(url="https://a.com", score=0.5):
    return SearchResult(title="t", url=url, content="c", score=score, source_query="q")


def test_cache_miss_returns_none(db_session):
    assert get_cached_results(db_session, "unknown query") is None


def test_store_then_retrieve(db_session):
    store_results(db_session, "Jane Doe State University", [_result()])

    cached = get_cached_results(db_session, "Jane Doe State University")

    assert cached is not None
    assert cached[0].url == "https://a.com"


def test_query_normalization_is_case_and_whitespace_insensitive(db_session):
    store_results(db_session, "  Jane Doe State University  ", [_result()])

    cached = get_cached_results(db_session, "jane doe state university")

    assert cached is not None


def test_expired_entries_are_not_returned(db_session, monkeypatch):
    from config import get_settings

    store_results(db_session, "Jane Doe State University", [_result()])

    entry = db_session.query(SearchResultCache).first()
    entry.created_at = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(
        days=get_settings().cache_expiration_days + 1
    )
    db_session.commit()

    assert get_cached_results(db_session, "Jane Doe State University") is None


def test_storing_again_overwrites_existing_entry(db_session):
    store_results(db_session, "Jane Doe State University", [_result(url="https://old.com")])
    store_results(db_session, "Jane Doe State University", [_result(url="https://new.com")])

    cached = get_cached_results(db_session, "Jane Doe State University")

    assert len(cached) == 1
    assert cached[0].url == "https://new.com"
