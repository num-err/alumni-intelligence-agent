"""High-level search orchestration for one alumnus.

Builds multiple queries for a student, checks the cache before hitting
Tavily, merges results across all queries, removes duplicate URLs, and
ranks by relevance. This is what the enrichment pipeline (later
milestones) calls -- it never talks to Claude.
"""

import logging
from collections.abc import Callable

import aiohttp
from sqlalchemy.orm import Session

from app.models.alumni import AlumniRecord
from app.services.query_builder import build_queries
from app.services.search_cache_service import get_cached_results, store_results
from app.services.search_types import SearchResult
from app.services.tavily_client import TavilyClient
from config import get_settings

logger = logging.getLogger("alumni_agent")

MAX_RESULTS_PER_QUERY = 5
MAX_MERGED_RESULTS = 15


def _normalize_url(url: str) -> str:
    return url.strip().rstrip("/").lower()


def merge_and_rank(results: list[SearchResult], limit: int = MAX_MERGED_RESULTS) -> list[SearchResult]:
    """Deduplicate by URL (keeping the highest-scoring copy) and rank by score."""
    best_by_url: dict[str, SearchResult] = {}
    for result in results:
        if not result.url:
            continue
        key = _normalize_url(result.url)
        existing = best_by_url.get(key)
        if existing is None or result.score > existing.score:
            best_by_url[key] = result

    ranked = sorted(best_by_url.values(), key=lambda r: r.score, reverse=True)
    return ranked[:limit]


async def gather_evidence(
    db: Session,
    session: aiohttp.ClientSession,
    record: AlumniRecord,
    on_request: Callable[[], None] | None = None,
) -> list[SearchResult]:
    """Run every discovery query for `record`, merged and ranked.

    Uses the SQLite cache wherever possible so identical queries are never
    sent to Tavily twice. `on_request`, if given, is called once per actual
    Tavily call (never on a cache hit) -- used by the dashboard's
    API-request counter.
    """
    settings = get_settings()
    client = TavilyClient(api_key=settings.tavily_api_key, retries=settings.retry_count)

    all_results: list[SearchResult] = []
    for query in build_queries(record):
        cached = get_cached_results(db, query)
        if cached is not None:
            logger.debug("Cache hit for query %r", query)
            all_results.extend(cached)
            continue

        results = await client.search(session, query, max_results=MAX_RESULTS_PER_QUERY, on_request=on_request)
        store_results(db, query, results)
        all_results.extend(results)

    return merge_and_rank(all_results)
