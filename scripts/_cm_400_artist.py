import os, psycopg2
dsn = os.environ["DATABASE_URL"]
if dsn.startswith("postgresql+asyncpg://"):
    dsn = "postgresql://" + dsn[len("postgresql+asyncpg://"):]
dsn = dsn.replace("?ssl=", "?sslmode=").replace("&ssl=", "&sslmode=")

with psycopg2.connect(dsn) as c, c.cursor() as cur:
    cur.execute("""
        SELECT response_status, url, params, last_error
        FROM chartmetric_request_queue
        WHERE completed_at > now() - interval '10 minutes'
          AND handler = 'artist_stats'
          AND response_status = 400
        LIMIT 15
    """)
    for r in cur.fetchall():
        print(f"status={r[0]} url={r[1]}")
        print(f"  params={r[2]}")
        print(f"  err={r[3]}")
        print()
