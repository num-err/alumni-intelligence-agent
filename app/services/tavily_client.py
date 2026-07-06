"""Thin async client for the Tavily Search REST API.

Tavily is the only search backend the app talks to -- Google is never
scraped directly. This module owns the HTTP call and retry behavior; query
generation lives in `query_builder.py` and result merging/ranking lives in
`search_engine.py`.
"""

from collections.abc import Callable

import aiohttp

from app.services.errors import SearchError
from app.services.retry import retry_with_backoff
from app.services.search_types import SearchResult

TAVILY_SEARCH_URL = "https://api.tavily.com/search"


class TavilyClient:
    def __init__(self, api_key: str, retries: int = 3, timeout_seconds: float = 20.0):
        self._api_key = api_key
        self._retries = retries
        self._timeout = aiohttp.ClientTimeout(total=timeout_seconds)

    async def search(
        self,
        session: aiohttp.ClientSession,
        query: str,
        max_results: int = 5,
        on_request: Callable[[], None] | None = None,
    ) -> list[SearchResult]:
        """Run one search query against Tavily, retrying with backoff on failure.

        `on_request`, if given, is called once per actual HTTP attempt
        (including retries) -- used by the dashboard's API-request counter.
        """
        if not self._api_key:
            raise SearchError("TAVILY_API_KEY is not configured.")

        async def _call() -> list[SearchResult]:
            if on_request is not None:
                on_request()

            payload = {
                "api_key": self._api_key,
                "query": query,
                "max_results": max_results,
                "search_depth": "basic",
                "include_answer": False,
            }
            async with session.post(TAVILY_SEARCH_URL, json=payload, timeout=self._timeout) as response:
                body_text = await response.text()
                if response.status != 200:
                    raise SearchError(f"Tavily returned HTTP {response.status}: {body_text[:200]}")
                data = await response.json(content_type=None)

            return [
                SearchResult(
                    title=item.get("title") or "",
                    url=item.get("url") or "",
                    content=item.get("content") or "",
                    score=float(item.get("score") or 0.0),
                    source_query=query,
                )
                for item in data.get("results", [])
                if item.get("url")
            ]

        return await retry_with_backoff(_call, retries=self._retries, label=f"Tavily search '{query}'")
