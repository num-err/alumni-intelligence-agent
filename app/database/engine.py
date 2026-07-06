"""SQLAlchemy engine, session factory, and declarative base.

A single SQLite database (configured via `DATABASE_URL`) backs the
persisted alumni records, the search/Claude response caches, and --
because each record's `processing_status` is committed immediately --
doubles as the resumable checkpoint store for the worker pool.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from config import get_settings


class Base(DeclarativeBase):
    pass


def _make_engine():
    settings = get_settings()
    settings.cache_path.mkdir(parents=True, exist_ok=True)
    return create_engine(
        settings.database_url,
        # timeout: seconds to wait on a locked table before raising --
        # concurrent workers commit often, so a generous busy timeout
        # avoids spurious "database is locked" errors under load.
        connect_args={"check_same_thread": False, "timeout": 30},
    )


engine = _make_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def init_db() -> None:
    """Create all tables that don't exist yet. Safe to call on every startup."""
    from app.models import alumni, cache  # noqa: F401  (registers models on Base.metadata)

    Base.metadata.create_all(bind=engine)
