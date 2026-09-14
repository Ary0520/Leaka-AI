import sqlite3
import os

db_path = r'C:\Users\aryan\Desktop\WEB3 PROJECTS\Leaka AI\backend\revguard.db'

def run_migration():
    print(f"Connecting to database at {db_path}...")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    tables = ["test_cases", "test_runs", "test_suites"]
    for table in tables:
        try:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN workspace_id INTEGER REFERENCES workspaces(id);")
            print(f"Added workspace_id column to {table} table.")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e):
                print(f"Column workspace_id already exists in {table} table.")
            else:
                print(f"Error altering {table} table: {e}")

    conn.commit()
    conn.close()
    print("Migration completed successfully.")

if __name__ == "__main__":
    if not os.path.exists(db_path):
        print(f"Error: Database file not found at {db_path}")
    else:
        run_migration()
