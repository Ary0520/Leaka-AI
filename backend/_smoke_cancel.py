import urllib.request, json

def req(method, url, body=None, hdr=None):
    data = json.dumps(body).encode() if body else None
    h = {"Content-Type": "application/json"} if data else {}
    if hdr:
        h.update(hdr)
    rq = urllib.request.Request(url, data=data, method=method, headers=h)
    try:
        with urllib.request.urlopen(rq, timeout=10) as r:
            raw = r.read()
            return r.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as e:
        raw = e.read()
        return e.code, (json.loads(raw) if raw else {})

B = "http://127.0.0.1:8000"
passed = failed = 0

def check(label, cond):
    global passed, failed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed += 1
        print(f"  [FAIL] {label}")

# 1. Enqueue a run then immediately cancel
c, b = req("POST", f"{B}/api/tests/run", {
    "prompt": "cancel-smoke-test",
    "target_url": "https://example.com",
    "name": "cancel-smoke",
})
check("POST enqueue run", c == 200 and "job_id" in b)
job = b["job_id"]

c2, b2 = req("GET", f"{B}/api/tests/status/{job}")
current_status = b2.get("status")
print(f"  Status after enqueue: {current_status}")

if current_status in ("pending", "running"):
    c3, b3 = req("POST", f"{B}/api/tests/{job}/cancel")
    check("POST cancel active run -> cancelled", c3 == 200 and b3.get("status") == "cancelled")
    c4, b4 = req("POST", f"{B}/api/tests/{job}/cancel")
    check("POST cancel already-cancelled -> 409", c4 == 409)
else:
    print(f"  [INFO] Run already terminal ({current_status}) before cancel — correct: no Ollama")
    c3, b3 = req("POST", f"{B}/api/tests/{job}/cancel")
    check("POST cancel terminal run -> 409", c3 == 409)

# 2. 404 on nonexistent
c5, b5 = req("POST", f"{B}/api/tests/doesnotexist999/cancel")
check("POST cancel nonexistent -> 404", c5 == 404)

print(f"\n  {passed} passed, {failed} failed")
