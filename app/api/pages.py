"""Page routes: Home and Upload.

These routes render server-side templates and, for HTMX requests, return
HTML fragments rather than full pages. File parsing/enrichment is handled
in later milestones -- this module currently only accepts and stores the
uploaded workbook.
"""

import logging
import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.services.ingestion_service import ingest_upload, rows_needing_processing
from config import get_settings

logger = logging.getLogger("alumni_agent")

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

ALLOWED_EXTENSIONS = {".xlsx"}
_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


def _sanitize_filename(filename: str) -> str:
    """Strip path components and unsafe characters from an uploaded filename."""
    base = filename.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    return _SAFE_NAME_RE.sub("_", base)


@router.get("/", response_class=HTMLResponse)
async def home(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "home.html")


@router.get("/upload", response_class=HTMLResponse)
async def upload_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "upload.html")


@router.post("/upload", response_class=HTMLResponse)
async def upload_spreadsheet(
    request: Request, file: UploadFile, db: Session = Depends(get_db)
) -> HTMLResponse:
    settings = get_settings()

    original_name = file.filename or ""
    extension = "." + original_name.rsplit(".", 1)[-1].lower() if "." in original_name else ""

    if extension not in ALLOWED_EXTENSIONS:
        return templates.TemplateResponse(
            request,
            "partials/upload_result.html",
            {"success": False, "message": "Only .xlsx files are supported."},
            status_code=400,
        )

    safe_name = _sanitize_filename(original_name)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    stored_name = f"{timestamp}_{safe_name}"
    destination = settings.upload_path / stored_name

    contents = await file.read()
    destination.write_bytes(contents)
    logger.info("Stored upload %s (%d bytes) as %s", original_name, len(contents), stored_name)

    try:
        upload = ingest_upload(
            db,
            original_filename=original_name,
            stored_filename=stored_name,
            stored_path=destination,
        )
    except Exception:
        logger.exception("Failed to parse uploaded spreadsheet %s", original_name)
        return templates.TemplateResponse(
            request,
            "partials/upload_result.html",
            {
                "success": False,
                "message": (
                    f"Uploaded {original_name}, but it could not be parsed as a "
                    "valid spreadsheet. Please check the file and try again."
                ),
            },
            status_code=422,
        )

    queued = len(rows_needing_processing(upload))
    completed = upload.total_rows - queued

    return templates.TemplateResponse(
        request,
        "partials/upload_result.html",
        {
            "success": True,
            "message": f"Uploaded {original_name} successfully.",
            "upload": upload,
            "queued": queued,
            "completed": completed,
        },
    )
