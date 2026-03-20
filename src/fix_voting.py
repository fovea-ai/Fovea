"""
One-time fix for submissions stuck in 'voting' status.

Run this once from your Fovea folder:
    python fix_voting.py

This will approve all submissions that were accepted by a moderator
but never got enough votes under the old 20-vote system.
After running this, you can delete this file.
"""

import sys
import os

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, THIS_DIR)
os.chdir(THIS_DIR)

from core.storage import DB_PATH, init_db
import sqlite3

init_db()

conn = sqlite3.connect(DB_PATH)
c    = conn.cursor()

# Show what's stuck
c.execute("""
    SELECT id, description, submitted_by, votes_yes, votes_no, created_at
    FROM training_submissions
    WHERE status = 'voting'
    ORDER BY created_at ASC
""")
rows = c.fetchall()

if not rows:
    print("Nothing to fix — no submissions are stuck in 'voting'.")
    conn.close()
    input("\nPress Enter to close...")
else:
    print(f"Found {len(rows)} submission(s) stuck in 'voting':\n")
    for r in rows:
        print(f"  ID {r[0]}: '{r[1][:60]}' by {r[2]}")
        print(f"          Votes: yes={r[3]}, no={r[4]}  |  Created: {r[5][:16]}")
        print()

    confirm = input(f"Approve all {len(rows)} of these? (yes/no): ").strip().lower()

    if confirm == "yes":
        c.execute("""
            UPDATE training_submissions
            SET status = 'approved'
            WHERE status = 'voting'
        """)
        conn.commit()
        print(f"\nDone. Approved {c.rowcount} submission(s).")
    else:
        print("Cancelled — nothing changed.")

conn.close()
input("\nPress Enter to close...")