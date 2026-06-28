import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "ascel.db")

def cleanup_duplicates():
    print(f"Connecting to database at {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Find duplicates
    cursor.execute('''
        SELECT title, COUNT(*), MAX(confidence)
        FROM skills
        GROUP BY title
        HAVING COUNT(*) > 1
    ''')
    
    duplicates = cursor.fetchall()
    if not duplicates:
        print("No duplicate skills found.")
    else:
        print(f"Found {len(duplicates)} titles with duplicates.")
        
        for title, count, max_confidence in duplicates:
            print(f"Processing '{title}' (Count: {count}, Max Confidence: {max_confidence})")
            
            # Find the ID of the skill with the max confidence
            # If there are multiple with the same max confidence, we'll keep the first one we find
            cursor.execute('''
                SELECT id FROM skills
                WHERE title = ? AND confidence = ?
                LIMIT 1
            ''', (title, max_confidence))
            
            row = cursor.fetchone()
            if row:
                keep_id = row[0]
                
                # Delete all others
                cursor.execute('''
                    DELETE FROM skills
                    WHERE title = ? AND id != ?
                ''', (title, keep_id))
                
                deleted_count = cursor.rowcount
                print(f"  Deleted {deleted_count} duplicate entries for '{title}'.")
            
    conn.commit()
    
    # Apply Unique Index to prevent future duplicates
    try:
        cursor.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_skills_title ON skills(title)')
        print("Created UNIQUE INDEX 'idx_skills_title' on skills(title) successfully.")
    except sqlite3.Error as e:
        print(f"Error creating unique index: {e}")
        
    conn.commit()
    conn.close()
    print("Cleanup complete.")

if __name__ == "__main__":
    cleanup_duplicates()
