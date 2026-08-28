import logging

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import declarative_base, sessionmaker
from .config import settings

logger = logging.getLogger("revguard.database")

connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(settings.DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# ---------------------------------------------------------------------------
# pgvector: register the vector type on every psycopg2 connection so that
# `vector` columns serialize/deserialize correctly. Only applies to Postgres;
# harmless no-op guard for SQLite. Registration is best-effort: if the vector
# extension has not been enabled yet (first boot before migration), we do NOT
# crash — the app still starts and the migration will enable it.
# ---------------------------------------------------------------------------
if settings.DATABASE_URL.startswith("postgres"):

    @event.listens_for(engine, "connect")
    def _register_pgvector(dbapi_connection, connection_record):  # noqa: ANN001
        try:
            from pgvector.psycopg2 import register_vector
            register_vector(dbapi_connection)
        except Exception as exc:  # extension not enabled yet, or driver mismatch
            # Best-effort: vector columns simply won't be typed until the
            # extension exists + a fresh connection registers. Never block boot.
            logger.debug("pgvector register skipped on connect: %s", exc)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from . import models

    Base.metadata.create_all(bind=engine)
