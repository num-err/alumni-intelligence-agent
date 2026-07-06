import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.models.alumni import AlumniRecord
from app.services.claude_cache_service import get_cached_response
from app.services.reasoning_engine import CLAUDE_MODEL, reason_about_student

VALID_PAYLOAD = {
    "linkedin": "https://linkedin.com/in/janedoe",
    "email": None,
    "graduation_year": "2020",
    "country_origin": None,
    "current_location": None,
    "confidence": 90,
    "evidence": ["matched LinkedIn profile"],
    "review_required": False,
    "reason": "Confident match.",
}


def _fake_anthropic_client(create_mock: AsyncMock) -> SimpleNamespace:
    response = SimpleNamespace(
        stop_reason="end_turn",
        content=[SimpleNamespace(type="text", text=json.dumps(VALID_PAYLOAD))],
    )
    create_mock.return_value = response
    return SimpleNamespace(messages=SimpleNamespace(create=create_mock))


@pytest.mark.asyncio
async def test_reason_about_student_calls_claude_and_populates_cache(db_session):
    create_mock = AsyncMock()
    async_client = _fake_anthropic_client(create_mock)
    record = AlumniRecord(first_name="Jane", last_name="Doe")

    result = await reason_about_student(db_session, async_client, record, [])

    assert result.linkedin == "https://linkedin.com/in/janedoe"
    create_mock.assert_awaited_once()

    from app.services.prompt_builder import build_user_prompt

    prompt = build_user_prompt(record, [])
    assert get_cached_response(db_session, CLAUDE_MODEL, prompt) is not None


@pytest.mark.asyncio
async def test_reason_about_student_uses_cache_on_second_call(db_session):
    create_mock = AsyncMock()
    async_client = _fake_anthropic_client(create_mock)
    record = AlumniRecord(first_name="Jane", last_name="Doe")

    await reason_about_student(db_session, async_client, record, [])
    await reason_about_student(db_session, async_client, record, [])

    create_mock.assert_awaited_once()  # second call was served from cache


@pytest.mark.asyncio
async def test_on_request_called_only_on_cache_miss(db_session):
    create_mock = AsyncMock()
    async_client = _fake_anthropic_client(create_mock)
    record = AlumniRecord(first_name="Jane", last_name="Doe")
    calls = []

    await reason_about_student(db_session, async_client, record, [], on_request=lambda: calls.append(1))
    assert len(calls) == 1

    calls.clear()
    await reason_about_student(db_session, async_client, record, [], on_request=lambda: calls.append(1))
    assert calls == []  # served from cache this time
