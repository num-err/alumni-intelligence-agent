"""Thin async client for the Hunter.io REST API (Email Finder + Verifier).

Mirrors `tavily_client.py`'s shape: this module owns the HTTP call and
retry behavior only. Deciding when to call Hunter and what to do with the
result lives in `hunter_email_service.py`.
"""

from collections.abc import Callable
from dataclasses import dataclass

import aiohttp

from app.services.errors import HunterError
from app.services.retry import retry_with_backoff

HUNTER_FINDER_URL = "https://api.hunter.io/v2/email-finder"
HUNTER_VERIFIER_URL = "https://api.hunter.io/v2/email-verifier"


@dataclass
class HunterFinderResult:
    email: str | None
    score: int


@dataclass
class HunterVerifyResult:
    status: str
    score: int


class HunterClient:
    def __init__(self, api_key: str, retries: int = 3, timeout_seconds: float = 20.0):
        self._api_key = api_key
        self._retries = retries
        self._timeout = aiohttp.ClientTimeout(total=timeout_seconds)

    async def find_email(
        self,
        session: aiohttp.ClientSession,
        first_name: str,
        last_name: str,
        company: str,
        on_request: Callable[[], None] | None = None,
    ) -> HunterFinderResult | None:
        """Look up the most likely email for `first_name last_name` at `company`.

        Returns None if Hunter has no candidate (rather than raising), since
        "nobody found" is an expected, non-error outcome.
        """
        if not self._api_key:
            raise HunterError("HUNTER_API_KEY is not configured.")

        async def _call() -> HunterFinderResult | None:
            if on_request is not None:
                on_request()

            params = {
                "api_key": self._api_key,
                "first_name": first_name,
                "last_name": last_name,
                "company": company,
            }
            async with session.get(HUNTER_FINDER_URL, params=params, timeout=self._timeout) as response:
                body_text = await response.text()
                if response.status != 200:
                    raise HunterError(f"Hunter email-finder returned HTTP {response.status}: {body_text[:200]}")
                data = await response.json(content_type=None)

            result = data.get("data") or {}
            email = result.get("email")
            if not email:
                return None
            return HunterFinderResult(email=email, score=int(result.get("score") or 0))

        return await retry_with_backoff(
            _call, retries=self._retries, label=f"Hunter email-finder '{first_name} {last_name}' @ '{company}'"
        )

    async def verify_email(
        self,
        session: aiohttp.ClientSession,
        email: str,
        on_request: Callable[[], None] | None = None,
    ) -> HunterVerifyResult | None:
        """Check whether `email` is deliverable."""
        if not self._api_key:
            raise HunterError("HUNTER_API_KEY is not configured.")

        async def _call() -> HunterVerifyResult:
            if on_request is not None:
                on_request()

            params = {"api_key": self._api_key, "email": email}
            async with session.get(HUNTER_VERIFIER_URL, params=params, timeout=self._timeout) as response:
                body_text = await response.text()
                if response.status != 200:
                    raise HunterError(f"Hunter email-verifier returned HTTP {response.status}: {body_text[:200]}")
                data = await response.json(content_type=None)

            result = data.get("data") or {}
            return HunterVerifyResult(status=result.get("status") or "unknown", score=int(result.get("score") or 0))

        return await retry_with_backoff(_call, retries=self._retries, label=f"Hunter email-verifier '{email}'")
