import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "ascel.db")

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()
cursor.execute("PRAGMA table_info(chat_journal)")
for row in cursor.fetchall():
    print(row)
conn.close()
