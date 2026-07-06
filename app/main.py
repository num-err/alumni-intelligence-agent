"""FastAPI application entrypoint.

This module wires together configuration, templates, static files, and
route modules. Business logic must not live here -- routes delegate to
services under `app/services/`.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api import pages, processing, reports, review
from app.api import settings as settings_page
from app.database.engine import init_db
from config import get_settings

logger = logging.getLogger("alumni_agent")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    settings.ensure_directories()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    init_db()
    logger.info("Alumni Agent starting up")
    yield
    logger.info("Alumni Agent shutting down")


def create_app() -> FastAPI:
    app = FastAPI(title="Alumni Intelligence Agent", lifespan=lifespan)
    app.mount("/static", StaticFiles(directory="app/static"), name="static")
    app.include_router(pages.router)
    app.include_router(processing.router)
    app.include_router(review.router)
    app.include_router(reports.router)
    app.include_router(settings_page.router)
    return app


app = create_app()
