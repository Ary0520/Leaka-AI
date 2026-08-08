import json
from app.database import SessionLocal
from app.models import TestRun

db = SessionLocal()
runs = db.query(TestRun).filter(TestRun.steps_log != None).order_by(TestRun.id.desc()).limit(5).all()
for run in runs:
    if not run.steps_log:
        continue
    steps = json.loads(run.steps_log)
    if not steps:
        continue
    print(f"Run: {run.name[:50]}")
    for s in steps:
        result = s.get("result") or ""
        action = s.get("action") or {}
        action_name = list(action.keys())[0] if action else "unknown"
        action_val = action.get(action_name, "")
        print(f"  step {s.get('step')} [{action_name}] {str(action_val)[:60]}")
        if result:
            print(f"    -> {str(result)[:120]}")
    print()
    break
db.close()
