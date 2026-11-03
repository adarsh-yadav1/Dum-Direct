from collections.abc import Iterator

import pytest
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.models import Base


def make_sqlite_engine() -> Engine:
    """In-memory SQLite with foreign keys enforced, matching PostgreSQL's behaviour."""
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection, _record):  # noqa: ANN001
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    return engine


@pytest.fixture()
def session() -> Iterator[Session]:
    engine = make_sqlite_engine()
    with Session(engine) as db:
        yield db
    engine.dispose()
