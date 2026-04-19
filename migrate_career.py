"""Migration script: add admission_block, entry_score to university_major; create major_entry_score table. Run once."""
import sqlite3
import os

DB_PATH = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'database.db')


def migrate():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("PRAGMA table_info(university_major)")
    cols = [row[1] for row in cur.fetchall()]

    if 'admission_block' not in cols:
        cur.execute("ALTER TABLE university_major ADD COLUMN admission_block TEXT")
        print("Added admission_block")

    if 'entry_score' not in cols:
        cur.execute("ALTER TABLE university_major ADD COLUMN entry_score REAL")
        print("Added entry_score")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS major_entry_score (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            major_id INTEGER NOT NULL REFERENCES university_major(id) ON DELETE CASCADE,
            year INTEGER NOT NULL,
            score REAL NOT NULL,
            UNIQUE(major_id, year)
        )
    """)
    print("Created major_entry_score table")

    conn.commit()
    conn.close()
    print("Migration complete.")


if __name__ == '__main__':
    migrate()
