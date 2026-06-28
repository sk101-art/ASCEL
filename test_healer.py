import os
from healing_engine import HealingEngine

def test_healing_engine():
    healer = HealingEngine()

    print("--- Test 1: Suggest-Only (Should Block) ---")
    res1 = healer.run_healing_cycle("echo 'fixing'", None, "Suggest-Only")
    print(f"Result: {res1['status']}")

    print("\n--- Test 2: Auto-Heal Success ---")
    res2 = healer.run_healing_cycle("echo 'fixing'", "echo 'probing'", "Silent Auto-Heal")
    print(f"Result: {res2['status']}")

    print("\n--- Test 3: Auto-Heal Probe Failure (Rollback) ---")
    # We will write a dummy file in the fix, and the probe will fail.
    # The rollback should clean up the file (since it's untracked, git clean -fd will remove it).
    fix_cmd = "echo 'bad_code' > dummy_bad_file.txt"
    probe_cmd = "false" # Always fails on Linux/Mac. For Windows, we can use `exit 1` or a command that fails.
    
    # Check if dummy_bad_file.txt exists before
    if os.path.exists("dummy_bad_file.txt"):
        os.remove("dummy_bad_file.txt")
        
    res3 = healer.run_healing_cycle(fix_cmd, probe_cmd, "Silent Auto-Heal")
    print(f"Result: {res3['status']}")
    
    # Verify rollback
    if os.path.exists("dummy_bad_file.txt"):
        print("ERROR: Rollback failed! The file still exists.")
    else:
        print("SUCCESS: Rollback worked! The file was removed.")

if __name__ == "__main__":
    test_healing_engine()
