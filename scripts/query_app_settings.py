import sqlite3
from pathlib import Path

p = Path(r"C:\Users\rohit\AppData\Local\Temp\CafePOS-Test\CafePOS\data\cafe.db")
if not p.exists():
    print('DB not found', p)
    raise SystemExit(1)
conn = sqlite3.connect(str(p))
c = conn.cursor()
try:
    c.execute('SELECT key, value FROM app_settings')
    rows = c.fetchall()
    for k,v in rows:
        print(f"{k}: {v}")
finally:
    conn.close()
