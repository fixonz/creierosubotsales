import sqlite3
import os

def dump_db(path):
    if not os.path.exists(path):
        print(f"File not found: {path}")
        return
    print(f"--- DUMPING {path} ---")
    conn = sqlite3.connect(path)
    cursor = conn.cursor()
    cursor.execute("SELECT id, amount_expected, address_used, created_at, status FROM sales ORDER BY id DESC LIMIT 10")
    rows = cursor.fetchall()
    for r in rows:
        print(r)
    conn.close()

dump_db("a1_z1_c1_2c2/bot_database.sqlite")
dump_db("bot_database.sqlite")
