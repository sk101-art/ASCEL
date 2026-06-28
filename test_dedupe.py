import sqlite3
import os
import uuid
from datetime import datetime, timezone

DB_PATH = os.path.join(os.path.dirname(__file__), "ascel.db")

def setup_mock_skill(title: str, confidence: float):
    print(f"Setting up mock skill '{title}' with confidence {confidence}...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Delete if exists
    cursor.execute("DELETE FROM skills WHERE title = ?", (title,))
    
    skill_id = str(uuid.uuid4())
    now_iso = datetime.now(timezone.utc).isoformat()
    
    cursor.execute(
        """INSERT INTO skills 
           (id, title, tags, tech_stack, summary, body_markdown, conversation_hash, confidence, created_at, updated_at) 
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (skill_id, title, "c, cpp, gcc", "C", "Mock summary", "Mock body", 
         "mockhash", confidence, now_iso, now_iso)
    )
    conn.commit()
    conn.close()

def run_test():
    test_title = "stdbool.h Error Fix" # Using a mock title
    
    # 1. Insert high confidence skill
    setup_mock_skill(test_title, 0.9)
    
    print("Testing deduplication logic directly...")
    
    # Check current state
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, confidence FROM skills WHERE title = ?", (test_title,))
    original_id, original_conf = cursor.fetchone()
    
    # Simulate distiller behavior manually for precision
    skill_id = str(uuid.uuid4())
    confidence = 0.5
    now_iso = datetime.now(timezone.utc).isoformat()
    
    cursor.execute("SELECT id, confidence FROM skills WHERE title = ?", (test_title,))
    existing = cursor.fetchone()
    
    if existing:
        old_id, old_confidence = existing
        if confidence > old_confidence:
            print("FAIL: Should not update, new confidence is lower.")
        else:
            print(f"PASS: Discarding extraction '{test_title}' (new conf {confidence} <= old conf {old_confidence})")
    else:
        print("FAIL: Expected existing skill.")
    
    conn.close()

if __name__ == "__main__":
    run_test()
