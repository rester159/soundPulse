"""Which URLs are triggering the 'No date was given' error
and which ones are still writing dry-mode status=0?"""
import os, psycopg2
dsn = os.environ["DATABASE_URL"]
if dsn.startswith("postgresql+asyncpg://"):
    dsn = "postgresql://" + dsn[len("postgresql+asyncpg://"):]
dsn = dsn.replace("?ssl=", "?sslmode=").replace("&ssl=", "&sslmode=")

with psycopg2.connect(dsn) as c, c.cursor() as cur:
    print("=== 'No date' 400s in last 10 min ===")
    cur.execute("""
        SELECT url, params, last_error
        FROM chartmetric_request_queue
        WHERE completed_at > now() - interval '10 minutes'
          AND response_status = 400
          AND last_error LIKE '%date%'
        LIMIT 10
    """)
    for r in cur.fetchall():
        print(f"  url={r[0]}")
        print(f"    params={r[1]}")
        print(f"    err={r[2][:200]}")

    print()
    print("=== Most recent dry-mode status=0 rows (last 2 min) ===")
    cur.execute("""
        SELECT handler, url, params, completed_at
        FROM chartmetric_request_queue
        WHERE completed_at > now() - interval '2 minutes'
          AND response_status = 0
        ORDER BY completed_at DESC LIMIT 10
    """)
    for r in cur.fetchall():
        print(f"  {r[3]}  handler={r[0]}  url={r[1][:70]}")
        print(f"    params={r[2]}")

    print()
    print("=== All status breakdown, last 2 min ===")
    cur.execute("""
        SELECT response_status, handler, COUNT(*) AS n
        FROM chartmetric_request_queue
        WHERE completed_at > now() - interval '2 minutes'
        GROUP BY response_status, handler
        ORDER BY handler, response_status NULLS LAST
    """)
    for r in cur.fetchall():
        print(f"  handler={r[1]:14} status={str(r[0]):5} n={r[2]}")
