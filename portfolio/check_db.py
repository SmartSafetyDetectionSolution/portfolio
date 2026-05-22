import sqlite3
import json

conn = sqlite3.connect('messages.db')
conn.row_factory = sqlite3.Row
rows = conn.execute("SELECT * FROM messages").fetchall()
print(json.dumps([dict(r) for r in rows], indent=2, ensure_ascii=False))
conn.close()
