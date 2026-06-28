"""
ASCEL End-to-End Integration Test
==================================
Two simulated chat sessions over the real HTTP API:

  Chat A  -> multi-step debugging conversation -> distill into skill
  Chat B  -> new user asks a related question
             -> verify the skill is retrieved and injected

Run:  python e2e_test.py
Requires: backend on localhost:8000  +  distiller.py running
"""
import requests
import time
import uuid
import sys

BASE = "http://localhost:8000"
results = []

def PASS(label, detail=""):
    msg = f"[PASS] {label}"
    if detail:
        msg += f"  ->  {detail}"
    print(msg)
    results.append((label, True))
    return True

def FAIL(label, detail=""):
    msg = f"[FAIL] {label}"
    if detail:
        msg += f"  ->  {detail}"
    print(msg)
    results.append((label, False))
    return False

def check(label, condition, detail=""):
    return PASS(label, detail) if condition else FAIL(label, detail)

def sep(title=""):
    print()
    print("=" * 62)
    if title:
        print(f"  {title}")
        print("=" * 62)


# ----------------------------------------------------------------
sep("Step 0 - Health Check")
# ----------------------------------------------------------------
try:
    r = requests.get(f"{BASE}/health", timeout=5)
    check("Backend reachable", r.status_code == 200,
          r.json().get("status", ""))
except Exception as e:
    FAIL("Backend reachable", str(e))
    print("\n[FAIL] Cannot reach backend. Start it with:  python run_all.py")
    sys.exit(1)


# ----------------------------------------------------------------
sep("Step 1 - Skill Count Baseline")
# ----------------------------------------------------------------
r = requests.get(f"{BASE}/skills/count", timeout=5)
check("GET /skills/count returns 200", r.status_code == 200)
skill_count_before = r.json().get("count", 0)
print(f"[INFO] Skills in vault before test: {skill_count_before}")


# ----------------------------------------------------------------
sep("Step 2 - Chat Session A: Multi-Step Debugging Conversation")
# ----------------------------------------------------------------
chat_a_id = f"test_chat_a_{uuid.uuid4().hex[:8]}"
print(f"[INFO] Chat A ID: {chat_a_id}\n")

# A realistic conda + pandas debugging session (8 turns)
turns_a = [
    ("user",
     "I'm getting ModuleNotFoundError: No module named 'pandas' when I run my script."),
    ("assistant",
     "This usually means pandas is not installed in your active Python environment. "
     "Step 1: Verify which Python and pip you are using by running 'which python' "
     "and 'which pip'. They should both point to the same environment."),
    ("user",
     "They point to different places. python is in my conda env but pip is the system one."),
    ("assistant",
     "That is the root cause. Step 2: Install pandas into your conda env by running "
     "'python -m pip install pandas'. Using 'python -m pip' guarantees the install "
     "goes into the environment that owns that python binary."),
    ("user",
     "I ran that but now I get: ImportError: libstdc++.so.6: cannot open shared object file."),
    ("assistant",
     "This is a glibc/libstdc++ version mismatch between your conda env and the system. "
     "Step 3: Fix it with 'conda install -c conda-forge libstdcxx-ng'. This installs "
     "the correct C++ standard library inside your conda environment."),
    ("user",
     "That fixed it! pandas imported successfully and my script runs now."),
    ("assistant",
     "The complete fix chain was: (1) use 'python -m pip install pandas' instead of "
     "bare pip so the install targets your conda env, then (2) run "
     "'conda install -c conda-forge libstdcxx-ng' to resolve the libstdc++ mismatch. "
     "Both steps are required when mixing conda and pip in the same workflow."),
]

all_logged = True
for role, content in turns_a:
    r = requests.post(f"{BASE}/log-turn",
                      json={"conversation_id": chat_a_id,
                            "role": role, "content": content},
                      timeout=10)
    if r.status_code != 201:
        all_logged = False
        print(f"  [FAIL] log_turn ({role}): {r.status_code} {r.text}")

check("All 8 turns logged to Chat A", all_logged,
      f"conversation_id={chat_a_id}")

r = requests.get(f"{BASE}/chat/{chat_a_id}", timeout=5)
check("GET /chat/{id} returns full history",
      r.status_code == 200 and len(r.json()) == 8,
      f"{len(r.json())} turns returned")


# ----------------------------------------------------------------
sep("Step 3 - Distill Chat A into a Skill")
# ----------------------------------------------------------------
r = requests.post(f"{BASE}/save-skill",
                  json={"conversation_id": chat_a_id},
                  timeout=10)
check("POST /save-skill returns 202", r.status_code == 202,
      r.json().get("message", ""))

print("[INFO] Polling distillation-status (up to 120 s)...")
distill_status = "processing"
for attempt in range(40):
    time.sleep(3)
    try:
        sr = requests.get(f"{BASE}/distillation-status/{chat_a_id}",
                          timeout=5)
        distill_status = sr.json().get("status", "unknown")
        print(f"  [{attempt+1:02d}] status = {distill_status}", end="\r")
        if distill_status in ("completed", "failed", "idle"):
            break
    except Exception:
        pass

print()  # flush the \r line
check("Distillation completed", distill_status == "completed",
      f"final status = {distill_status}")

if distill_status != "completed":
    print("[WARN] Distillation did not complete.")
    print("[WARN] Make sure 'python distiller.py' is running in a separate terminal.")
    print("[WARN] Continuing with remaining checks against the existing vault.\n")


# ----------------------------------------------------------------
sep("Step 4 - Verify Skill Appears in Vault")
# ----------------------------------------------------------------
r = requests.get(f"{BASE}/skills/count", timeout=5)
skill_count_after = r.json().get("count", 0)
check("Skill count increased after distillation",
      skill_count_after > skill_count_before,
      f"{skill_count_before} -> {skill_count_after}")

r = requests.get(f"{BASE}/skills", timeout=5)
check("GET /skills returns array", r.status_code == 200 and isinstance(r.json(), list))
skills = r.json()
newest = skills[0] if skills else None

if newest:
    print(f"[INFO] Newest skill in vault:")
    print(f"       title        : {newest.get('title','(none)')}")
    print(f"       skill_id     : {newest.get('skill_id','(none)')}")
    print(f"       is_searchable: {newest.get('is_searchable')}")
    check("Newest skill has a title",  bool(newest.get("title")))
    check("skill_id field present",    bool(newest.get("skill_id")))


# ----------------------------------------------------------------
sep("Step 5 - Skill CRUD Endpoints")
# ----------------------------------------------------------------
if newest:
    sid = newest["skill_id"]

    r = requests.get(f"{BASE}/skills/{sid}/preview", timeout=5)
    check("GET /skills/{id}/preview returns 200", r.status_code == 200,
          f"content len={len(r.json().get('content',''))}")
    preview = r.json()
    check("Preview has content", bool(preview.get("content")))
    check("Preview has title",   bool(preview.get("title")))
    check("Preview has created_at", bool(preview.get("created_at")))

    r = requests.get(f"{BASE}/skills/{sid}/history", timeout=5)
    check("GET /skills/{id}/history returns 200", r.status_code == 200)
    hist = r.json().get("history", [])
    check("History has at least 1 entry", len(hist) >= 1,
          f"{len(hist)} entries")

    sha = hist[0]["full_sha"] if hist else "initial"
    r = requests.post(f"{BASE}/skills/{sid}/rollback/{sha}", timeout=5)
    check("POST rollback returns 200", r.status_code == 200,
          r.json().get("message", "")[:60])
else:
    FAIL("Skill CRUD checks skipped", "no skills in vault")


# ----------------------------------------------------------------
sep("Step 6 - Search and Filter Endpoints")
# ----------------------------------------------------------------
r = requests.get(f"{BASE}/skills",
                 params={"search": "pandas", "limit": 10},
                 timeout=5)
check("GET /skills?search=pandas returns 200", r.status_code == 200)
sr = r.json()
check("Search result is a list", isinstance(sr, list),
      f"{len(sr)} result(s)")

r = requests.get(f"{BASE}/skills", params={"limit": 3}, timeout=5)
check("GET /skills?limit=3 respects limit",
      isinstance(r.json(), list) and len(r.json()) <= 3,
      f"got {len(r.json())}")


# ----------------------------------------------------------------
sep("Step 7 - Chat Session B: New User Asks Related Question")
# ----------------------------------------------------------------
chat_b_id = f"test_chat_b_{uuid.uuid4().hex[:8]}"
print(f"[INFO] Chat B ID: {chat_b_id}")
print(f"[INFO] Query: 'pandas import fails with libstdc++ error in conda'")
print(f"[INFO] Waiting for Ollama response (timeout 120 s)...\n")

try:
    r = requests.post(
        f"{BASE}/chat",
        json={
            "conversation_id": chat_b_id,
            "message": "pandas import fails with libstdc++ error in conda",
        },
        timeout=120,
    )
    check("POST /chat returns 200", r.status_code == 200)
    body        = r.json()
    response    = body.get("response", "")
    used_skill  = body.get("used_skill")
    trust_tier  = body.get("trust_tier", "")

    print(f"\n[INFO] AI response (first 350 chars):")
    print(f"       {response[:350].strip()}")
    print()

    check("Response field non-empty",   bool(response))
    check("trust_tier field present",   bool(trust_tier), trust_tier)
    check("Skill injected (used_skill)", used_skill is not None,
          used_skill.get("title","") if used_skill
          else "None -- score below 0.50 threshold")

    if used_skill:
        print(f"[PASS] Injected skill: '{used_skill.get('title')}'  "
              f"score={used_skill.get('score',0):.4f}")
    else:
        print("[WARN] Skill NOT injected. Likely reasons:")
        print("       1. Newly distilled skill has no embedding yet.")
        print("          Fix: python retriever.py   (runs backfill_embeddings)")
        print("       2. Ollama returned zero-vector; FTS5 score was below 0.50.")
        print("       3. Skill tags/title don't match 'pandas libstdc++ conda'.")

except requests.exceptions.ReadTimeout:
    FAIL("POST /chat returned within 120 s", "Ollama timed out")
except Exception as e:
    FAIL("POST /chat", str(e))


# ----------------------------------------------------------------
sep("Step 8 - SSE Endpoint")
# ----------------------------------------------------------------
try:
    r = requests.get(f"{BASE}/events/skills", stream=True, timeout=4)
    check("GET /events/skills returns 200", r.status_code == 200)
    ct = r.headers.get("Content-Type", "")
    check("Content-Type is text/event-stream", "text/event-stream" in ct, ct)
    chunk = next(r.iter_content(chunk_size=64), b"")
    check("First SSE chunk contains 'ping'", b"ping" in chunk,
          chunk.decode(errors="replace").strip())
    r.close()
except Exception as e:
    FAIL("SSE endpoint", str(e))


# ----------------------------------------------------------------
sep("Step 9 - Cleanup Test Data")
# ----------------------------------------------------------------
r = requests.delete(f"{BASE}/chat/{chat_a_id}", timeout=5)
check("DELETE Chat A", r.status_code == 200)
r = requests.delete(f"{BASE}/chat/{chat_b_id}", timeout=5)
check("DELETE Chat B", r.status_code == 200)


# ----------------------------------------------------------------
sep("FINAL RESULTS")
# ----------------------------------------------------------------
passed = sum(1 for _, ok in results if ok)
failed = sum(1 for _, ok in results if not ok)
total  = len(results)
print(f"\n  [PASS] {passed}/{total} checks passed")
if failed:
    print(f"  [FAIL] {failed}/{total} checks FAILED:")
    for label, ok in results:
        if not ok:
            print(f"         * {label}")
print()
sys.exit(0 if failed == 0 else 1)
