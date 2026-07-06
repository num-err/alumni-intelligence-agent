"""Reports: end-of-run statistics per upload, and completed-spreadsheet export."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.alumni import Upload
from app.services.export_service import export_upload
from app.services.report_service import build_report

logger = logging.getLogger("alumni_agent")

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/reports", response_class=HTMLResponse)
async def reports_page(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    uploads = db.query(Upload).order_by(Upload.uploaded_at.desc()).all()
    reports = [build_report(upload) for upload in uploads]
    return templates.TemplateResponse(request, "reports.html", {"reports": reports})


@router.get("/reports/{upload_id}/download")
async def download_completed_spreadsheet(upload_id: int, db: Session = Depends(get_db)) -> FileResponse:
    upload = db.get(Upload, upload_id)
    if upload is None:
        raise HTTPException(status_code=404, detail="Upload not found")

    output_path = export_upload(upload)
    logger.info("Exported completed spreadsheet for upload %s to %s", upload_id, output_path)
    return FileResponse(
        output_path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=output_path.name,
    )
