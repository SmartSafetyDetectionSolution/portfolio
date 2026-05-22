import sqlite3
import json
import os

db_path = 'messages.db'
output_path = 'db_full_check.txt'

try:
    if not os.path.exists(db_path):
        data = {"error": "Database not found"}
    else:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        
        messages = [dict(r) for r in conn.execute("SELECT * FROM messages ORDER BY created_at DESC").fetchall()]
        posts = [dict(r) for r in conn.execute("SELECT * FROM posts ORDER BY created_at DESC").fetchall()]
        
        data = {
            "messages": messages,
            "posts": posts
        }
        conn.close()
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(json.dumps(data, indent=2, ensure_ascii=False))
except Exception as e:
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(f"Error: {str(e)}")
