import re

def patch_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. Patch enqueue_test
    old_enqueue_test = "tc = db.query(TestCase).filter(TestCase.id == test_case_id, TestCase.owner_id == owner_id).first()"
    new_enqueue_test = """try:
            tc = _get_owned_test_case(db, test_case_id, user)
        except HTTPException:
            tc = None"""
    content = content.replace(old_enqueue_test, new_enqueue_test)

    # 2. Patch run_suite
    old_run_suite = """    suite = db.query(TestSuite).filter(TestSuite.id == id, TestSuite.owner_id == user["sub"]).first()
    if not suite:
        raise HTTPException(404, "Suite not found")"""
    new_run_suite = """    suite = _get_owned_suite(db, id, user)"""
    content = content.replace(old_run_suite, new_run_suite)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Patched collaboration endpoints!")

if __name__ == "__main__":
    patch_file(r"C:\Users\aryan\Desktop\WEB3 PROJECTS\Leaka AI\backend\app\main.py")
