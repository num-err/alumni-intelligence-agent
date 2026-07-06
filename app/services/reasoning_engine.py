"""High-level orchestration for reasoning over one student's search evidence.

Builds the prompt, checks the Claude response cache, and calls Claude only
on a cache miss. This is what the enrichment pipeline (later milestones)
calls -- it never talks to Tavily.
"""

from collections.abc import Callable

import anthropic
from sqlalchemy.orm import Session

from app.models.alumni import AlumniRecord
from app.services.claude_cache_service import get_cached_response, store_response
from app.services.claude_client import ClaudeClient
from app.services.claude_types import ClaudeEnrichment
from app.services.prompt_builder import build_system_prompt, build_user_prompt
from app.services.search_types import SearchResult
from config import get_settings

# Balanced choice for a high-volume, per-record reasoning task: strong
# enough to avoid hallucinating identity matches, far cheaper than Opus at
# the scale of a 1,000+ row roster. See claude-api skill model table for
# current pricing ($3/$15 per 1M tokens, $2/$10 intro through 2026-08-31).
CLAUDE_MODEL = "claude-sonnet-5"


async def reason_about_student(
    db: Session,
    async_client: anthropic.AsyncAnthropic,
    record: AlumniRecord,
    evidence: list[SearchResult],
    on_request: Callable[[], None] | None = None,
) -> ClaudeEnrichment:
    """Ask Claude to verify/extract fields for `record` from `evidence`.

    `on_request`, if given, is called once per actual Claude call (never on
    a cache hit) -- used by the dashboard's API-request counter.
    """
    user_prompt = build_user_prompt(record, evidence)

    cached = get_cached_response(db, CLAUDE_MODEL, user_prompt)
    if cached is not None:
        return cached

    settings = get_settings()
    client = ClaudeClient(async_client, model=CLAUDE_MODEL, retries=settings.retry_count)
    result = await client.enrich(system=build_system_prompt(), user_prompt=user_prompt, on_request=on_request)

    store_response(db, CLAUDE_MODEL, user_prompt, result)
    return result
