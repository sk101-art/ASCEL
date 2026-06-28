import subprocess
import time
import os
import json
import sqlite3

# Create a fresh test_conv_123.json to test the startup scan
triggers_dir = "triggers"
if not os.path.exists(triggers_dir):
    os.makedirs(triggers_dir)

trigger_file = os.path.join(triggers_dir, "test_conv_123.json")
test_log = [
  {
    "role": "user",
    "content": "How do I fix stdbool.h not found?",
    "timestamp": "2026-06-28 14:03:19"
  },
  {
    "role": "assistant",
    "content": "Include the stdbool library.",
    "timestamp": "2026-06-28 14:03:19"
  }
]
with open(trigger_file, "w") as f:
    json.dump(test_log, f)

print("Starting distiller.py...")
proc = subprocess.Popen(["python", "distiller.py"])

try:
    print("Waiting 35 seconds for Ollama inference and VRAM eviction...")
    time.sleep(35)
    
    if not os.path.exists(trigger_file):
        print(f"SUCCESS: {trigger_file} has been successfully deleted!")
    else:
        print(f"FAILED: {trigger_file} still exists!")
        
    print("Fetching extracted skill from database...")
    conn = sqlite3.connect("ascel.db")
    c = conn.cursor()
    # Fetch the most recent skill
    c.execute("SELECT title, summary FROM skills ORDER BY created_at DESC LIMIT 1")
    row = c.fetchone()
    if row:
        print("\n--- Extracted Skill ---")
        print(f"Title: {row[0]}")
        print(f"Summary: {row[1]}")
        print("-----------------------\n")
        print("SUCCESS: Database record verified.")
    else:
        print("FAILED: No skill found in database.")
    conn.close()
    
finally:
    print("Terminating distiller.py...")
    proc.terminate()
    proc.wait()
    print("Test Complete.")
