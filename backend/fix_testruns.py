import re

def fix_testrun_creations(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. run_suite
    old_run_suite = """run = TestRun(
            job_id=job_id,
            run_group_id=run_group_id,
            owner_id=user["sub"],
            test_case_id=tc.id,
            name=run_name,
            prompt=tc.prompt,
            target_url=tc.target_url,
            success_criteria=tc.success_criteria,
            assertions=tc.assertions,  # inherit deterministic assertions
            status=TestRunStatus.PENDING,
        )"""
    new_run_suite = """run = TestRun(
            job_id=job_id,
            run_group_id=run_group_id,
            owner_id=user["sub"],
            test_case_id=tc.id,
            workspace_id=tc.workspace_id,
            name=run_name,
            prompt=tc.prompt,
            target_url=tc.target_url,
            success_criteria=tc.success_criteria,
            assertions=tc.assertions,  # inherit deterministic assertions
            status=TestRunStatus.PENDING,
        )"""

    # 2. enqueue_test
    old_enqueue_test = """run = TestRun(
        job_id=job_id,
        task_id=None,
        owner_id=owner_id,
        test_case_id=test_case_id,
        environment_id=environment_id,
        fixture_id=fixture_id,
        name=run_name,
        prompt=prompt,
        target_url=target_url,
        success_criteria=success_criteria,
        assertions=assertions_json,
        status=TestRunStatus.PENDING,
    )"""
    new_enqueue_test = """run = TestRun(
        job_id=job_id,
        task_id=None,
        owner_id=owner_id,
        test_case_id=test_case_id,
        workspace_id=body.workspace_id if body.workspace_id else (tc.workspace_id if test_case_id and tc else None),
        environment_id=environment_id,
        fixture_id=fixture_id,
        name=run_name,
        prompt=prompt,
        target_url=target_url,
        success_criteria=success_criteria,
        assertions=assertions_json,
        status=TestRunStatus.PENDING,
    )"""

    # 3. trigger_ci
    old_trigger_ci = """run = TestRun(
            job_id=job_id,
            owner_id=caller_owner_id or tc.owner_id,
            test_case_id=tc.id,
            name=f"[CI] {tc.name}",
            prompt=tc.prompt,
            target_url=tc.target_url,
            success_criteria=tc.success_criteria,
            assertions=tc.assertions,  # inherit deterministic assertions
            status=TestRunStatus.PENDING,
            commit_sha=body.commit_sha,
            repo_full_name=body.repo_full_name,
        )"""
    new_trigger_ci = """run = TestRun(
            job_id=job_id,
            owner_id=caller_owner_id or tc.owner_id,
            test_case_id=tc.id,
            workspace_id=tc.workspace_id,
            name=f"[CI] {tc.name}",
            prompt=tc.prompt,
            target_url=tc.target_url,
            success_criteria=tc.success_criteria,
            assertions=tc.assertions,  # inherit deterministic assertions
            status=TestRunStatus.PENDING,
            commit_sha=body.commit_sha,
            repo_full_name=body.repo_full_name,
        )"""

    # 4. trigger_pr_check
    old_trigger_pr = """run = TestRun(
            job_id=job_id, owner_id=owner_id, test_case_id=tc.id,
            name=f"[PR] {tc.name}", prompt=tc.prompt, target_url=tc.target_url,
            success_criteria=tc.success_criteria, assertions=tc.assertions,
            status=TestRunStatus.PENDING,
        )"""
    new_trigger_pr = """run = TestRun(
            job_id=job_id, owner_id=owner_id, test_case_id=tc.id,
            workspace_id=tc.workspace_id,
            name=f"[PR] {tc.name}", prompt=tc.prompt, target_url=tc.target_url,
            success_criteria=tc.success_criteria, assertions=tc.assertions,
            status=TestRunStatus.PENDING,
        )"""

    content = content.replace(old_run_suite, new_run_suite)
    content = content.replace(old_enqueue_test, new_enqueue_test)
    content = content.replace(old_trigger_ci, new_trigger_ci)
    content = content.replace(old_trigger_pr, new_trigger_pr)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Fixed TestRun creations!")

fix_testrun_creations(r'C:\Users\aryan\Desktop\WEB3 PROJECTS\Leaka AI\backend\app\main.py')
