import subprocess
import time
import requests
import os
import json

print("Starting FastAPI server...")
proc = subprocess.Popen(["uvicorn", "main:app", "--port", "8000"])

try:
    time.sleep(2)
    
    print("Logging user turn...")
    r1 = requests.post("http://127.0.0.1:8000/log-turn", json={
        "conversation_id": "test_conv_123",
        "role": "user",
        "content": "How do I fix stdbool.h not found?"
    })
    print(r1.status_code, r1.json())
    
    print("Logging assistant turn...")
    r2 = requests.post("http://127.0.0.1:8000/log-turn", json={
        "conversation_id": "test_conv_123",
        "role": "assistant",
        "content": "Include the stdbool library."
    })
    print(r2.status_code, r2.json())
    
    print("Triggering save skill...")
    r3 = requests.post("http://127.0.0.1:8000/save-skill", json={
        "conversation_id": "test_conv_123"
    })
    print(r3.status_code, r3.json())
    
    trigger_file = os.path.join("triggers", "test_conv_123.json")
    if os.path.exists(trigger_file):
        print(f"SUCCESS: {trigger_file} exists on disk!")
        with open(trigger_file, "r", encoding="utf-8") as f:
            print("Contents:")
            print(json.dumps(json.load(f), indent=2))
    else:
        print(f"FAILED: {trigger_file} not found!")

finally:
    print("Terminating server...")
    proc.terminate()
    proc.wait()
    print("Test Complete.")
