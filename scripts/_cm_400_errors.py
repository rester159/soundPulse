"""Dump the full 400-error URLs + params + error messages."""
import os, psycopg2

dsn = os.environ["DATABASE_URL"]
if dsn.startswith("postgresql+asyncpg://"):
    dsn = "postgresql://" + dsn[len("postgresql+asyncpg://"):]
dsn = dsn.replace("?ssl=", "?sslmode=").replace("&ssl=", "&sslmode=")

with psycopg2.connect(dsn) as c, c.cursor() as cur:
    cur.execute("""
        SELECT handler, response_status, url, params, last_error
        FROM chartmetric_request_queue
        WHERE completed_at > now() - interval '5 minutes'
          AND response_status = 400
        LIMIT 20
    """)
    rows = cur.fetchall()
    print(f"=== {len(rows)} 400 errors in last 5min ===")
    for r in rows:
        print(f"{r[0]:16} status={r[1]} url={r[2]}")
        print(f"  params={r[3]}")
        print(f"  err={r[4]}")
        print()
