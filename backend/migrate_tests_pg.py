import sys
from sqlalchemy import text
from app.database import engine

def run_migration():
    print("Connecting to database...")
    with engine.connect() as conn:
        tables = ["test_cases", "test_runs", "test_suites"]
        for table in tables:
            try:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN workspace_id INTEGER REFERENCES workspaces(id);"))
                print(f"Added workspace_id column to {table} table.")
            except Exception as e:
                if "already exists" in str(e) or "DuplicateColumn" in str(e):
                    print(f"Column workspace_id already exists in {table} table.")
                else:
                    print(f"Error altering {table} table: {e}")
        conn.commit()
    print("Migration completed successfully.")

if __name__ == "__main__":
    run_migration()
