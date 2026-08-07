import sys
try:
    import requests
except ImportError:
    print("requests not installed, using urllib as fallback")
    import urllib.request, urllib.error, json

    def _req(method, url, json_body=None):
        data = None
        headers = {}
        if json_body is not None:
            data = json.dumps(json_body).encode()
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                body = resp.read().decode()
                parsed = json.loads(body) if body else None
                return resp.status, parsed
        except urllib.error.HTTPError as e:
            body = e.read().decode()
            parsed = json.loads(body) if body else None
            return e.code, parsed
        except Exception as e:
            return 0, {"error": str(e)}
else:
    def _req(method, url, json_body=None):
        r = requests.request(method, url, json=json_body, timeout=10)
        try:
            body = r.json()
        except Exception:
            body = r.text
        return r.status_code, body


B = "http://127.0.0.1:8000"
passed = 0
failed = 0

def check(label, status_code, body, expected_code=None, predicate=None):
    global passed, failed
    ok = True
    if expected_code is not None and status_code != expected_code:
        ok = False
    if predicate is not None and not predicate(body):
        ok = False
    if ok:
        print(f"[PASS] {label} -> {status_code}")
        passed += 1
    else:
        print(f"[FAIL] {label} -> {status_code} {body}")
        failed += 1
    return body


# ---------------- Test Cases ----------------
print("\n=== TestCases REST smoke ===")
s, tc = _req("POST", f"{B}/api/test-cases", {
    "name": "Smoke TC 1",
    "prompt": "Open page and verify title",
    "target_url": "https://example.com",
    "success_criteria": "Page title contains Example",
})
tc = check("POST test-case", s, tc, 200, lambda b: "id" in b)
tc_id = tc["id"]

s, data = _req("GET", f"{B}/api/test-cases")
check("GET test-cases", s, data, 200, lambda b: isinstance(b, list))

s, upd = _req("PUT", f"{B}/api/test-cases/{tc_id}", {"name": "Smoke TC 1 (UPDATED)"})
upd = check("PUT test-case", s, upd, 200, lambda b: b.get("name") == "Smoke TC 1 (UPDATED)")

s, _ = _req("DELETE", f"{B}/api/test-cases/{tc_id}")
check("DELETE test-case", s, _, 204)

s, data = _req("DELETE", f"{B}/api/test-cases/{tc_id}")
check("DELETE missing case 404", s, data, 404)

# ---------------- Test Suites ----------------
print("\n=== TestSuites REST smoke ===")
s, suite = _req("POST", f"{B}/api/test-suites", {
    "name": "Smoke Suite",
    "description": "Suite created via API smoke",
})
suite = check("POST suite", s, suite, 200, lambda b: "id" in b)
s_id = suite["id"]

s, data = _req("GET", f"{B}/api/test-suites")
check("GET suites", s, data, 200, lambda b: isinstance(b, list))

s, upd = _req("PUT", f"{B}/api/test-suites/{s_id}", {"description": "Updated description"})
upd = check("PUT suite", s, upd, 200, lambda b: b.get("description") == "Updated description")

s, data = _req("POST", f"{B}/api/test-suites/{s_id}/run")
check("POST suite/run empty -> 400", s, data, 400)

# Add a case to suite, then run
s, case1 = _req("POST", f"{B}/api/test-cases", {
    "name": "Suite TC A",
    "suite_id": s_id,
    "prompt": "Open example.com",
    "target_url": "https://example.com",
    "success_criteria": "Page loads",
})
case1 = check("POST suite-case A", s, case1, 200, lambda b: "id" in b)

s, case2 = _req("POST", f"{B}/api/test-cases", {
    "name": "Suite TC B",
    "suite_id": s_id,
    "prompt": "Check something",
    "target_url": "https://example.org",
    "success_criteria": "Done",
})
case2 = check("POST suite-case B", s, case2, 200, lambda b: "id" in b)

s, run = _req("POST", f"{B}/api/test-suites/{s_id}/run")
run = check("POST suite/run (2 cases)", s, run, 200,
            lambda b: isinstance(b.get("job_ids"), list) and len(b["job_ids"]) == 2)
print("   -> job_ids:", run.get("job_ids"))

s, _ = _req("DELETE", f"{B}/api/test-suites/{s_id}")
check("DELETE suite", s, _, 204)

s, data = _req("DELETE", f"{B}/api/test-suites/{s_id}")
check("DELETE missing suite 404", s, data, 404)

# ---------------- Summary ----------------
print(f"\n=== Summary: {passed} passed, {failed} failed ===")
sys.exit(0 if failed == 0 else 1)
