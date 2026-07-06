import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.engine import Base
from app.models import alumni  # noqa: F401  (registers models on Base.metadata)


@pytest.fixture()
def db_session():
    """An isolated in-memory SQLite session, independent of the app's real DB."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def session_factory():
    """A sessionmaker bound to one shared in-memory SQLite DB (via StaticPool),
    so multiple independent `Session()` calls see the same data -- this
    mirrors how the worker pool opens one session per record.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine)
