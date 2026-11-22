import sqlite3

db_path = 'c:/Users/justf/Downloads/ForensicLedger_AutoDemo/ForensicLedger/backend/forensicledger.db'
conn = sqlite3.connect(db_path)
c = conn.cursor()
c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
tables = [r[0] for r in c.fetchall()]
print('Database Tables:', tables)

for t in tables:
    c.execute(f"PRAGMA table_info({t});")
    cols = [(r[1], r[2], "PK" if r[5] else "") for r in c.fetchall()]
    c.execute(f"SELECT count(*) FROM {t};")
    count = c.fetchone()[0]
    print(f"\n=======================================================")
    print(f"TABLE: {t} (Row count: {count})")
    print("-------------------------------------------------------")
    for col in cols:
        print(f"  {col[0]:<16} : {col[1]:<10} {col[2]}")
    
    c.execute(f"SELECT * FROM {t} LIMIT 1;")
    sample = c.fetchone()
    if sample:
        masked = list(sample)
        if t == 'users' and len(masked) > 2:
            masked[2] = "[HMAC_SHA256_SALTED_HASH_PROTECTED]"
        print("  Sample Record   :", masked)
