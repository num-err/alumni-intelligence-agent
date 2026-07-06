import re

import aiohttp
import pytest
from aioresponses import aioresponses

from app.services.errors import HunterError
from app.services.hunter_client import HUNTER_FINDER_URL, HUNTER_VERIFIER_URL, HunterClient

FINDER_PATTERN = re.compile(rf"^{re.escape(HUNTER_FINDER_URL)}\?")
VERIFIER_PATTERN = re.compile(rf"^{re.escape(HUNTER_VERIFIER_URL)}\?")


@pytest.mark.asyncio
async def test_find_email_parses_result():
    client = HunterClient(api_key="fake-key", retries=0)
    payload = {"data": {"email": "jane@acme.com", "score": 90}}

    with aioresponses() as mocked:
        mocked.get(FINDER_PATTERN, payload=payload)
        async with aiohttp.ClientSession() as session:
            result = await client.find_email(session, first_name="Jane", last_name="Doe", company="Acme")

    assert result is not None
    assert result.email == "jane@acme.com"
    assert result.score == 90


@pytest.mark.asyncio
async def test_find_email_returns_none_when_no_candidate():
    client = HunterClient(api_key="fake-key", retries=0)
    payload = {"data": {"email": None, "score": 0}}

    with aioresponses() as mocked:
        mocked.get(FINDER_PATTERN, payload=payload)
        async with aiohttp.ClientSession() as session:
            result = await client.find_email(session, first_name="Jane", last_name="Doe", company="Acme")

    assert result is None


@pytest.mark.asyncio
async def test_find_email_missing_api_key_raises_without_calling_network():
    client = HunterClient(api_key="", retries=0)

    async with aiohttp.ClientSession() as session:
        with pytest.raises(HunterError):
            await client.find_email(session, first_name="Jane", last_name="Doe", company="Acme")


@pytest.mark.asyncio
async def test_find_email_retries_then_succeeds():
    client = HunterClient(api_key="fake-key", retries=1)
    payload = {"data": {"email": "jane@acme.com", "score": 90}}

    with aioresponses() as mocked:
        mocked.get(FINDER_PATTERN, status=500)
        mocked.get(FINDER_PATTERN, payload=payload)
        async with aiohttp.ClientSession() as session:
            result = await client.find_email(session, first_name="Jane", last_name="Doe", company="Acme")

    assert result.email == "jane@acme.com"


@pytest.mark.asyncio
async def test_find_email_exhausts_retries_and_raises():
    client = HunterClient(api_key="fake-key", retries=1)

    with aioresponses() as mocked:
        mocked.get(FINDER_PATTERN, status=500)
        mocked.get(FINDER_PATTERN, status=500)
        async with aiohttp.ClientSession() as session:
            with pytest.raises(HunterError):
                await client.find_email(session, first_name="Jane", last_name="Doe", company="Acme")


@pytest.mark.asyncio
async def test_verify_email_parses_result():
    client = HunterClient(api_key="fake-key", retries=0)
    payload = {"data": {"status": "valid", "score": 95}}

    with aioresponses() as mocked:
        mocked.get(VERIFIER_PATTERN, payload=payload)
        async with aiohttp.ClientSession() as session:
            result = await client.verify_email(session, "jane@acme.com")

    assert result.status == "valid"
    assert result.score == 95


@pytest.mark.asyncio
async def test_verify_email_missing_api_key_raises_without_calling_network():
    client = HunterClient(api_key="", retries=0)

    async with aiohttp.ClientSession() as session:
        with pytest.raises(HunterError):
            await client.verify_email(session, "jane@acme.com")


@pytest.mark.asyncio
async def test_on_request_called_once_per_attempt_including_retries():
    client = HunterClient(api_key="fake-key", retries=1)
    payload = {"data": {"email": "jane@acme.com", "score": 90}}
    calls = []

    with aioresponses() as mocked:
        mocked.get(FINDER_PATTERN, status=500)
        mocked.get(FINDER_PATTERN, payload=payload)
        async with aiohttp.ClientSession() as session:
            await client.find_email(
                session, first_name="Jane", last_name="Doe", company="Acme", on_request=lambda: calls.append(1)
            )

    assert len(calls) == 2
