import os
import sys

# Add backend directory to sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal
from app.models import TestRun, TestCase

def fix_runs():
    db = SessionLocal()
    try:
        # Find runs with no workspace_id but they belong to a TestCase that HAS a workspace_id
        runs = db.query(TestRun).filter(TestRun.workspace_id == None, TestRun.test_case_id != None).all()
        count = 0
        for run in runs:
            tc = db.query(TestCase).filter(TestCase.id == run.test_case_id).first()
            if tc and tc.workspace_id:
                run.workspace_id = tc.workspace_id
                count += 1
                
        db.commit()
        print(f"Fixed {count} runs mapped via TestCase!")
        
        # What if it was an ad-hoc run? We don't have a test_case_id. 
        # For ad-hoc runs in Acme (workspace_id=1), maybe we can't know for sure, 
        # but the schema changes we just did will prevent it going forward.
    finally:
        db.close()

if __name__ == "__main__":
    fix_runs()
