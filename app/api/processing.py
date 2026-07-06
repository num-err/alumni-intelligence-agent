"""Routes for starting, observing, and viewing an enrichment run.

Two surfaces share the same underlying `run_enrichment` worker pool and
`progress_tracker` state:

- JSON API (`/process/...`) for programmatic start/poll.
- HTML dashboard (`/processing/...`) -- a live-updating page built with
  HTMX polling, for a human watching the run.
"""

import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.alumni import Upload
from app.workers.enrichment_worker import prepare_run, run_enrichment
from app.workers.progress_tracker import RunProgress, get_run

logger = logging.getLogger("alumni_agent")

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def _format_duration(seconds: float | None) -> str:
    if seconds is None:
        return "calculating..."
    total_seconds = int(seconds)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


def _progress_to_dict(progress: RunProgress) -> dict:
    return {
        "upload_id": progress.upload_id,
        "total": progress.total,
        "completed": progress.completed,
        "failed": progress.failed,
        "processed": progress.processed,
        "remaining": progress.remaining,
        "api_requests": progress.api_requests,
        "average_confidence": progress.average_confidence,
        "last_completed_student": progress.last_completed_student,
        "is_running": progress.is_running,
        "errors": progress.errors,
        "workers": {
            worker_id: {"status": status.status, "current_student": status.current_student}
            for worker_id, status in progress.workers.items()
        },
    }


def _progress_context(upload_id: int) -> dict:
    """Template context shared by the dashboard page and its polling partial."""
    progress = get_run(upload_id)
    if progress is None:
        return {"progress": None, "is_running": False}

    percent = int((progress.processed / progress.total) * 100) if progress.total else 100
    return {
        "progress": progress,
        "is_running": progress.is_running,
        "percent": percent,
        "elapsed_display": _format_duration(progress.elapsed_seconds),
        "eta_display": _format_duration(progress.estimated_seconds_remaining),
    }


def _start_run(upload_id: int) -> None:
    """Register the run's progress synchronously, then hand execution to a
    background task. `prepare_run` runs to completion before this function
    returns, so `get_run(upload_id)` reflects it immediately -- scheduling
    `run_enrichment` via `asyncio.create_task` alone would let the caller
    race its own not-yet-started background task.
    """
    prepared = prepare_run(upload_id)
    asyncio.create_task(run_enrichment(upload_id, prepared=prepared))


def _start_run_if_needed(upload_id: int, db: Session) -> None:
    upload = db.get(Upload, upload_id)
    if upload is None:
        raise HTTPException(status_code=404, detail="Upload not found")

    existing = get_run(upload_id)
    if existing is not None and existing.is_running:
        raise HTTPException(status_code=409, detail="This upload is already being processed")

    logger.info("Starting enrichment run for upload %s", upload_id)
    _start_run(upload_id)


# --- JSON API ---------------------------------------------------------


@router.post("/process/{upload_id}")
async def start_processing(upload_id: int, db: Session = Depends(get_db)) -> dict:
    _start_run_if_needed(upload_id, db)
    return {"started": True, "upload_id": upload_id}


@router.get("/process/{upload_id}/status")
async def processing_status(upload_id: int) -> dict:
    progress = get_run(upload_id)
    if progress is None:
        return {"upload_id": upload_id, "started": False}
    return _progress_to_dict(progress)


# --- HTML dashboard -----------------------------------------------------


@router.get("/processing/{upload_id}", response_class=HTMLResponse)
async def processing_page(request: Request, upload_id: int, db: Session = Depends(get_db)) -> HTMLResponse:
    upload = db.get(Upload, upload_id)
    if upload is None:
        raise HTTPException(status_code=404, detail="Upload not found")

    context = {"upload": upload, **_progress_context(upload_id)}
    return templates.TemplateResponse(request, "processing.html", context)


@router.post("/processing/{upload_id}/start", response_class=HTMLResponse)
async def start_processing_page(request: Request, upload_id: int, db: Session = Depends(get_db)) -> HTMLResponse:
    """Start (or resume) a run from the dashboard button; always safe to click again."""
    upload = db.get(Upload, upload_id)
    if upload is None:
        raise HTTPException(status_code=404, detail="Upload not found")

    existing = get_run(upload_id)
    if existing is None or not existing.is_running:
        logger.info("Starting enrichment run for upload %s", upload_id)
        _start_run(upload_id)

    return templates.TemplateResponse(request, "partials/progress_panel.html", _progress_context(upload_id))


@router.get("/processing/{upload_id}/panel", response_class=HTMLResponse)
async def processing_panel(request: Request, upload_id: int) -> HTMLResponse:
    return templates.TemplateResponse(request, "partials/progress_panel.html", _progress_context(upload_id))
