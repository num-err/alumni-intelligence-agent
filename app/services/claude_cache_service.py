"""SQLite-backed cache for Claude enrichment responses.

Keyed by a hash of the exact prompt sent to Claude (model + user prompt,
which fully encodes the student's known values and evidence), so an
identical enrichment request is never billed twice.
"""

import datetime
import hashlib

from sqlalchemy.orm import Session

from app.models.cache import ClaudeResponseCache
from app.services.claude_types import ClaudeEnrichment
from config import get_settings


def _hash_prompt(model: str, user_prompt: str) -> str:
    normalized = f"{model}\n{user_prompt.strip()}"
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def get_cached_response(db: Session, model: str, user_prompt: str) -> ClaudeEnrichment | None:
    """Return the cached enrichment for this exact prompt, or None if missing/expired."""
    settings = get_settings()
    cached = db.query(ClaudeResponseCache).filter_by(prompt_hash=_hash_prompt(model, user_prompt)).first()
    if cached is None:
        return None

    created_at = cached.created_at.replace(tzinfo=datetime.timezone.utc)
    age = datetime.datetime.now(datetime.timezone.utc) - created_at
    if age.days >= settings.cache_expiration_days:
        return None

    return ClaudeEnrichment.from_dict(cached.response)


def store_response(db: Session, model: str, user_prompt: str, response: ClaudeEnrichment) -> None:
    """Insert or refresh the cache entry for this exact prompt."""
    prompt_hash = _hash_prompt(model, user_prompt)
    cached = db.query(ClaudeResponseCache).filter_by(prompt_hash=prompt_hash).first()
    payload = response.to_dict()

    if cached is None:
        db.add(ClaudeResponseCache(prompt_hash=prompt_hash, response=payload))
    else:
        cached.response = payload
        cached.created_at = datetime.datetime.now(datetime.timezone.utc)

    db.commit()
