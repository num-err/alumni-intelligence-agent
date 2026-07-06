"""Manual review queue: approve, reject, edit, or skip low-confidence rows.

A global queue (not scoped to one upload) -- rows land here whenever
`AlumniRecord.review_required` is true, regardless of which upload they
came from.
"""

import logging

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.alumni import AlumniRecord
from app.services import review_service

logger = logging.getLogger("alumni_agent")

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def _get_record_or_404(db: Session, record_id: int) -> AlumniRecord:
    record = db.get(AlumniRecord, record_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Record not found")
    return record


@router.get("/review", response_class=HTMLResponse)
async def review_queue(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    records = (
        db.query(AlumniRecord)
        .filter(AlumniRecord.review_required.is_(True))
        .order_by(AlumniRecord.confidence.asc())
        .all()
    )
    return templates.TemplateResponse(request, "review.html", {"records": records})


@router.get("/review/{record_id}/row", response_class=HTMLResponse)
async def display_row(request: Request, record_id: int, db: Session = Depends(get_db)) -> HTMLResponse:
    record = _get_record_or_404(db, record_id)
    return templates.TemplateResponse(request, "partials/review_row.html", {"record": record})


@router.get("/review/{record_id}/edit", response_class=HTMLResponse)
async def edit_form(request: Request, record_id: int, db: Session = Depends(get_db)) -> HTMLResponse:
    record = _get_record_or_404(db, record_id)
    return templates.TemplateResponse(request, "partials/review_row_edit.html", {"record": record, "errors": []})


@router.post("/review/{record_id}/approve", response_class=HTMLResponse)
async def approve_record(record_id: int, db: Session = Depends(get_db)) -> HTMLResponse:
    record = _get_record_or_404(db, record_id)
    review_service.approve(record)
    db.commit()
    logger.info("Reviewer approved record %s", record_id)
    return HTMLResponse("")


@router.post("/review/{record_id}/reject", response_class=HTMLResponse)
async def reject_record(record_id: int, db: Session = Depends(get_db)) -> HTMLResponse:
    record = _get_record_or_404(db, record_id)
    review_service.reject(record)
    db.commit()
    logger.info("Reviewer rejected record %s", record_id)
    return HTMLResponse("")


@router.post("/review/{record_id}/skip", response_class=HTMLResponse)
async def skip_record(record_id: int) -> HTMLResponse:
    """No DB change -- just removes the row from the reviewer's current view."""
    return HTMLResponse("")


@router.post("/review/{record_id}/edit", response_class=HTMLResponse)
async def submit_edit(
    request: Request,
    record_id: int,
    db: Session = Depends(get_db),
    linkedin: str = Form(""),
    public_email: str = Form(""),
    graduation_year: str = Form(""),
    country_origin: str = Form(""),
    current_location: str = Form(""),
) -> HTMLResponse:
    record = _get_record_or_404(db, record_id)
    updates = {
        "linkedin": linkedin,
        "public_email": public_email,
        "graduation_year": graduation_year,
        "country_origin": country_origin,
        "current_location": current_location,
    }
    errors = review_service.edit(record, updates)
    if errors:
        return templates.TemplateResponse(
            request, "partials/review_row_edit.html", {"record": record, "errors": errors}
        )

    db.commit()
    logger.info("Reviewer manually edited record %s", record_id)
    return HTMLResponse("")
