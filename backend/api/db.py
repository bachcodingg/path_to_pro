from __future__ import annotations

import logging
from collections.abc import Iterator

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from api.settings import settings
from domain.models import Base


def make_engine(url: str) -> Engine:
    kwargs = {}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
        if url in ("sqlite://", "sqlite:///:memory:"):
            from sqlalchemy.pool import StaticPool

            kwargs["poolclass"] = StaticPool
    engine = create_engine(url, **kwargs)
    if url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def _fk_on(dbapi_conn, _):  # SQLite needs foreign keys switched on for cascades
            dbapi_conn.execute("PRAGMA foreign_keys=ON")

    return engine


engine = make_engine(settings.database_url)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


log = logging.getLogger("pathtopro")


def init_db(bind: Engine | None = None) -> None:
    eng = bind or engine
    Base.metadata.create_all(eng)
    add_missing_columns(eng)


def add_missing_columns(eng: Engine) -> list[str]:
    """Additive schema sync for databases created before a column existed (deployments
    that started from create_all rather than Alembic). Only adds nullable columns or
    columns with a server default, and missing indexes; never drops or alters."""
    insp = inspect(eng)
    added = []
    with eng.begin() as conn:
        for table in Base.metadata.sorted_tables:
            if not insp.has_table(table.name):
                continue
            have = {c["name"] for c in insp.get_columns(table.name)}
            for col in table.columns:
                if col.name in have:
                    continue
                if not col.nullable and col.server_default is None:
                    log.warning("cannot add %s.%s automatically: run the Alembic migration", table.name, col.name)
                    continue
                ddl = f'ALTER TABLE {table.name} ADD COLUMN {col.name} {col.type.compile(eng.dialect)}'
                if col.server_default is not None:
                    ddl += f" DEFAULT '{col.server_default.arg}'"
                if not col.nullable:
                    ddl += " NOT NULL"
                # Table/column names and types come from our own metadata, never from input.
                conn.execute(text(ddl))  # nosemgrep
                added.append(f"{table.name}.{col.name}")
            indexes = {i["name"] for i in insp.get_indexes(table.name)}
            new_cols = {a.split(".", 1)[1] for a in added if a.startswith(f"{table.name}.")}
            for idx in table.indexes:
                if idx.name not in indexes and {c.name for c in idx.columns} & new_cols:
                    idx.create(conn)
    if added:
        log.info("added columns: %s", ", ".join(added))
    return added


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
