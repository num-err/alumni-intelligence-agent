import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.services.claude_client import ClaudeClient
from app.services.errors import ClaudeReasoningError

VALID_PAYLOAD = {
    "linkedin": "https://linkedin.com/in/janedoe",
    "email": None,
    "graduation_year": "2020",
    "country_origin": None,
    "current_location": None,
    "confidence": 85,
    "evidence": ["matched LinkedIn profile"],
    "review_required": False,
    "reason": "Confident match.",
}


def _fake_response(text: str, stop_reason: str = "end_turn"):
    return SimpleNamespace(stop_reason=stop_reason, content=[SimpleNamespace(type="text", text=text)])


def _fake_anthropic_client(create_mock: AsyncMock) -> SimpleNamespace:
    return SimpleNamespace(messages=SimpleNamespace(create=create_mock))


@pytest.mark.asyncio
async def test_enrich_parses_successful_response():
    create_mock = AsyncMock(return_value=_fake_response(json.dumps(VALID_PAYLOAD)))
    client = ClaudeClient(_fake_anthropic_client(create_mock), model="claude-sonnet-5", retries=0)

    result = await client.enrich(system="sys", user_prompt="user")

    assert result.linkedin == "https://linkedin.com/in/janedoe"
    assert result.confidence == 85
    create_mock.assert_awaited_once()
    _, kwargs = create_mock.call_args
    assert kwargs["model"] == "claude-sonnet-5"
    assert kwargs["output_config"]["format"]["type"] == "json_schema"


@pytest.mark.asyncio
async def test_refusal_raises_claude_reasoning_error():
    create_mock = AsyncMock(return_value=_fake_response("", stop_reason="refusal"))
    client = ClaudeClient(_fake_anthropic_client(create_mock), model="claude-sonnet-5", retries=0)

    with pytest.raises(ClaudeReasoningError):
        await client.enrich(system="sys", user_prompt="user")


@pytest.mark.asyncio
async def test_missing_text_block_raises_claude_reasoning_error():
    response = SimpleNamespace(stop_reason="end_turn", content=[])
    create_mock = AsyncMock(return_value=response)
    client = ClaudeClient(_fake_anthropic_client(create_mock), model="claude-sonnet-5", retries=0)

    with pytest.raises(ClaudeReasoningError):
        await client.enrich(system="sys", user_prompt="user")


@pytest.mark.asyncio
async def test_retries_then_succeeds():
    create_mock = AsyncMock(
        side_effect=[Exception("transient"), _fake_response(json.dumps(VALID_PAYLOAD))]
    )
    client = ClaudeClient(_fake_anthropic_client(create_mock), model="claude-sonnet-5", retries=1)

    result = await client.enrich(system="sys", user_prompt="user")

    assert result.confidence == 85
    assert create_mock.await_count == 2


@pytest.mark.asyncio
async def test_on_request_called_once_per_attempt_including_retries():
    create_mock = AsyncMock(
        side_effect=[Exception("transient"), _fake_response(json.dumps(VALID_PAYLOAD))]
    )
    client = ClaudeClient(_fake_anthropic_client(create_mock), model="claude-sonnet-5", retries=1)
    calls = []

    await client.enrich(system="sys", user_prompt="user", on_request=lambda: calls.append(1))

    assert len(calls) == 2  # one failed attempt + one successful retry
