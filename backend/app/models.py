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
