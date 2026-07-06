"""Resolves and verifies a replacement email via Hunter.io.

Only ever consulted when `decision_engine._email_needs_enrichment()` is
true (missing or at the stale email domain) -- Hunter credits are never
spent on alumni who already have a good email on file.

An email Hunter can't confirm is deliverable is dropped rather than
written; a wrong/bounced address is worse than leaving the field for a
human reviewer.
"""

from collections.abc import Callable
from dataclasses import dataclass

import aiohttp

from app.services.claude_types import ClaudeEnrichment
from app.services.hunter_client import HunterClient, HunterVerifyResult

# "valid" is Hunter's only fully-confirmed status. "accept_all" means the
# mail server accepts any address on that domain -- Hunter can't confirm
# this specific one exists, so it's only trusted at a high score. "webmail"
# (gmail.com etc.) sounds benign but Hunter's own docs say it never reaches
# the remote SMTP server for those, so it's unconfirmed, not confirmed-good.
_ACCEPT_ALL_MIN_SCORE = 90


def _is_deliverable(verification: HunterVerifyResult | None) -> bool:
    if verification is None:
        return False
    if verification.status == "valid":
        return True
    return verification.status == "accept_all" and verification.score >= _ACCEPT_ALL_MIN_SCORE


@dataclass
class EmailResolution:
    email: str | None
    hunter_verified: bool


async def resolve_email(
    session: aiohttp.ClientSession,
    client: HunterClient,
    first_name: str | None,
    last_name: str | None,
    enrichment: ClaudeEnrichment,
    on_request: Callable[[], None] | None = None,
) -> EmailResolution:
    """Find/verify a replacement email for one student.

    If Claude already surfaced a candidate email, only verify it (one
    Hunter credit). Otherwise, if Claude found a current employer, ask
    Hunter's Email Finder for a candidate before verifying it.
    """
    candidate = enrichment.email

    if not candidate:
        if not (enrichment.current_employer and first_name and last_name):
            return EmailResolution(email=None, hunter_verified=False)

        finder = await client.find_email(
            session,
            first_name=first_name,
            last_name=last_name,
            company=enrichment.current_employer,
            on_request=on_request,
        )
        candidate = finder.email if finder else None
        if not candidate:
            return EmailResolution(email=None, hunter_verified=False)

    verification = await client.verify_email(session, candidate, on_request=on_request)
    verified = _is_deliverable(verification)
    return EmailResolution(email=candidate if verified else None, hunter_verified=verified)
