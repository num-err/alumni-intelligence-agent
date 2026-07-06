"""Generic async retry helper with exponential backoff.

Shared by the Tavily client (Milestone 3) and, later, the Claude client
(Milestone 4) -- any outbound API call should be wrapped with this rather
than hand-rolling its own retry loop.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import TypeVar

logger = logging.getLogger("alumni_agent")

T = TypeVar("T")


async def retry_with_backoff(
    func: Callable[[], Awaitable[T]],
    *,
    retries: int,
    base_delay: float = 1.0,
    label: str = "operation",
) -> T:
    """Call `func`, retrying on exception with exponential backoff.

    Makes `retries + 1` total attempts. Re-raises the last exception if
    every attempt fails.
    """
    last_exc: Exception | None = None

    for attempt in range(retries + 1):
        try:
            return await func()
        except Exception as exc:
            last_exc = exc
            if attempt == retries:
                break
            delay = base_delay * (2**attempt)
            logger.warning(
                "%s failed (attempt %d/%d): %s. Retrying in %.1fs",
                label,
                attempt + 1,
                retries + 1,
                exc,
                delay,
            )
            await asyncio.sleep(delay)

    assert last_exc is not None
    raise last_exc
