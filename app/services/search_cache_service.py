"""SQLite-backed cache for Tavily search results.

Guarantees the app never calls Tavily twice for the same (normalized)
query, and expires entries after `settings.cache_expiration_days`.
"""

import datetime
import hashlib

from sqlalchemy.orm import Session

from app.models.cache import SearchResultCache
from app.services.search_types import SearchResult
from config import get_settings


def _hash_query(query: str) -> str:
    normalized = query.strip().lower()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def get_cached_results(db: Session, query: str) -> list[SearchResult] | None:
    """Return cached results for `query`, or None if missing/expired."""
    settings = get_settings()
    cached = db.query(SearchResultCache).filter_by(query_hash=_hash_query(query)).first()
    if cached is None:
        return None

    created_at = cached.created_at.replace(tzinfo=datetime.timezone.utc)
    age = datetime.datetime.now(datetime.timezone.utc) - created_at
    if age.days >= settings.cache_expiration_days:
        return None

    return [SearchResult.from_dict(item) for item in cached.results]


def store_results(db: Session, query: str, results: list[SearchResult]) -> None:
    """Insert or refresh the cache entry for `query`."""
    query_hash = _hash_query(query)
    cached = db.query(SearchResultCache).filter_by(query_hash=query_hash).first()
    payload = [result.to_dict() for result in results]

    if cached is None:
        db.add(SearchResultCache(query_hash=query_hash, query_text=query, results=payload))
    else:
        cached.results = payload
        cached.created_at = datetime.datetime.now(datetime.timezone.utc)

    db.commit()
