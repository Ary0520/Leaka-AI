"""
Idempotent, additive migrations for Application Intelligence.

Design contract (R11.1):
  - Every migration is idempotent: safe to run any number of times.
  - Every migration is additive: it only CREATEs extensions/tables/columns
    IF NOT EXISTS. It NEVER drops or destructively alters existing objects.
  - Migrations run against the shared Supabase Postgres. Because local and
    Azure share that database, a migration applies once for both.

This module is intentionally simple (no Alembic): the project already uses
`Base.metadata.create_all` + occasional raw ALTERs. We keep that spirit but
centralize the raw DDL that create_all cannot express (extensions, pgvector
columns, HNSW indexes) into explicitly-numbered, idempotent steps.

Run all pending migrations via `run_migrations()`. Each step is guarded so a
failure in one (e.g. lacking privileges to CREATE EXTENSION) is logged and
does not abort the others or crash app startup.
"""

from __future__ import annotations

import logging

from sqlalchemy import text

from .database import engine
from .config import settings

logger = logging.getLogger("revguard.migrations")


def _is_postgres() -> bool:
    return settings.DATABASE_URL.startswith("postgres")


# ---------------------------------------------------------------------------
# M1 — pgvector extension + embeddings table
# ---------------------------------------------------------------------------
def _m1_pgvector_and_embeddings() -> None:
    """
    Enable the pgvector extension and create the `embeddings` table.

    The `embeddings` table is the shared vector store for Application
    Intelligence (memory + coverage semantic signals). It is keyed by
    (content_hash, model_id) so identical content is never re-embedded
    (cost governance, R5.11). `dim` is stored per row so mixed-provider
    vectors never collide, and similarity queries always filter by model_id.
    """
    if not _is_postgres():
        # SQLite fallback (local dev without Postgres): skip vector features.
        logger.info("M1 skipped: DATABASE_URL is not Postgres; vector features disabled.")
        return

    with engine.begin() as conn:
        # 1. Extension (requires the DB role to have privilege; Supabase allows it).
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

        # 2. embeddings table. We create the vector column with a fixed max the
        #    providers we support fit within. pgvector `vector` without a fixed
        #    dimension is allowed, but we store dim explicitly for clarity and
        #    to filter by (model_id, dim) at query time. Use vector(1536) as the
        #    widest supported (OpenAI text-embedding-3-small); the local
        #    sentence-transformers model (384) fits by storing shorter vectors
        #    — pgvector requires matching dim per column, so we DO NOT fix the
        #    column dimension and instead use an unbounded `vector` column.
        conn.execute(text(
            """
            CREATE TABLE IF NOT EXISTS embeddings (
                id            BIGSERIAL PRIMARY KEY,
                owner_id      VARCHAR(64),
                application_id INTEGER,
                content_hash  VARCHAR(64) NOT NULL,
                model_id      VARCHAR(128) NOT NULL,
                dim           INTEGER NOT NULL,
                embedding     vector NOT NULL,
                token_cost    INTEGER DEFAULT 0,
                created_at    TIMESTAMP DEFAULT (now() AT TIME ZONE 'utc')
            )
            """
        ))

        # 3. Uniqueness for cost-governance dedup: one row per (content_hash, model_id).
        conn.execute(text(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS uq_embeddings_content_model
            ON embeddings (content_hash, model_id)
            """
        ))

        # 4. Owner/application scoping index for fast tenant-scoped reads.
        conn.execute(text(
            """
            CREATE INDEX IF NOT EXISTS ix_embeddings_owner_app
            ON embeddings (owner_id, application_id)
            """
        ))

    logger.info("M1 applied: pgvector extension + embeddings table ready.")


# ---------------------------------------------------------------------------
# M2 — Application Graph tables (Layer 1)
# ---------------------------------------------------------------------------
def _m2_graph_tables() -> None:
    """
    Create the Application Graph tables (graph_nodes, graph_edges,
    node_fingerprints, graph_snapshots, snapshot_members).

    These are ORM models, so we let SQLAlchemy emit `CREATE TABLE IF NOT EXISTS`
    for exactly these tables (checkfirst=True). This is idempotent and additive
    — it never touches existing tables.
    """
    from .database import Base
    from . import models  # ensure models are imported/registered on Base

    graph_tables = [
        models.GraphNode.__table__,
        models.GraphEdge.__table__,
        models.NodeFingerprint.__table__,
        models.GraphSnapshot.__table__,
        models.SnapshotMember.__table__,
    ]
    Base.metadata.create_all(bind=engine, tables=graph_tables, checkfirst=True)
    logger.info("M2 applied: application graph tables ready.")


# ---------------------------------------------------------------------------
# M3 — Coverage Intelligence tables (Layer 2)
# ---------------------------------------------------------------------------
def _m3_coverage_tables() -> None:
    """
    Create the Coverage Intelligence tables (coverage_verdicts, coverage_links).

    ORM models → SQLAlchemy emits `CREATE TABLE IF NOT EXISTS` for exactly these
    tables (checkfirst=True). Idempotent and additive; never touches existing
    tables. Runs after M2 because these tables FK to graph_nodes.
    """
    from .database import Base
    from . import models  # ensure models are imported/registered on Base

    coverage_tables = [
        models.CoverageVerdict.__table__,
        models.CoverageLink.__table__,
    ]
    Base.metadata.create_all(bind=engine, tables=coverage_tables, checkfirst=True)
    logger.info("M3 applied: coverage intelligence tables ready.")


# ---------------------------------------------------------------------------
# M4 — Memory tables (Layer 3)
# ---------------------------------------------------------------------------
def _m4_memory_tables() -> None:
    """
    Create the Memory tables (memory_items, memory_write_queue).

    ORM models → SQLAlchemy emits `CREATE TABLE IF NOT EXISTS` for exactly these
    tables (checkfirst=True). Idempotent and additive; never touches existing
    tables. Runs after M2 because memory_items FKs to graph_nodes.
    """
    from .database import Base
    from . import models  # ensure models are imported/registered on Base

    memory_tables = [
        models.MemoryItem.__table__,
        models.MemoryWriteQueue.__table__,
    ]
    Base.metadata.create_all(bind=engine, tables=memory_tables, checkfirst=True)
    logger.info("M4 applied: memory tables ready.")


# ---------------------------------------------------------------------------
# M5 — PR Intelligence tables (Layer 4)
# ---------------------------------------------------------------------------
def _m5_repo_tables() -> None:
    """
    Create the PR Intelligence tables (repo_connections, code_diffs,
    flow_mappings).

    ORM models → SQLAlchemy emits `CREATE TABLE IF NOT EXISTS` for exactly these
    tables (checkfirst=True). Idempotent and additive; never touches existing
    tables. Runs after M2 because flow_mappings FKs to graph_nodes.

    Secret columns on repo_connections store references only (R9.3) — the schema
    has no plaintext token column by design.
    """
    from .database import Base
    from . import models  # ensure models are imported/registered on Base

    repo_tables = [
        models.RepoConnection.__table__,
        models.CodeDiff.__table__,
        models.FlowMapping.__table__,
    ]
    Base.metadata.create_all(bind=engine, tables=repo_tables, checkfirst=True)
    logger.info("M5 applied: PR intelligence tables ready.")


# ---------------------------------------------------------------------------
# M6 — enrich app_map_nodes with business_category + connects_to
# ---------------------------------------------------------------------------
def _m6_app_map_node_enrichment() -> None:
    """
    Add relationship/category columns to the EXISTING `app_map_nodes` table so
    the explorer can persist observed categories, navigation, DEPENDENCIES, and
    flow composition — which feed graph edges + centrality-based risk.

    create_all cannot add columns to an existing table, so we emit guarded
    ADD COLUMNs. Idempotent + additive on both Postgres and SQLite:
      - Postgres supports `ADD COLUMN IF NOT EXISTS`.
      - SQLite has no IF NOT EXISTS for columns, so we check pragma first.
    Never drops or alters existing columns.
    """
    from sqlalchemy import inspect

    cols_to_add = {
        "business_category": "VARCHAR(64)",
        "connects_to": "TEXT",
        "depends_on": "TEXT",
        "flow_steps": "TEXT",
    }

    if _is_postgres():
        with engine.begin() as conn:
            for name, ddl in cols_to_add.items():
                conn.execute(text(
                    f"ALTER TABLE app_map_nodes ADD COLUMN IF NOT EXISTS {name} {ddl}"
                ))
    else:
        # SQLite (local dev): check existing columns, add only if missing.
        insp = inspect(engine)
        existing = {c["name"] for c in insp.get_columns("app_map_nodes")}
        with engine.begin() as conn:
            for name, ddl in cols_to_add.items():
                if name not in existing:
                    conn.execute(text(f"ALTER TABLE app_map_nodes ADD COLUMN {name} {ddl}"))
    logger.info("M6 applied: app_map_nodes enriched (business_category, connects_to).")


def ensure_embeddings_hnsw_index(dim: int, threshold: int = 1000) -> None:
    """
    Lazily create an HNSW cosine index on `embeddings.embedding` once the table
    is large enough to benefit (design: avoid indexing overhead on tiny sets).

    HNSW requires a fixed dimension, so the index is created over a dimension-
    cast expression and filtered by that dim at query time. This is a helper
    called by the vector-search path when it detects scale, NOT part of the
    boot migrations. No-op on non-Postgres.
    """
    if not _is_postgres():
        return
    try:
        with engine.begin() as conn:
            count = conn.execute(text("SELECT count(*) FROM embeddings WHERE dim = :d"), {"d": dim}).scalar()
            if (count or 0) < threshold:
                return
            index_name = f"ix_embeddings_hnsw_cosine_{dim}"
            # Expression index over vectors cast to the fixed dim, cosine ops.
            conn.execute(text(
                f"""
                CREATE INDEX IF NOT EXISTS {index_name}
                ON embeddings USING hnsw ((embedding::vector({dim})) vector_cosine_ops)
                WHERE dim = {dim}
                """
            ))
        logger.info("HNSW index ensured for embeddings dim=%s", dim)
    except Exception as exc:  # index is an optimization; never fail the caller
        logger.warning("HNSW index creation skipped (dim=%s): %s", dim, exc)


# ---------------------------------------------------------------------------
# B1 — Backfill existing AppMapNodes into the Application Graph
# ---------------------------------------------------------------------------
def _b1_backfill_graph() -> None:
    """
    Upgrade already-explored applications into the persistent graph (R11.2).

    Idempotent + additive: only applications that have AppMapNodes but NO graph
    nodes are processed; each uses the same pure reconcile() engine + persist
    path as a live explore, so a re-run is a no-op. It never drops or mutates
    existing AppMapNode / ExploreRun rows, so the existing `/map` endpoint keeps
    working throughout. Guarded by run_migrations() so a failure never blocks
    boot and leaves prior state intact.

    Runs only after M2 (graph tables) has created the tables. On a non-Postgres
    local DB the graph tables still exist (create_all), so backfill also works
    there for dev parity.
    """
    from .graph_worker import backfill_all_pending
    summary = backfill_all_pending()
    logger.info(
        "B1 applied: backfilled=%s skipped=%s failed=%s",
        len(summary.get("backfilled", [])),
        len(summary.get("skipped", [])),
        len(summary.get("failed", [])),
    )


# ---------------------------------------------------------------------------
# Public runner
# ---------------------------------------------------------------------------
_MIGRATIONS = [
    ("M1_pgvector_and_embeddings", _m1_pgvector_and_embeddings),
    ("M2_graph_tables", _m2_graph_tables),
    ("M3_coverage_tables", _m3_coverage_tables),
    ("M4_memory_tables", _m4_memory_tables),
    ("M5_repo_tables", _m5_repo_tables),
    ("M6_app_map_node_enrichment", _m6_app_map_node_enrichment),
    ("B1_backfill_graph", _b1_backfill_graph),
]


def run_migrations() -> None:
    """Run all migrations, each guarded so one failure never blocks the rest."""
    for name, fn in _MIGRATIONS:
        try:
            fn()
        except Exception as exc:  # noqa: BLE001 — never crash boot on a migration
            logger.error("Migration %s failed (continuing): %s", name, exc)
