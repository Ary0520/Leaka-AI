"""
Migration M3 + coverage model tests (Task 10, Requirements 4.1, 4.3, 4.9, 11.1).

Verifies the coverage tables are created idempotently and that the dedup unique
constraints hold (one verdict per (app, node); one link per (app, node, test)).
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError

from app.database import SessionLocal, engine, Base, init_db
from app.migrations import run_migrations
from app.models import (
    Application, ExploreRun, ExploreRunStatus, AppMapNode, GraphNode,
    TestCase, CoverageVerdict, CoverageLink,
)

init_db()
Base.metadata.create_all(bind=engine)


def test_m3_is_idempotent_and_creates_tables():
    run_migrations()
    run_migrations()  # twice — must not error
    insp = inspect(engine)
    tables = insp.get_table_names()
    assert "coverage_verdicts" in tables
    assert "coverage_links" in tables


def _seed_node_and_test(owner: str) -> tuple[int, int, int]:
    db = SessionLocal()
    try:
        app_row = Application(owner_id=owner, name="CovApp", base_url="https://s.com")
        db.add(app_row); db.flush()
        node = GraphNode(
            owner_id=owner, application_id=app_row.id,
            canonical_key=uuid.uuid4().hex[:16], node_type="page", label="Login",
            status="active",
        )
        db.add(node)
        tc = TestCase(owner_id=owner, name="Login test", prompt="log in")
        db.add(tc)
        db.commit()
        return app_row.id, node.id, tc.id
    finally:
        db.close()


def _cleanup(owner: str):
    db = SessionLocal()
    try:
        app_ids = [a.id for a in db.query(Application).filter(Application.owner_id == owner).all()]
        if app_ids:
            db.query(CoverageLink).filter(CoverageLink.application_id.in_(app_ids)).delete(synchronize_session=False)
            db.query(CoverageVerdict).filter(CoverageVerdict.application_id.in_(app_ids)).delete(synchronize_session=False)
            db.query(GraphNode).filter(GraphNode.application_id.in_(app_ids)).delete(synchronize_session=False)
            db.query(Application).filter(Application.id.in_(app_ids)).delete(synchronize_session=False)
        db.query(TestCase).filter(TestCase.owner_id == owner).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


def test_verdict_unique_per_app_node():
    owner = f"COVM3_{uuid.uuid4().hex[:8]}"
    try:
        app_id, node_id, _ = _seed_node_and_test(owner)
        db = SessionLocal()
        try:
            db.add(CoverageVerdict(owner_id=owner, application_id=app_id, node_id=node_id,
                                   state="covered", confidence_milli=900))
            db.commit()
            # Duplicate (app, node) must violate the unique constraint.
            db.add(CoverageVerdict(owner_id=owner, application_id=app_id, node_id=node_id,
                                   state="uncovered", confidence_milli=0))
            with pytest.raises(IntegrityError):
                db.commit()
            db.rollback()
        finally:
            db.close()
    finally:
        _cleanup(owner)


def test_link_unique_per_app_node_test():
    owner = f"COVM3_{uuid.uuid4().hex[:8]}"
    try:
        app_id, node_id, tc_id = _seed_node_and_test(owner)
        db = SessionLocal()
        try:
            db.add(CoverageLink(owner_id=owner, application_id=app_id, node_id=node_id,
                                test_case_id=tc_id, source="generated"))
            db.commit()
            db.add(CoverageLink(owner_id=owner, application_id=app_id, node_id=node_id,
                                test_case_id=tc_id, source="manual"))
            with pytest.raises(IntegrityError):
                db.commit()
            db.rollback()
        finally:
            db.close()
    finally:
        _cleanup(owner)
