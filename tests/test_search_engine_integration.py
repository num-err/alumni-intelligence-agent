import aiohttp
import pytest
from aioresponses import aioresponses

from app.models.alumni import AlumniRecord
from app.services.search_cache_service import get_cached_results
from app.services.search_engine import gather_evidence
from app.services.tavily_client import TAVILY_SEARCH_URL
from config import get_settings


@pytest.mark.asyncio
async def test_gather_evidence_merges_across_queries_and_populates_cache(db_session, monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("TAVILY_API_KEY", "fake-key")
    monkeypatch.setenv("INSTITUTION_NAME", "Test University")
    get_settings.cache_clear()

    record = AlumniRecord(first_name="Jane", last_name="Doe")
    # build_queries(record) with no grad year/country/email yields 6 queries
    payload = {"results": [{"title": "Jane Doe", "url": "https://linkedin.com/in/janedoe", "content": "c", "score": 0.8}]}

    with aioresponses() as mocked:
        for _ in range(6):
            mocked.post(TAVILY_SEARCH_URL, payload=payload)
        async with aiohttp.ClientSession() as session:
            results = await gather_evidence(db_session, session, record)

    # all 5 queries returned the same URL, so merge_and_rank collapses to 1
    assert len(results) == 1
    assert results[0].url == "https://linkedin.com/in/janedoe"

    # every query should now be cached
    assert get_cached_results(db_session, "Jane Doe Test University") is not None

    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_gather_evidence_uses_cache_on_second_call(db_session, monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("TAVILY_API_KEY", "fake-key")
    get_settings.cache_clear()

    record = AlumniRecord(first_name="Jane", last_name="Doe")
    payload = {"results": [{"title": "Jane Doe", "url": "https://linkedin.com/in/janedoe", "content": "c", "score": 0.8}]}

    with aioresponses() as mocked:
        for _ in range(6):
            mocked.post(TAVILY_SEARCH_URL, payload=payload)
        async with aiohttp.ClientSession() as session:
            await gather_evidence(db_session, session, record)

    # second call: no mocked routes registered, so any real HTTP call would fail
    with aioresponses():
        async with aiohttp.ClientSession() as session:
            results = await gather_evidence(db_session, session, record)

    assert len(results) == 1

    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_on_request_called_only_for_actual_calls_not_cache_hits(db_session, monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("TAVILY_API_KEY", "fake-key")
    get_settings.cache_clear()

    record = AlumniRecord(first_name="Jane", last_name="Doe")
    payload = {"results": [{"title": "Jane Doe", "url": "https://linkedin.com/in/janedoe", "content": "c", "score": 0.8}]}
    calls = []

    with aioresponses() as mocked:
        for _ in range(6):
            mocked.post(TAVILY_SEARCH_URL, payload=payload)
        async with aiohttp.ClientSession() as session:
            await gather_evidence(db_session, session, record, on_request=lambda: calls.append(1))

    assert len(calls) == 6  # 6 queries, all cache misses on the first call

    calls.clear()
    with aioresponses():  # no routes registered -- a real call here would fail
        async with aiohttp.ClientSession() as session:
            await gather_evidence(db_session, session, record, on_request=lambda: calls.append(1))

    assert calls == []  # every query was a cache hit this time

    get_settings.cache_clear()
