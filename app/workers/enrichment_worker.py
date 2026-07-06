"""Concurrent worker pool that enriches all pending rows of an upload.

Implements the core processing workflow: search -> reason -> validate ->
decide -> write immediately -> checkpoint (commit) -> continue. Progress
is tracked in-memory via `progress_tracker` so a live dashboard (Milestone
7) can observe it; the durable checkpoint is each record's
`processing_status`, committed the moment it changes -- that's what makes
crash-resume possible without any separate checkpoint file.
"""

import asyncio
import logging
from collections.abc import Callable

import aiohttp
import anthropic
from sqlalchemy.orm import Session

from app.database.engine import SessionLocal
from app.models.alumni import AlumniRecord, Upload
from app.services.decision_engine import _email_needs_enrichment, apply_decision, decide
from app.services.hunter_client import HunterClient
from app.services.hunter_email_service import EmailResolution, resolve_email
from app.services.ingestion_service import rows_needing_processing
from app.services.reasoning_engine import reason_about_student
from app.services.search_engine import gather_evidence
from app.workers.progress_tracker import RunProgress, create_run
from config import get_settings

logger = logging.getLogger("alumni_agent")

_STOP = object()


def _student_name(record: AlumniRecord) -> str:
    name = " ".join(part for part in (record.first_name, record.last_name) if part).strip()
    return name or f"row {record.row_index}"


async def _process_one_record(
    record_id: int,
    session_factory: Callable[[], Session],
    http_session: aiohttp.ClientSession,
    async_client: anthropic.AsyncAnthropic,
    hunter_client: HunterClient,
    progress: RunProgress,
    worker_id: int,
) -> None:
    """Process a single record in its own DB session, isolating each commit."""
    db = session_factory()
    try:
        record = db.get(AlumniRecord, record_id)
        if record is None:
            return

        name = _student_name(record)

        # Mark as in-flight and checkpoint immediately: if the process dies
        # mid-enrichment, this row is still not "completed" and will be
        # picked back up by rows_needing_processing() on the next run.
        record.processing_status = "processing"
        db.commit()

        progress.set_worker_status(worker_id, status="searching", student=name)
        try:
            evidence = await gather_evidence(db, http_session, record, on_request=progress.record_api_request)

            progress.set_worker_status(worker_id, status="reasoning", student=name)
            enrichment = await reason_about_student(
                db, async_client, record, evidence, on_request=progress.record_api_request
            )

            email_resolution: EmailResolution | None = None
            if _email_needs_enrichment(record.email):
                progress.set_worker_status(worker_id, status="verifying email", student=name)
                email_resolution = await resolve_email(
                    http_session,
                    hunter_client,
                    record.first_name,
                    record.last_name,
                    enrichment,
                    on_request=progress.record_api_request,
                )

            progress.set_worker_status(worker_id, status="writing", student=name)
            decision = decide(record, enrichment, email_resolution)
            apply_decision(record, decision)
            db.commit()  # checkpoint: this student is now durably marked completed

            progress.record_success(name, decision.confidence)
        except Exception as exc:  # noqa: BLE001 -- pipeline boundary: one bad row must not stop the run
            logger.warning("Enrichment failed for %s: %s", name, exc)
            db.rollback()  # discard any partial writes from this attempt
            record.processing_status = "failed"
            # Persisted so the reason is visible in the export itself, not just
            # the live dashboard/log file (both of which disappear once the
            # process restarts). Replaces rather than appends -- this reflects
            # why the row is *currently* failed, not a full retry history.
            record.evidence = [f"Processing failed: {exc}"]
            db.commit()
            progress.record_failure(name, str(exc))
    finally:
        progress.set_worker_status(worker_id, status="idle", student=None)
        db.close()


async def _worker_loop(
    worker_id: int,
    queue: asyncio.Queue,
    session_factory: Callable[[], Session],
    http_session: aiohttp.ClientSession,
    async_client: anthropic.AsyncAnthropic,
    hunter_client: HunterClient,
    progress: RunProgress,
) -> None:
    while True:
        record_id = await queue.get()
        try:
            if record_id is _STOP:
                return
            await _process_one_record(
                record_id, session_factory, http_session, async_client, hunter_client, progress, worker_id
            )
        finally:
            queue.task_done()


def prepare_run(
    upload_id: int,
    session_factory: Callable[[], Session] = SessionLocal,
) -> tuple[RunProgress, list[int]]:
    """Synchronously determine pending rows and register the run's progress.

    Split out from `run_enrichment` so a caller that fire-and-forgets the
    worker pool via `asyncio.create_task` (as the dashboard routes do) can
    call this first and see `get_run(upload_id)` populated immediately --
    `asyncio.create_task` doesn't execute a line of the coroutine until the
    event loop next yields, so without this split the caller would race its
    own background task and briefly render a "not started" view.
    """
    db = session_factory()
    try:
        upload = db.get(Upload, upload_id)
        if upload is None:
            raise ValueError(f"No upload with id {upload_id}")
        pending_ids = [record.id for record in rows_needing_processing(upload)]
    finally:
        db.close()

    progress = create_run(upload_id, total=len(pending_ids))
    return progress, pending_ids


async def run_enrichment(
    upload_id: int,
    worker_count: int | None = None,
    session_factory: Callable[[], Session] = SessionLocal,
    async_client: anthropic.AsyncAnthropic | None = None,
    hunter_client: HunterClient | None = None,
    prepared: tuple[RunProgress, list[int]] | None = None,
) -> RunProgress:
    """Enrich every not-yet-completed row of `upload_id` using a worker pool.

    Rows already marked "completed" (from a prior run, or a re-uploaded
    partially-enriched spreadsheet) are skipped -- this is what makes the
    job resumable and idempotent to re-invoke. Pass `prepared` (from a
    prior call to `prepare_run`) to avoid recomputing/re-registering the
    run when the caller already did so synchronously.
    """
    settings = get_settings()
    worker_count = worker_count or settings.worker_count
    progress, pending_ids = prepared or prepare_run(upload_id, session_factory)

    if not pending_ids:
        progress.finish()
        return progress

    owns_client = async_client is None
    async_client = async_client or anthropic.AsyncAnthropic(api_key=settings.claude_api_key)
    hunter_client = hunter_client or HunterClient(api_key=settings.hunter_api_key, retries=settings.retry_count)

    queue: asyncio.Queue = asyncio.Queue()
    for record_id in pending_ids:
        queue.put_nowait(record_id)
    for _ in range(worker_count):
        queue.put_nowait(_STOP)

    try:
        async with aiohttp.ClientSession() as http_session:
            workers = [
                asyncio.create_task(
                    _worker_loop(i, queue, session_factory, http_session, async_client, hunter_client, progress)
                )
                for i in range(worker_count)
            ]
            await asyncio.gather(*workers)
    finally:
        if owns_client:
            await async_client.close()

    progress.finish()
    return progress
