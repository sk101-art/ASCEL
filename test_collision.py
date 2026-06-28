import requests
import json
import time

URL = "http://localhost:8000/chat"

def test_query(message: str, expected_key: str):
    print(f"Testing query: '{message}'")
    try:
        response = requests.post(URL, json={
            "conversation_id": "test_collision",
            "message": message
        })
        response.raise_for_status()
        data = response.json()
        
        print("Response Metadata:", json.dumps({k: v for k, v in data.items() if k != "response"}, indent=2))
        
        if expected_key in data and data[expected_key] is not None:
            print(f"PASS: Expected key '{expected_key}' found.\n")
        else:
            print(f"FAIL: Expected key '{expected_key}' not found or was None.\n")
            
    except Exception as e:
        print(f"Error testing query: {e}")

if __name__ == "__main__":
    print("Running Context Collision Tests...\n")
    test_query("fatal error: stdbool.h not found", "used_skill")
    time.sleep(2)  # Give the backend a brief moment
    test_query("My audio sounds weird", "reason")
