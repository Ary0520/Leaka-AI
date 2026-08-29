"""
Migration M5 + PR Intelligence model tests (Task 16, Requirements 6.1, 9.3, 11.1).

Verifies the repo/diff/mapping tables are created idempotently, the dedup unique
constraints hold, webhook delivery-id dedup works (replay protection groundwork),
and — critically — that RepoConnection has NO plaintext secret column (R9.3).
"""

from __future__ import annotations

import json
import uuid

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError

from app.database import SessionLocal, engine, Base, init_db
from app.migrations import run_migrations
from app.models import (
    Application, GraphNode, RepoConnection, CodeDiff, FlowMapping,
)

init_db()
Base.metadata.create_all(bind=engine)


def test_m5_idempotent_and_creates_tables():
    run_migrations()
    run_migrations()  # twice — must not error
    insp = inspect(engine)
    tables = insp.get_table_names()
    assert "repo_connections" in tables
    assert "code_diffs" in tables
    assert "flow_mappings" in tables


def test_repo_connection_has_no_plaintext_secret_column():
    """R9.3: secrets are stored as references only — no plaintext token column."""
    insp = inspect(engine)
    cols = {c["name"] for c in insp.get_columns("repo_connections")}
    assert "secret_ref" in cols
    assert "webhook_secret_ref" in cols
    # None of these plaintext-secret names may exist on the model.
    for banned in ("token", "secret", "access_token", "webhook_secret", "password"):
        assert banned not in cols, f"plaintext secret column '{banned}' must not exist"


def _seed_app(owner: str) -> int:
    db = SessionLocal()
    try:
        app_row = Application(owner_id=owner, name="RepoApp", base_url="https://s.com")
        db.add(app_row); db.commit()
        return app_row.id
    finally:
        db.close()


def _cleanup(owner: str):
    db = SessionLocal()
    try:
        app_ids = [a.id for a in db.query(Application).filter(Application.owner_id == owner).all()]
        if app_ids:
            db.query(FlowMapping).filter(FlowMapping.application_id.in_(app_ids)).delete(synchronize_session=False)
            db.query(CodeDiff).filter(CodeDiff.application_id.in_(app_ids)).delete(synchronize_session=False)
            db.query(RepoConnection).filter(RepoConnection.application_id.in_(app_ids)).delete(synchronize_session=False)
            db.query(GraphNode).filter(GraphNode.application_id.in_(app_ids)).delete(synchronize_session=False)
            db.query(Application).filter(Application.id.in_(app_ids)).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


def test_repo_connection_unique_per_app_provider_repo():
    owner = f"REPOM5_{uuid.uuid4().hex[:8]}"
    try:
        app_id = _seed_app(owner)
        db = SessionLocal()
        try:
            db.add(RepoConnection(owner_id=owner, application_id=app_id,
                                  provider="github", repo_full_name="org/repo",
                                  secret_ref="ref://secret/abc"))
            db.commit()
            db.add(RepoConnection(owner_id=owner, application_id=app_id,
                                  provider="github", repo_full_name="org/repo",
                                  secret_ref="ref://secret/def"))
            with pytest.raises(IntegrityError):
                db.commit()
            db.rollback()
        finally:
            db.close()
    finally:
        _cleanup(owner)


def test_code_diff_delivery_id_dedup():
    owner = f"REPOM5_{uuid.uuid4().hex[:8]}"
    try:
        app_id = _seed_app(owner)
        db = SessionLocal()
        try:
            conn = RepoConnection(owner_id=owner, application_id=app_id,
                                  provider="github", repo_full_name="org/repo")
            db.add(conn); db.flush()
            db.add(CodeDiff(owner_id=owner, application_id=app_id, repo_connection_id=conn.id,
                            pr_number="42", ingest_status="ingested", delivery_id="delivery-1"))
            db.commit()
            # Same delivery id → replay → unique violation (dedup groundwork).
            db.add(CodeDiff(owner_id=owner, application_id=app_id, repo_connection_id=conn.id,
                            pr_number="42", ingest_status="ingested", delivery_id="delivery-1"))
            with pytest.raises(IntegrityError):
                db.commit()
            db.rollback()
        finally:
            db.close()
    finally:
        _cleanup(owner)


def test_flow_mapping_unique_per_diff_node():
    owner = f"REPOM5_{uuid.uuid4().hex[:8]}"
    try:
        app_id = _seed_app(owner)
        db = SessionLocal()
        try:
            node = GraphNode(owner_id=owner, application_id=app_id,
                             canonical_key=uuid.uuid4().hex[:16], node_type="page",
                             label="Checkout", status="active")
            db.add(node)
            conn = RepoConnection(owner_id=owner, application_id=app_id,
                                  provider="github", repo_full_name="org/repo")
            db.add(conn); db.flush()
            diff = CodeDiff(owner_id=owner, application_id=app_id, repo_connection_id=conn.id,
                            pr_number="7", ingest_status="ingested")
            db.add(diff); db.flush()
            db.add(FlowMapping(owner_id=owner, application_id=app_id, code_diff_id=diff.id,
                               node_id=node.id, confidence_milli=800,
                               signals=json.dumps({"route": True}),
                               recommended_tests=json.dumps([1, 2]),
                               coverage_state="covered"))
            db.commit()
            db.add(FlowMapping(owner_id=owner, application_id=app_id, code_diff_id=diff.id,
                               node_id=node.id, confidence_milli=500,
                               coverage_state="uncovered"))
            with pytest.raises(IntegrityError):
                db.commit()
            db.rollback()
        finally:
            db.close()
    finally:
        _cleanup(owner)
