import sqlite3
import logging
import os

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(__file__), "ascel.db")

def init_db():
    logger.info(f"Connecting to SQLite database at {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    logger.info("Creating tables...")
    
    # Primary skills table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS chat_journal (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        conversation_id TEXT NOT NULL,
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS skills (
        id TEXT PRIMARY KEY,
        title TEXT,
        tags TEXT,
        tech_stack TEXT,
        created_at TEXT,
        updated_at TEXT,
        confidence REAL,
        body_markdown TEXT,
        summary TEXT,
        conversation_hash TEXT,
        embedding TEXT
    )
    '''
)

    # FTS5 virtual table
    cursor.execute('''
    CREATE VIRTUAL TABLE IF NOT EXISTS skills_fts USING fts5(
        title, tags, tech_stack, summary, body_markdown,
        content=skills,
        content_rowid=id
    )
    ''')

    # Triggers to keep FTS5 synchronized
    # FTS5 external content triggers syntax requires 'rowid' which is implicitly aliased to the primary key in SQLite.
    
    cursor.execute('''
    CREATE TRIGGER IF NOT EXISTS skills_ai AFTER INSERT ON skills BEGIN
        INSERT INTO skills_fts (rowid, title, tags, tech_stack, summary, body_markdown)
        VALUES (new.rowid, new.title, new.tags, new.tech_stack, new.summary, new.body_markdown);
    END;
    ''')

    cursor.execute('''
    CREATE TRIGGER IF NOT EXISTS skills_ad AFTER DELETE ON skills BEGIN
        INSERT INTO skills_fts (skills_fts, rowid, title, tags, tech_stack, summary, body_markdown)
        VALUES ('delete', old.rowid, old.title, old.tags, old.tech_stack, old.summary, old.body_markdown);
    END;
    ''')

    cursor.execute('''
    CREATE TRIGGER IF NOT EXISTS skills_au AFTER UPDATE ON skills BEGIN
        INSERT INTO skills_fts (skills_fts, rowid, title, tags, tech_stack, summary, body_markdown)
        VALUES ('delete', old.rowid, old.title, old.tags, old.tech_stack, old.summary, old.body_markdown);
        INSERT INTO skills_fts (rowid, title, tags, tech_stack, summary, body_markdown)
        VALUES (new.rowid, new.title, new.tags, new.tech_stack, new.summary, new.body_markdown);
    END;
    ''')

    conn.commit()
    conn.close()
    logger.info("Database initialization complete.")

if __name__ == "__main__":
    init_db()