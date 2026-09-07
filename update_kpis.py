import sys
import re

with open('backend/app/main.py', 'r') as f: content = f.read()

new_kpi = """
@app.get("/api/dashboard/kpis")
def dashboard_kpis(
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    owner = user["sub"]
    
    # All-time stats
    total_runs = db.query(TestRun).filter(TestRun.owner_id == owner, TestRun.status != TestRunStatus.PENDING).count()
    passed_runs = db.query(TestRun).filter(TestRun.owner_id == owner, TestRun.is_successful == True).count()
    pass_rate = round((passed_runs / total_runs) * 100, 1) if total_runs > 0 else None

    # Flake Rate
    flaky_runs = db.query(TestRun).filter(TestRun.owner_id == owner, TestRun.is_flaky == True).count()
    flake_rate = round((flaky_runs / total_runs) * 100, 1) if total_runs > 0 else 0

    # Quarantined Tests
    quarantined_tests = db.query(TestCase).filter(TestCase.owner_id == owner, TestCase.is_quarantined == True).count()

    # Failure Categories
    from sqlalchemy import func
    failures = db.query(TestRun.rca_category, func.count(TestRun.id)).filter(
        TestRun.owner_id == owner, TestRun.is_successful == False, TestRun.rca_category != None
    ).group_by(TestRun.rca_category).all()
    failure_categories = [{"category": str(f[0]), "count": f[1]} for f in failures]

    return {
        "pass_rate": pass_rate,
        "flake_rate": flake_rate,
        "quarantined_tests": quarantined_tests,
        "failure_categories": failure_categories,
        "total_runs": total_runs,
        "passed_runs": passed_runs,
        "failed_runs": total_runs - passed_runs
    }
"""

content = re.sub(r'@app\.get\("/api/dashboard/kpis"\).*?return \{.*?\}', new_kpi.strip(), content, flags=re.DOTALL)
with open('backend/app/main.py', 'w') as f: f.write(content)
print('Updated KPI endpoint to all-time stats!')
