"""One-time diagnostic: print all skill titles and embedding status from the vault."""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "ascel.db")
conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row

rows = conn.execute(
    "SELECT id, title, confidence, created_at, embedding FROM skills ORDER BY created_at DESC"
).fetchall()

print(f"\n=== Skill Vault ({len(rows)} skills) ===")
for r in rows:
    has_emb = bool(r["embedding"])
    tag = "EMB" if has_emb else "   "
    print(f"  [{tag}] conf={r['confidence']:.2f}  {r['title']}")

if not rows:
    print("  (empty \u2014 no skills have been distilled yet)")

print()
conn.close()
