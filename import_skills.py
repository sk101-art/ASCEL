import os
import sqlite3
import yaml
import datetime

DB_PATH = 'ascel.db'

def init_db():
    import database
    database.init_db()

def import_skills():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

    skills_dir = 'skills'
    for file in os.listdir(skills_dir):
        if file.endswith('.md'):
            path = os.path.join(skills_dir, file)
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if content.startswith('---'):
                parts = content.split('---', 2)
                if len(parts) >= 3:
                    frontmatter = parts[1]
                    body = parts[2].strip()
                    meta = yaml.safe_load(frontmatter)
                    
                    skill_id = meta.get('skill_id', file.replace('.md', ''))
                    title = meta.get('title', '')
                    summary = meta.get('summary', '')
                    tags = meta.get('title', '')
                    ts = meta.get('tech_stack', [])
                    tech_stack = ', '.join(ts) if isinstance(ts, list) else str(ts)
                    
                    cursor.execute('''
                        INSERT OR REPLACE INTO skills
                        (id, title, tags, tech_stack, summary, body_markdown, confidence, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (skill_id, title, tags, tech_stack, summary, body, 1.0, now_iso, now_iso))
    conn.commit()
    conn.close()

if __name__ == '__main__':
    init_db()
    import_skills()
    import retriever
    retriever.backfill_embeddings()
