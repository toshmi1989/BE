from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


_engine: Engine | None = None
SessionLocal: sessionmaker[Session] | None = None


def _make_engine(database_url: str) -> Engine:
    connect_args: dict = {}
    engine_kwargs: dict = {"future": True}
    if database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
        if ":memory:" in database_url:
            engine_kwargs["poolclass"] = StaticPool
    return create_engine(database_url, connect_args=connect_args, **engine_kwargs)


def configure_engine(database_url: str | None = None) -> Engine:
    """(Re)configure global engine — used by app startup and tests."""
    global _engine, SessionLocal
    settings = get_settings()
    url = database_url or settings.database_url
    _engine = _make_engine(url)

    if url.startswith("sqlite"):

        @event.listens_for(_engine, "connect")
        def _set_sqlite_fk(dbapi_connection, _connection_record) -> None:  # noqa: ANN001
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False, future=True)
    return _engine


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        configure_engine()
    assert _engine is not None
    return _engine


def get_db() -> Generator[Session, None, None]:
    if SessionLocal is None:
        configure_engine()
    assert SessionLocal is not None
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Eager default for import-time convenience (overridden in tests via configure_engine).
configure_engine()
