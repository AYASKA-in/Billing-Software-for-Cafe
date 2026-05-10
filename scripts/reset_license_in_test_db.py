import sqlite3
from pathlib import Path

p = Path(r"C:\Users\rohit\AppData\Local\Temp\CafePOS-Test\CafePOS\data\cafe.db")
print('Using DB:', p)
if not p.exists():
    print('DB not found; nothing to do.')
    raise SystemExit(0)

conn = sqlite3.connect(str(p))
c = conn.cursor()

# Inspect table columns
c.execute("PRAGMA table_info('app_settings')")
cols = [r[1] for r in c.fetchall()]
print('app_settings columns:', cols)

text_cols = [cname for cname in cols if cname.lower() in ('key','name','setting_key','setting_name','k','setting')]
value_cols = [cname for cname in cols if cname.lower() in ('value','val','setting_value')]

deleted = 0
# Try common schemas
if 'key' in cols:
    for k in ('license_token','license_payload_json','license_last_seen_date'):
        c.execute('DELETE FROM app_settings WHERE key=?', (k,))
        deleted += c.rowcount
elif 'name' in cols:
    for k in ('license_token','license_payload_json','license_last_seen_date'):
        c.execute('DELETE FROM app_settings WHERE name=?', (k,))
        deleted += c.rowcount
else:
    # Fallback: delete rows where any column contains 'license' or token pattern
    for col in cols:
        try:
            c.execute(f"DELETE FROM app_settings WHERE {col} LIKE ?", ('%license_%',))
            deleted += c.rowcount
        except Exception:
            pass
        try:
            c.execute(f"DELETE FROM app_settings WHERE {col} LIKE ?", ('%CAFEPOS1-%',))
            deleted += c.rowcount
        except Exception:
            pass

conn.commit()

# Show remaining rows that look license-related
results = []
for col in cols:
    try:
        c.execute(f"SELECT {', '.join(cols)} FROM app_settings WHERE {col} LIKE ? LIMIT 10", ('%license%',))
        rows = c.fetchall()
        for r in rows:
            results.append(r)
    except Exception:
        pass

print(f'Deleted ~{deleted} rows (best-effort).')
if results:
    print('Remaining rows matching "license":')
    for r in results:
        print(r)
else:
    print('No remaining license-like rows found.')

conn.close()
print('Done.')
