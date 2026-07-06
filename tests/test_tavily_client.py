import aiohttp
import pytest
from aioresponses import aioresponses

from app.services.errors import SearchError
from app.services.tavily_client import TAVILY_SEARCH_URL, TavilyClient


@pytest.mark.asyncio
async def test_search_parses_results():
    client = TavilyClient(api_key="fake-key", retries=0)
    payload = {
        "results": [
            {"title": "Jane Doe LinkedIn", "url": "https://linkedin.com/in/janedoe", "content": "snippet", "score": 0.9},
            {"title": "No URL", "content": "should be dropped"},
        ]
    }

    with aioresponses() as mocked:
        mocked.post(TAVILY_SEARCH_URL, payload=payload)
        async with aiohttp.ClientSession() as session:
            results = await client.search(session, "Jane Doe State University")

    assert len(results) == 1
    assert results[0].url == "https://linkedin.com/in/janedoe"
    assert results[0].score == 0.9
    assert results[0].source_query == "Jane Doe State University"


@pytest.mark.asyncio
async def test_missing_api_key_raises_without_calling_network():
    client = TavilyClient(api_key="", retries=0)

    async with aiohttp.ClientSession() as session:
        with pytest.raises(SearchError):
            await client.search(session, "Jane Doe")


@pytest.mark.asyncio
async def test_retries_then_succeeds():
    client = TavilyClient(api_key="fake-key", retries=2)
    payload = {"results": [{"title": "t", "url": "https://a.com", "content": "c", "score": 0.5}]}

    with aioresponses() as mocked:
        mocked.post(TAVILY_SEARCH_URL, status=500)
        mocked.post(TAVILY_SEARCH_URL, payload=payload)
        async with aiohttp.ClientSession() as session:
            results = await client.search(session, "Jane Doe")

    assert len(results) == 1


@pytest.mark.asyncio
async def test_exhausts_retries_and_raises():
    client = TavilyClient(api_key="fake-key", retries=1)

    with aioresponses() as mocked:
        mocked.post(TAVILY_SEARCH_URL, status=500)
        mocked.post(TAVILY_SEARCH_URL, status=500)
        async with aiohttp.ClientSession() as session:
            with pytest.raises(SearchError):
                await client.search(session, "Jane Doe")


@pytest.mark.asyncio
async def test_on_request_called_once_per_attempt_including_retries():
    client = TavilyClient(api_key="fake-key", retries=1)
    payload = {"results": [{"title": "t", "url": "https://a.com", "content": "c", "score": 0.5}]}
    calls = []

    with aioresponses() as mocked:
        mocked.post(TAVILY_SEARCH_URL, status=500)
        mocked.post(TAVILY_SEARCH_URL, payload=payload)
        async with aiohttp.ClientSession() as session:
            await client.search(session, "Jane Doe", on_request=lambda: calls.append(1))

    assert len(calls) == 2  # one failed attempt + one successful retry
