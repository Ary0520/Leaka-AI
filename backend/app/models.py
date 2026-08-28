from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, ForeignKey, Enum as SAEnum, Boolean, UniqueConstraint
)
from sqlalchemy.orm import relationship
import enum

from .database import Base


class TestRunStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TestSuite(Base):
    __tablename__ = "test_suites"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(String(64), nullable=True, index=True)  # Supabase user UUID
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    tests = relationship("TestCase", back_populates="suite", cascade="all, delete-orphan")


class TestCase(Base):
    __tablename__ = "test_cases"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(String(64), nullable=True, index=True)  # Supabase user UUID
    suite_id = Column(Integer, ForeignKey("test_suites.id"), nullable=True)
    name = Column(String(255), nullable=False)
    prompt = Column(Text, nullable=False)
    success_criteria = Column(Text, nullable=True)
    target_url = Column(String(2048), nullable=True)
    # Deterministic assertions (JSON array of {type, value, options}).
    # NULL = no assertions → run behaves exactly as before (LLM verdict only).
    assertions = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    suite = relationship("TestSuite", back_populates="tests")
    runs = relationship("TestRun", back_populates="test_case", cascade="all, delete-orphan")


class TestRun(Base):
    __tablename__ = "test_runs"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(String(64), nullable=True, index=True)  # Supabase user UUID
    job_id = Column(String(64), unique=True, index=True, nullable=False)
    task_id = Column(String(128), unique=True, index=True, nullable=True)
    test_case_id = Column(Integer, ForeignKey("test_cases.id"), nullable=True)

    name = Column(String(255), nullable=False)
    prompt = Column(Text, nullable=False)
    target_url = Column(String(2048), nullable=True)
    success_criteria = Column(Text, nullable=True)
    # Deterministic assertions copied from the test case (or set ad-hoc) at
    # enqueue time. JSON array of {type, value, options}. NULL = none.
    assertions = Column(Text, nullable=True)
    # Per-assertion evaluation results written by the worker after the run.
    # JSON array of {type, value, passed, actual, detail}. NULL = not evaluated.
    assertion_results = Column(Text, nullable=True)

    status = Column(SAEnum(TestRunStatus), default=TestRunStatus.PENDING, index=True)
    result_summary = Column(Text, nullable=True)
    final_result = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)

    total_steps = Column(Integer, default=0)
    duration_seconds = Column(Integer, default=0)
    visited_urls = Column(Text, nullable=True)

    dom_snapshot = Column(Text, nullable=True)
    steps_log = Column(Text, nullable=True)
    live_steps = Column(Text, nullable=True)   # incremental steps written per-step during run

    is_successful = Column(Boolean, nullable=True)
    has_visual_proof = Column(Boolean, default=False)

    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    test_case = relationship("TestCase", back_populates="runs")
    screenshots = relationship(
        "TestScreenshot", back_populates="test_run", cascade="all, delete-orphan"
    )
    linear_issue = relationship(
        "LinearIssue", back_populates="test_run", uselist=False, cascade="all, delete-orphan"
    )


class TestScreenshot(Base):
    __tablename__ = "test_screenshots"

    id = Column(Integer, primary_key=True, index=True)
    test_run_id = Column(Integer, ForeignKey("test_runs.id"), nullable=False)
    file_path = Column(String(2048), nullable=False)
    url = Column(String(2048), nullable=True)
    caption = Column(String(500), nullable=True)
    step_index = Column(Integer, nullable=True)
    is_failure_point = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    test_run = relationship("TestRun", back_populates="screenshots")


class LinearIssue(Base):
    __tablename__ = "linear_issues"

    id = Column(Integer, primary_key=True, index=True)
    test_run_id = Column(Integer, ForeignKey("test_runs.id"), nullable=False, unique=True)
    issue_id = Column(String(128), nullable=False)
    identifier = Column(String(64), nullable=True)
    title = Column(String(500), nullable=False)
    url = Column(String(2048), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    test_run = relationship("TestRun", back_populates="linear_issue")


class UserSettings(Base):
    """
    Per-user integration settings stored in the database.
    Each Supabase user (owner_id = sub claim) gets one row.
    This allows every Leaka user to connect their own Slack workspace,
    configure their own dashboard URL, etc. — independent of the global .env.
    """
    __tablename__ = "user_settings"
    __table_args__ = (UniqueConstraint("owner_id", name="uq_user_settings_owner"),)

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(String(64), nullable=False, unique=True, index=True)

    # Slack
    slack_webhook_url = Column(String(2048), nullable=True)
    slack_auto_alert_on_failure = Column(Boolean, default=True, nullable=False)
    # Dashboard deep-link base (e.g. "https://app.leaka.ai" or "http://localhost:3000")
    dashboard_base_url = Column(String(512), nullable=True)

    # Onboarding
    onboarding_completed = Column(Boolean, default=False, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ===========================================================================
# APPLICATION INTELLIGENCE (Explore Mode)
# ---------------------------------------------------------------------------
# A parallel subsystem: connect an application, autonomously explore it, and
# build a map of its pages/forms/flows. Completely independent of the test-run
# tables above — nothing here touches TestRun / TestCase execution logic.
# ===========================================================================


class ExploreRunStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Application(Base):
    """
    A user-connected application that Leaka can explore and map.
    Owner-scoped like every other user resource.
    """
    __tablename__ = "applications"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(String(64), nullable=True, index=True)  # Supabase user UUID
    name = Column(String(255), nullable=False)
    base_url = Column(String(2048), nullable=False)
    description = Column(Text, nullable=True)
    # Optional login hint for the explorer (natural-language, e.g.
    # "Log in with standard_user / secret_sauce"). NOT a secrets store — v1
    # keeps this simple; real credential vaulting is a later enterprise phase.
    login_hint = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    explore_runs = relationship(
        "ExploreRun", back_populates="application", cascade="all, delete-orphan"
    )
    map_nodes = relationship(
        "AppMapNode", back_populates="application", cascade="all, delete-orphan"
    )


class ExploreRun(Base):
    """
    A single autonomous exploration run against an Application. Mirrors the
    TestRun lifecycle (pending → running → completed/failed) but is separate.
    """
    __tablename__ = "explore_runs"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(String(64), nullable=True, index=True)
    application_id = Column(Integer, ForeignKey("applications.id"), nullable=False)
    job_id = Column(String(64), unique=True, index=True, nullable=False)
    task_id = Column(String(128), unique=True, index=True, nullable=True)

    status = Column(SAEnum(ExploreRunStatus), default=ExploreRunStatus.PENDING, index=True)
    max_steps = Column(Integer, default=40)

    nodes_found = Column(Integer, default=0)
    result_summary = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    live_steps = Column(Text, nullable=True)   # incremental steps during run
    visited_urls = Column(Text, nullable=True)  # JSON list

    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    application = relationship("Application", back_populates="explore_runs")


class AppMapNode(Base):
    """
    One discovered element of an application's map — a page, a form, or a flow.
    Written by the explore worker from the agent's structured output.
    """
    __tablename__ = "app_map_nodes"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(String(64), nullable=True, index=True)
    application_id = Column(Integer, ForeignKey("applications.id"), nullable=False, index=True)
    explore_run_id = Column(Integer, ForeignKey("explore_runs.id"), nullable=True)

    # node_type: "page" | "form" | "flow"
    node_type = Column(String(32), nullable=False, default="page")
    label = Column(String(500), nullable=False)         # human name, e.g. "Checkout"
    url = Column(String(2048), nullable=True)            # where it lives, if known
    description = Column(Text, nullable=True)            # what it does
    # Suggested test prompt the explorer drafted for this node (used by the
    # "generate test" one-click). NULL if none drafted.
    suggested_prompt = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    application = relationship("Application", back_populates="map_nodes")


# ===========================================================================
# APPLICATION GRAPH (Layer 1) — persistent, versioned graph built by
# reconciling explore discoveries. Additive; independent of the execution path.
# JSON-shaped fields are stored as Text (JSON strings) to match the existing
# codebase convention (assertions, steps_log, etc.) and stay portable.
# ===========================================================================


class GraphNode(Base):
    """
    A persistent node in an application's graph — a page, flow, form, action,
    or role — with a stable canonical identity that survives re-explores.
    """
    __tablename__ = "graph_nodes"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(String(64), nullable=True, index=True)
    application_id = Column(Integer, ForeignKey("applications.id"), nullable=False, index=True)

    # Stable identity (hash of the most stable fingerprint signals). Unique per
    # application so the same entity keeps one node across explore runs.
    canonical_key = Column(String(64), nullable=False, index=True)

    node_type = Column(String(32), nullable=False, default="page")       # page|flow|form|action|role
    business_category = Column(String(64), nullable=True)                 # e.g. checkout|auth|content|unknown
    label = Column(String(500), nullable=False)
    url_pattern = Column(String(2048), nullable=True)                     # normalized url signature
    role_association = Column(String(64), nullable=True, default="unknown")
    dependencies_incomplete = Column(Boolean, default=False, nullable=False)

    # JSON-as-text
    semantics = Column(Text, nullable=True)          # evidence/signals used to classify
    risk = Column(Text, nullable=True)               # {level, score, factors}
    manual_overrides = Column(Text, nullable=True)   # authoritative human edits (win over computed)

    status = Column(String(16), nullable=False, default="active", index=True)  # active|stale

    first_seen_run = Column(Integer, ForeignKey("explore_runs.id"), nullable=True)
    last_seen_run = Column(Integer, ForeignKey("explore_runs.id"), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("application_id", "canonical_key", name="uq_graph_node_app_key"),
    )

    application = relationship("Application")
    fingerprints = relationship(
        "NodeFingerprint", back_populates="node", cascade="all, delete-orphan"
    )


class GraphEdge(Base):
    """A typed, directed relationship between two graph nodes."""
    __tablename__ = "graph_edges"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(String(64), nullable=True, index=True)
    application_id = Column(Integer, ForeignKey("applications.id"), nullable=False, index=True)

    source_node_id = Column(Integer, ForeignKey("graph_nodes.id"), nullable=False, index=True)
    target_node_id = Column(Integer, ForeignKey("graph_nodes.id"), nullable=False, index=True)
    # navigates_to | contains | requires_role | depends_on | part_of_flow
    edge_type = Column(String(32), nullable=False)
    confidence = Column(Integer, default=100)        # 0..100 (int to avoid float noise)
    provenance = Column(Text, nullable=True)         # JSON-as-text
    status = Column(String(16), nullable=False, default="active", index=True)  # active|stale

    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint(
            "application_id", "source_node_id", "target_node_id", "edge_type",
            name="uq_graph_edge_dedup",
        ),
    )


class NodeFingerprint(Base):
    """
    A versioned identity signal set for a graph node. A new version is appended
    when a node's fingerprint drifts (UI change), retaining prior versions for
    future intent-preserving re-identification (self-healing seed).
    """
    __tablename__ = "node_fingerprints"

    id = Column(Integer, primary_key=True, index=True)
    node_id = Column(Integer, ForeignKey("graph_nodes.id"), nullable=False, index=True)

    url_signature = Column(String(2048), nullable=True)
    dom_signature = Column(String(64), nullable=True)
    aria_signature = Column(String(64), nullable=True)
    text_signature = Column(String(64), nullable=True)
    # References embeddings.id (raw-migration table); plain int, no ORM FK to
    # avoid coupling the ORM to a non-ORM table.
    embedding_id = Column(Integer, nullable=True)
    observed_run = Column(Integer, ForeignKey("explore_runs.id"), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    node = relationship("GraphNode", back_populates="fingerprints")


class GraphSnapshot(Base):
    """
    An immutable, point-in-time capture of an application's full graph produced
    by a reconciliation. Append-only; enables diffing and audit.
    """
    __tablename__ = "graph_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(String(64), nullable=True, index=True)
    application_id = Column(Integer, ForeignKey("applications.id"), nullable=False, index=True)
    explore_run_id = Column(Integer, ForeignKey("explore_runs.id"), nullable=True)

    node_count = Column(Integer, default=0)
    edge_count = Column(Integer, default=0)
    diff_summary = Column(Text, nullable=True)       # JSON-as-text: vs previous snapshot

    created_at = Column(DateTime, default=datetime.utcnow)

    members = relationship(
        "SnapshotMember", back_populates="snapshot", cascade="all, delete-orphan"
    )


class SnapshotMember(Base):
    """A frozen copy of a node's state as it existed within a given snapshot."""
    __tablename__ = "snapshot_members"

    id = Column(Integer, primary_key=True, index=True)
    snapshot_id = Column(Integer, ForeignKey("graph_snapshots.id"), nullable=False, index=True)
    node_id = Column(Integer, ForeignKey("graph_nodes.id"), nullable=True, index=True)
    # Frozen node metadata at snapshot time (JSON-as-text). We keep node_id for
    # linkage but the frozen state is the source of truth for diffing so history
    # survives even if the live node later changes.
    node_state = Column(Text, nullable=False)
    canonical_key = Column(String(64), nullable=True, index=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    snapshot = relationship("GraphSnapshot", back_populates="members")


# ===========================================================================
# COVERAGE INTELLIGENCE (Layer 2) — per-node coverage verdicts and the
# authoritative test↔node links that drive them. Additive; owner+application
# scoped like every other resource. JSON-shaped fields are Text (JSON strings)
# to match the existing convention.
# ===========================================================================


class CoverageVerdict(Base):
    """
    The computed coverage classification for a single graph node.

    One row per (application_id, node_id): the coverage engine recomputes and
    upserts it. `state` is covered|partially_covered|uncovered; `confidence` is
    a float in [0.0, 1.0]; `evidence` records the contributing signals so the
    verdict is explainable (R4.1, R4.8).
    """
    __tablename__ = "coverage_verdicts"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(String(64), nullable=True, index=True)
    application_id = Column(Integer, ForeignKey("applications.id"), nullable=False, index=True)
    node_id = Column(Integer, ForeignKey("graph_nodes.id"), nullable=False, index=True)

    # covered | partially_covered | uncovered
    state = Column(String(24), nullable=False, default="uncovered", index=True)
    # Stored as an integer 0..1000 (= confidence * 1000) to avoid float noise in
    # the DB while keeping the API-facing value in [0.0, 1.0]. See the coverage
    # engine / endpoint for the conversion.
    confidence_milli = Column(Integer, nullable=False, default=0)
    evidence = Column(Text, nullable=True)           # JSON-as-text: signals list

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("application_id", "node_id", name="uq_coverage_verdict_app_node"),
    )


class CoverageLink(Base):
    """
    An authoritative link between a TestCase and a graph node (R4.3).

    Created when a test is generated from a node ("generate test" flow) or when
    a user manually links them. `source` is generated|manual. If the linked node
    later becomes stale, the link is flagged `orphaned` (not dropped) for review
    (R4.9).
    """
    __tablename__ = "coverage_links"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(String(64), nullable=True, index=True)
    application_id = Column(Integer, ForeignKey("applications.id"), nullable=False, index=True)
    node_id = Column(Integer, ForeignKey("graph_nodes.id"), nullable=False, index=True)
    test_case_id = Column(Integer, ForeignKey("test_cases.id"), nullable=False, index=True)

    source = Column(String(16), nullable=False, default="generated")  # generated|manual
    orphaned = Column(Boolean, default=False, nullable=False, index=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint(
            "application_id", "node_id", "test_case_id", name="uq_coverage_link_dedup",
        ),
    )


# ===========================================================================
# MEMORY (Layer 3) — durable, per-application learned knowledge store.
# MemoryItem holds the knowledge itself; MemoryWriteQueue is the durable
# write-back queue for items that couldn't be persisted immediately (R5.5a).
# Both owner+application scoped like every other resource.
# ===========================================================================


class MemoryItem(Base):
    """
    One piece of durable learned knowledge about an application — element
    fingerprints, preferred locator hierarchies, timing/flakiness observations,
    auth patterns, historical outcomes (R5.1).

    Kinds: locator | timing | auth_pattern | outcome | fingerprint
    Each kind's payload is a free-form JSON dict specific to the kind.
    """
    __tablename__ = "memory_items"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(String(64), nullable=True, index=True)
    application_id = Column(Integer, ForeignKey("applications.id"), nullable=False, index=True)
    # The graph node this item is about (nullable — some memory is app-global).
    node_id = Column(Integer, ForeignKey("graph_nodes.id"), nullable=True, index=True)

    # locator | timing | auth_pattern | outcome | fingerprint
    kind = Column(String(32), nullable=False, index=True)
    payload = Column(Text, nullable=False)           # JSON-as-text (the learned knowledge)
    # FK to embeddings table (optional — only kinds that benefit from semantic
    # retrieval have an embedding). Plain int, no ORM FK to the non-ORM table.
    embedding_id = Column(Integer, nullable=True)
    content_hash = Column(String(64), nullable=True, index=True)
    provenance = Column(Text, nullable=True)         # JSON-as-text: run, model, when
    version = Column(Integer, nullable=False, default=1)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        # Per-node, one item per (kind, content_hash) to avoid duplicate memories
        # for unchanged knowledge. content_hash may be NULL for legacy items, so
        # this index only deduplicates when both are present.
        UniqueConstraint(
            "application_id", "node_id", "kind", "content_hash",
            name="uq_memory_item_dedup",
        ),
    )


class MemoryWriteQueue(Base):
    """
    Durable write-back queue for memory items that could not be persisted
    immediately (DB/embedder failure, R5.5a). A periodic graph_worker task drains
    this with retry + backoff so knowledge is never lost, even if the in-flight
    run that produced it has already completed.
    """
    __tablename__ = "memory_write_queue"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(String(64), nullable=True, index=True)
    application_id = Column(Integer, ForeignKey("applications.id"), nullable=False, index=True)

    # The full MemoryItem payload (JSON-as-text), ready to be re-attempted.
    payload = Column(Text, nullable=False)
    attempts = Column(Integer, nullable=False, default=0)
    # When to next retry (UTC). NULL = retry now.
    next_retry_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
