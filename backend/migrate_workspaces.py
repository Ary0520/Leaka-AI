import os
import sys

# Add backend directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import engine
from app.models import Base
from sqlalchemy import text

print("Creating new tables (Organizations, Workspaces, WorkspaceMembers)...")
Base.metadata.create_all(bind=engine)

with engine.connect() as conn:
    print("Migrating applications table...")
    try:
        conn.execute(text("ALTER TABLE applications ADD COLUMN workspace_id INTEGER REFERENCES workspaces(id);"))
        conn.commit()
        print("Migration complete.")
    except Exception as e:
        if "duplicate column name" in str(e).lower():
            print("Column workspace_id already exists.")
        else:
            print(f"Error: {e}")
            conn.rollback()
