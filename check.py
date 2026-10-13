"""Pre-flight check: confirms the Audiences API is running and every read endpoint responds.

    python3 check.py              # checks http://127.0.0.1:8788
    python3 check.py --port 9000

Read-only: it never creates or changes anything.
"""
import json, sys, urllib.error, urllib.request

KEY = "sk_test_audiences_2026"
port = 8788
if "--port" in sys.argv:
    port = int(sys.argv[sys.argv.index("--port") + 1])
BASE = f"http://127.0.0.1:{port}"


def get(path, key=KEY):
    req = urllib.request.Request(BASE + path)
    if key:
        req.add_header("X-Api-Key", key)
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def post(path, body):
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode(), method="POST")
    req.add_header("X-Api-Key", KEY)
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=5) as r:
        return r.status, json.loads(r.read())


checks = [
    ("server is up", lambda: get("/health", key=None)[0] == 200),
    ("API key accepted", lambda: get("/genres")[0] == 200),
    ("genres and languages", lambda: len(get("/genres")[1]["genres"]) > 0),
    ("geography (states)", lambda: get("/geo?type=state")[1]["total"] > 0),
    ("geography (DMAs)", lambda: get("/geo?type=dma")[1]["total"] > 0),
    ("content search", lambda: get("/content/search?q=football")[1]["total"] > 0),
    ("content by id", lambda: get("/content/ct-001")[0] == 200),
    ("segment list", lambda: get("/segments")[1]["total"] > 0),
    ("segment by id", lambda: get("/segments/seg-001")[0] == 200),
    ("size estimate", lambda: post("/estimate", {"definition": {"genres": ["golf"]}})[1]["estimated_households"] > 0),
]

failed = 0
for name, fn in checks:
    try:
        ok = fn()
    except Exception as e:
        ok, name = False, f"{name} ({e.__class__.__name__}: {e})"
    failed += not ok
    print(f"  {'OK  ' if ok else 'FAIL'}  {name}")

if failed:
    print(f"\n{failed} check(s) failed. Is the server running on port {port}? Start it with: python3 server.py")
    sys.exit(1)
print("\nAll good. Read BRIEF.md and API.md, then start building.")
