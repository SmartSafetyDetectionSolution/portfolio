import sqlite3
import json
import os

db_path = 'temp_zip_db/messages.db'
output_path = 'zip_db_check.txt'

if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    messages = [dict(r) for r in conn.execute("SELECT * FROM messages ORDER BY created_at DESC").fetchall()]
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(json.dumps(messages, indent=2, ensure_ascii=False))
    conn.close()
else:
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("DB not found in extracted folder.")
