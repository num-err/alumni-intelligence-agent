import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import openpyxl
import pytest
from aioresponses import aioresponses

from app.models.alumni import Upload
from app.services.ingestion_service import ingest_upload
from app.services.tavily_client import TAVILY_SEARCH_URL
from app.workers.enrichment_worker import run_enrichment
from config import get_settings

VALID_PAYLOAD = {
    "linkedin": "https://linkedin.com/in/janedoe",
    "email": None,
    "graduation_year": "2020",
    "country_origin": None,
    "current_location": None,
    "confidence": 97,
    "evidence": ["matched LinkedIn profile"],
    "review_required": False,
    "reason": "Confident match.",
}

TAVILY_PAYLOAD = {"results": [{"title": "t", "url": "https://linkedin.com/in/match", "content": "c", "score": 0.8}]}


def _make_workbook(tmp_path, headers, rows, name="roster.xlsx"):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(headers)
    for row in rows:
        ws.append(row)
    path = tmp_path / name
    wb.save(path)
    return path


def _fake_response(text: str, stop_reason: str = "end_turn"):
    return SimpleNamespace(stop_reason=stop_reason, content=[SimpleNamespace(type="text", text=text)])


def _fake_async_client(create_mock: AsyncMock) -> SimpleNamespace:
    return SimpleNamespace(messages=SimpleNamespace(create=create_mock))


@pytest.fixture(autouse=True)
def _fast_settings(monkeypatch):
    """Give every test a real Tavily key and zero retries, so mocked
    failures raise immediately instead of sleeping through backoff."""
    get_settings.cache_clear()
    monkeypatch.setenv("TAVILY_API_KEY", "fake-key")
    monkeypatch.setenv("RETRY_COUNT", "0")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_run_enrichment_processes_pending_and_skips_completed(tmp_path, session_factory):
    path = _make_workbook(
        tmp_path,
        ["First Name", "Last Name", "Processing Status"],
        [["Jane", "Doe", ""], ["John", "Smith", "completed"]],
    )

    db = session_factory()
    upload = ingest_upload(db, original_filename="roster.xlsx", stored_filename="roster.xlsx", stored_path=path)
    upload_id = upload.id
    db.close()

    create_mock = AsyncMock(return_value=_fake_response(json.dumps(VALID_PAYLOAD)))
    async_client = _fake_async_client(create_mock)

    with aioresponses() as mocked:
        mocked.post(TAVILY_SEARCH_URL, payload=TAVILY_PAYLOAD, repeat=True)
        progress = await run_enrichment(
            upload_id, worker_count=2, session_factory=session_factory, async_client=async_client
        )

    assert progress.total == 1  # only Jane was pending; John was already completed
    assert progress.completed == 1
    assert progress.failed == 0
    create_mock.assert_awaited_once()  # John was never re-processed
    # 6 Tavily queries (no grad year/country/email known) + 1 Claude call for Jane
    assert progress.api_requests == 7

    db = session_factory()
    upload = db.get(Upload, upload_id)
    records = {r.first_name: r for r in upload.records}
    assert records["Jane"].processing_status == "completed"
    assert records["Jane"].linkedin == "https://linkedin.com/in/janedoe"
    assert records["John"].linkedin is None  # untouched -- was already completed, never queued
    db.close()


@pytest.mark.asyncio
async def test_a_failing_record_does_not_stop_other_records(tmp_path, session_factory):
    path = _make_workbook(tmp_path, ["First Name", "Last Name"], [["Jane", "Doe"], ["Broken", "Person"]])

    db = session_factory()
    upload = ingest_upload(db, original_filename="roster.xlsx", stored_filename="roster.xlsx", stored_path=path)
    upload_id = upload.id
    db.close()

    async def create_side_effect(*args, **kwargs):
        prompt = kwargs["messages"][0]["content"]
        if "Broken Person" in prompt:
            raise RuntimeError("simulated Claude outage")
        return _fake_response(json.dumps(VALID_PAYLOAD))

    async_client = _fake_async_client(AsyncMock(side_effect=create_side_effect))

    with aioresponses() as mocked:
        mocked.post(TAVILY_SEARCH_URL, payload=TAVILY_PAYLOAD, repeat=True)
        progress = await run_enrichment(
            upload_id, worker_count=1, session_factory=session_factory, async_client=async_client
        )

    assert progress.completed == 1
    assert progress.failed == 1
    assert len(progress.errors) == 1

    db = session_factory()
    upload = db.get(Upload, upload_id)
    records = {r.first_name: r for r in upload.records}
    assert records["Jane"].processing_status == "completed"
    assert records["Broken"].processing_status == "failed"
    # failure reason is persisted onto the record itself, not just the
    # transient in-memory progress/log, so it survives into the export
    assert any("simulated Claude outage" in line for line in records["Broken"].evidence)
    db.close()


@pytest.mark.asyncio
async def test_second_run_retries_failed_rows_without_touching_completed_ones(tmp_path, session_factory):
    path = _make_workbook(tmp_path, ["First Name", "Last Name"], [["Jane", "Doe"]])

    db = session_factory()
    upload = ingest_upload(db, original_filename="roster.xlsx", stored_filename="roster.xlsx", stored_path=path)
    upload_id = upload.id
    db.close()

    failing_client = _fake_async_client(AsyncMock(side_effect=RuntimeError("simulated outage")))
    with aioresponses() as mocked:
        mocked.post(TAVILY_SEARCH_URL, payload=TAVILY_PAYLOAD, repeat=True)
        await run_enrichment(upload_id, worker_count=1, session_factory=session_factory, async_client=failing_client)

    db = session_factory()
    upload = db.get(Upload, upload_id)
    assert upload.records[0].processing_status == "failed"
    db.close()

    # outage resolved: the previously-failed row is retried on the next run
    recovered_client = _fake_async_client(AsyncMock(return_value=_fake_response(json.dumps(VALID_PAYLOAD))))
    with aioresponses() as mocked:
        mocked.post(TAVILY_SEARCH_URL, payload=TAVILY_PAYLOAD, repeat=True)
        progress = await run_enrichment(
            upload_id, worker_count=1, session_factory=session_factory, async_client=recovered_client
        )

    assert progress.total == 1
    assert progress.completed == 1

    db = session_factory()
    upload = db.get(Upload, upload_id)
    assert upload.records[0].processing_status == "completed"
    db.close()


@pytest.mark.asyncio
async def test_crash_mid_run_resumes_without_reprocessing_completed_rows(tmp_path, session_factory):
    path = _make_workbook(tmp_path, ["First Name", "Last Name"], [["A", "One"], ["B", "Two"]])

    db = session_factory()
    upload = ingest_upload(db, original_filename="roster.xlsx", stored_filename="roster.xlsx", stored_path=path)
    upload_id = upload.id
    db.close()

    call_count = 0

    async def slow_first_call(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            await asyncio.sleep(10)  # the task is cancelled long before this ever returns
        return _fake_response(json.dumps(VALID_PAYLOAD))

    stalling_client = _fake_async_client(AsyncMock(side_effect=slow_first_call))

    with aioresponses() as mocked:
        mocked.post(TAVILY_SEARCH_URL, payload=TAVILY_PAYLOAD, repeat=True)
        task = asyncio.create_task(
            run_enrichment(upload_id, worker_count=1, session_factory=session_factory, async_client=stalling_client)
        )
        await asyncio.sleep(0.3)  # let the worker reach the (now hanging) Claude call
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    # the in-flight record must not be "completed" -- it's eligible for resume
    db = session_factory()
    upload = db.get(Upload, upload_id)
    statuses = {r.first_name: r.processing_status for r in upload.records}
    assert statuses["A"] != "completed"
    db.close()

    # resume: a fresh run only needs to finish what wasn't completed
    recovered_client = _fake_async_client(AsyncMock(return_value=_fake_response(json.dumps(VALID_PAYLOAD))))
    with aioresponses() as mocked:
        mocked.post(TAVILY_SEARCH_URL, payload=TAVILY_PAYLOAD, repeat=True)
        progress = await run_enrichment(
            upload_id, worker_count=1, session_factory=session_factory, async_client=recovered_client
        )

    assert progress.completed == progress.total

    db = session_factory()
    upload = db.get(Upload, upload_id)
    assert all(r.processing_status == "completed" for r in upload.records)
    db.close()


@pytest.mark.asyncio
async def test_no_pending_rows_finishes_immediately(tmp_path, session_factory):
    path = _make_workbook(tmp_path, ["First Name", "Processing Status"], [["Jane", "completed"]])

    db = session_factory()
    upload = ingest_upload(db, original_filename="roster.xlsx", stored_filename="roster.xlsx", stored_path=path)
    upload_id = upload.id
    db.close()

    async_client = _fake_async_client(AsyncMock())
    progress = await run_enrichment(
        upload_id, worker_count=3, session_factory=session_factory, async_client=async_client
    )

    assert progress.total == 0
    assert progress.is_running is False
    async_client.messages.create.assert_not_awaited()
