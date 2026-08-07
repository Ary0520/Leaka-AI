from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, ForeignKey, Enum as SAEnum, Boolean
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

    status = Column(SAEnum(TestRunStatus), default=TestRunStatus.PENDING, index=True)
    result_summary = Column(Text, nullable=True)
    final_result = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)

    total_steps = Column(Integer, default=0)
    duration_seconds = Column(Integer, default=0)
    visited_urls = Column(Text, nullable=True)

    dom_snapshot = Column(Text, nullable=True)
    steps_log = Column(Text, nullable=True)

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
