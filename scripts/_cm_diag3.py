"""Last-60-seconds completion snapshot."""
import os, psycopg2

dsn = os.environ["DATABASE_URL"]
if dsn.startswith("postgresql+asyncpg://"):
    dsn = "postgresql://" + dsn[len("postgresql+asyncpg://"):]
dsn = dsn.replace("?ssl=", "?sslmode=").replace("&ssl=", "&sslmode=")

with psycopg2.connect(dsn) as conn, conn.cursor() as cur:
    cur.execute("""
        SELECT response_status, last_error, COUNT(*) AS n
        FROM chartmetric_request_queue
        WHERE completed_at > now() - interval '60 seconds'
        GROUP BY response_status, last_error
        ORDER BY n DESC
    """)
    print("=== last 60 seconds: status + error breakdown ===")
    rows = cur.fetchall()
    if not rows:
        print("  (no completions in the last 60s)")
    for r in rows:
        print(f"  status={str(r[0]):5} n={r[2]:5} err={(r[1] or '')[:60]}")

    cur.execute("""
        SELECT response_status, handler, LEFT(url, 60) AS u, last_error, completed_at
        FROM chartmetric_request_queue
        WHERE completed_at > now() - interval '30 seconds'
        ORDER BY completed_at DESC LIMIT 15
    """)
    print()
    print("=== last 30 seconds: individual rows (most recent first) ===")
    rows = cur.fetchall()
    if not rows:
        print("  (none)")
    for r in rows:
        print(f"  {r[4]}  status={str(r[0]):5}  handler={r[1]:14}  err={(r[3] or '')[:40]}")
