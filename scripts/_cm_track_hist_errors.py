"""Dump recent track_history errors + an instance log tail."""
import os, psycopg2
dsn = os.environ["DATABASE_URL"]
if dsn.startswith("postgresql+asyncpg://"):
    dsn = "postgresql://" + dsn[len("postgresql+asyncpg://"):]
dsn = dsn.replace("?ssl=", "?sslmode=").replace("&ssl=", "&sslmode=")

with psycopg2.connect(dsn) as c, c.cursor() as cur:
    print("=== track_history status breakdown, last 30 min ===")
    cur.execute("""
        SELECT response_status, COUNT(*) AS n
        FROM chartmetric_request_queue
        WHERE completed_at > now() - interval '30 minutes'
          AND handler = 'track_history'
        GROUP BY response_status
        ORDER BY response_status NULLS LAST
    """)
    for r in cur.fetchall():
        print(f"  status={str(r[0]):5} n={r[1]}")

    print()
    print("=== sample track_history errors (last 30 min, not 200) ===")
    cur.execute("""
        SELECT response_status, url, params, last_error
        FROM chartmetric_request_queue
        WHERE completed_at > now() - interval '30 minutes'
          AND handler = 'track_history'
          AND (response_status IS NULL OR response_status NOT BETWEEN 200 AND 299)
        LIMIT 10
    """)
    for r in cur.fetchall():
        print(f"  status={r[0]} url={r[1]}")
        print(f"    params={r[2]}")
        print(f"    err={(r[3] or '')[:160]}")

    print()
    print("=== any successes at all? ===")
    cur.execute("""
        SELECT response_status, handler, url, completed_at
        FROM chartmetric_request_queue
        WHERE response_status BETWEEN 200 AND 299
          AND handler = 'track_history'
        ORDER BY completed_at DESC LIMIT 5
    """)
    rows = cur.fetchall()
    if not rows:
        print("  (no track_history 2xx rows ever)")
    for r in rows:
        print(f"  {r[3]} {r[0]} {r[2]}")
