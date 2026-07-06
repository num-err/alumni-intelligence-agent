"""Cache tables so identical API calls are never repeated."""

import datetime

from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.engine import Base


class SearchResultCache(Base):
    """One row per unique (normalized) Tavily query."""

    __tablename__ = "search_cache"

    id: Mapped[int] = mapped_column(primary_key=True)
    query_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    query_text: Mapped[str] = mapped_column(String(512))
    results: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime.datetime] = mapped_column(
        default=lambda: datetime.datetime.now(datetime.timezone.utc)
    )


class ClaudeResponseCache(Base):
    """One row per unique (model, prompt) pair sent to Claude for reasoning."""

    __tablename__ = "claude_response_cache"

    id: Mapped[int] = mapped_column(primary_key=True)
    prompt_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    response: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime.datetime] = mapped_column(
        default=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
