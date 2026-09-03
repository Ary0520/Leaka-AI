import os
import sys

# Add backend directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import engine
from sqlalchemy import text

with engine.connect() as conn:
    print("Migrating environments table...")
    try:
        conn.execute(text("ALTER TABLE environments ADD COLUMN auth_strategy VARCHAR(32) NOT NULL DEFAULT 'none';"))
        conn.execute(text("ALTER TABLE environments ADD COLUMN auth_api_url VARCHAR(2048);"))
        conn.execute(text("ALTER TABLE environments ADD COLUMN auth_payload TEXT;"))
        conn.execute(text("ALTER TABLE environments ADD COLUMN auth_token_path VARCHAR(128);"))
        conn.execute(text("ALTER TABLE environments ADD COLUMN auth_state_template TEXT;"))
        conn.commit()
        print("Migration complete.")
    except Exception as e:
        print(f"Error: {e}")
        conn.rollback()
