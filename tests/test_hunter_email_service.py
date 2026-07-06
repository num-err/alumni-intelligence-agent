from unittest.mock import AsyncMock

import pytest

from app.services.claude_types import ClaudeEnrichment
from app.services.hunter_client import HunterFinderResult, HunterVerifyResult
from app.services.hunter_email_service import resolve_email


def _enrichment(**overrides) -> ClaudeEnrichment:
    defaults = dict(
        linkedin=None,
        email=None,
        graduation_year=None,
        country_origin=None,
        current_location=None,
        current_employer=None,
        confidence=60,
        evidence=[],
        review_required=False,
        reason="",
    )
    defaults.update(overrides)
    return ClaudeEnrichment(**defaults)


@pytest.mark.asyncio
async def test_verifies_claudes_own_candidate_without_calling_finder():
    client = AsyncMock()
    client.verify_email.return_value = HunterVerifyResult(status="valid", score=95)

    resolution = await resolve_email(
        session=object(),
        client=client,
        first_name="Jane",
        last_name="Doe",
        enrichment=_enrichment(email="jane@acme.com", current_employer="Acme"),
    )

    client.find_email.assert_not_called()
    client.verify_email.assert_called_once()
    assert resolution.email == "jane@acme.com"
    assert resolution.hunter_verified is True


@pytest.mark.asyncio
async def test_drops_claudes_candidate_when_verification_fails():
    client = AsyncMock()
    client.verify_email.return_value = HunterVerifyResult(status="invalid", score=10)

    resolution = await resolve_email(
        session=object(),
        client=client,
        first_name="Jane",
        last_name="Doe",
        enrichment=_enrichment(email="jane@acme.com"),
    )

    assert resolution.email is None
    assert resolution.hunter_verified is False


@pytest.mark.asyncio
async def test_finds_and_verifies_when_no_candidate_but_employer_known():
    client = AsyncMock()
    client.find_email.return_value = HunterFinderResult(email="jane@acme.com", score=80)
    client.verify_email.return_value = HunterVerifyResult(status="accept_all", score=95)

    resolution = await resolve_email(
        session=object(),
        client=client,
        first_name="Jane",
        last_name="Doe",
        enrichment=_enrichment(current_employer="Acme"),
    )

    client.find_email.assert_called_once()
    assert resolution.email == "jane@acme.com"
    assert resolution.hunter_verified is True


@pytest.mark.asyncio
async def test_low_score_accept_all_is_not_trusted():
    # accept_all means the mail server takes any address on that domain --
    # Hunter can't actually confirm this one exists, so a low-confidence
    # accept_all result must not be treated as verified.
    client = AsyncMock()
    client.verify_email.return_value = HunterVerifyResult(status="accept_all", score=70)

    resolution = await resolve_email(
        session=object(),
        client=client,
        first_name="Jane",
        last_name="Doe",
        enrichment=_enrichment(email="jane@acme.com"),
    )

    assert resolution.email is None
    assert resolution.hunter_verified is False


@pytest.mark.asyncio
async def test_webmail_status_is_not_trusted_despite_sounding_benign():
    # Hunter's own docs: webmail addresses never reach the remote SMTP
    # server, so this status is unconfirmed, not confirmed-good.
    client = AsyncMock()
    client.verify_email.return_value = HunterVerifyResult(status="webmail", score=99)

    resolution = await resolve_email(
        session=object(),
        client=client,
        first_name="Jane",
        last_name="Doe",
        enrichment=_enrichment(email="jane@gmail.com"),
    )

    assert resolution.email is None
    assert resolution.hunter_verified is False


@pytest.mark.asyncio
async def test_no_candidate_and_no_employer_never_calls_hunter():
    client = AsyncMock()

    resolution = await resolve_email(
        session=object(),
        client=client,
        first_name="Jane",
        last_name="Doe",
        enrichment=_enrichment(),
    )

    client.find_email.assert_not_called()
    client.verify_email.assert_not_called()
    assert resolution.email is None
    assert resolution.hunter_verified is False


@pytest.mark.asyncio
async def test_finder_with_no_result_never_calls_verifier():
    client = AsyncMock()
    client.find_email.return_value = None

    resolution = await resolve_email(
        session=object(),
        client=client,
        first_name="Jane",
        last_name="Doe",
        enrichment=_enrichment(current_employer="Acme"),
    )

    client.verify_email.assert_not_called()
    assert resolution.email is None
    assert resolution.hunter_verified is False
