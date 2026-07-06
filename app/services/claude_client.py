"""Thin async client for reasoning over evidence with Claude.

Claude never searches -- see `search_engine.py` for that. This module owns
the API call, JSON-schema enforcement (so parsing never has to guess at
format), and retry behavior.
"""

from collections.abc import Callable

import anthropic

from app.services.claude_types import ENRICHMENT_JSON_SCHEMA, ClaudeEnrichment, parse_enrichment
from app.services.errors import ClaudeReasoningError
from app.services.retry import retry_with_backoff

MAX_TOKENS = 4096


class ClaudeClient:
    def __init__(self, client: anthropic.AsyncAnthropic, model: str, retries: int = 3):
        self._client = client
        self._model = model
        self._retries = retries

    async def enrich(
        self, *, system: str, user_prompt: str, on_request: Callable[[], None] | None = None
    ) -> ClaudeEnrichment:
        """Send one evidence-reasoning request to Claude, retrying with backoff.

        `on_request`, if given, is called once per actual API attempt
        (including retries) -- used by the dashboard's API-request counter.
        """

        async def _call() -> ClaudeEnrichment:
            if on_request is not None:
                on_request()

            response = await self._client.messages.create(
                model=self._model,
                max_tokens=MAX_TOKENS,
                system=system,
                messages=[{"role": "user", "content": user_prompt}],
                output_config={"format": {"type": "json_schema", "schema": ENRICHMENT_JSON_SCHEMA}},
            )

            if response.stop_reason == "refusal":
                raise ClaudeReasoningError("Claude declined to respond (safety refusal)")

            text = next((block.text for block in response.content if block.type == "text"), None)
            if text is None:
                raise ClaudeReasoningError("Claude response contained no text content")

            return parse_enrichment(text)

        return await retry_with_backoff(_call, retries=self._retries, label="Claude enrichment")
