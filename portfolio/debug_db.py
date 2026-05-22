import sqlite3
import json
import os

db_path = 'messages.db'
output_path = 'db_check_result.txt'

try:
    if not os.path.exists(db_path):
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(f"Error: {db_path} does not exist.")
    else:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM messages ORDER BY created_at DESC").fetchall()
        data = [dict(r) for r in rows]
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(json.dumps(data, indent=2, ensure_ascii=False))
        conn.close()
except Exception as e:
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(f"Error: {str(e)}")
