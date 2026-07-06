"""Settings page: view and update the runtime configuration in `.env`."""

import logging

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.services.settings_service import get_settings_view, update_settings

logger = logging.getLogger("alumni_agent")

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request, "settings.html", {"view": get_settings_view(), "errors": [], "saved": False}
    )


@router.post("/settings", response_class=HTMLResponse)
async def save_settings(
    request: Request,
    claude_api_key: str = Form(""),
    tavily_api_key: str = Form(""),
    hunter_api_key: str = Form(""),
    institution_name: str = Form(...),
    stale_email_domain: str = Form(""),
    worker_count: str = Form(...),
    confidence_threshold: str = Form(...),
    retry_count: str = Form(...),
    cache_expiration_days: str = Form(...),
    output_dir: str = Form(...),
) -> HTMLResponse:
    errors = update_settings(
        claude_api_key=claude_api_key,
        tavily_api_key=tavily_api_key,
        hunter_api_key=hunter_api_key,
        institution_name=institution_name,
        stale_email_domain=stale_email_domain,
        worker_count=worker_count,
        confidence_threshold=confidence_threshold,
        retry_count=retry_count,
        cache_expiration_days=cache_expiration_days,
        output_dir=output_dir,
    )
    if errors:
        logger.warning("Settings update rejected: %s", errors)

    return templates.TemplateResponse(
        request, "settings.html", {"view": get_settings_view(), "errors": errors, "saved": not errors}
    )
