"""Which specific URLs + endpoint_keys are producing 400s right now?"""
import os, psycopg2
dsn = os.environ["DATABASE_URL"]
if dsn.startswith("postgresql+asyncpg://"):
    dsn = "postgresql://" + dsn[len("postgresql+asyncpg://"):]
dsn = dsn.replace("?ssl=", "?sslmode=").replace("&ssl=", "&sslmode=")

with psycopg2.connect(dsn) as c, c.cursor() as cur:
    cur.execute("""
        SELECT handler, url, params, handler_context, last_error
        FROM chartmetric_request_queue
        WHERE completed_at > now() - interval '5 minutes'
          AND response_status = 400
        LIMIT 20
    """)
    for r in cur.fetchall():
        print(f"handler={r[0]} url={r[1]}")
        print(f"  params={r[2]}")
        print(f"  ctx={r[3]}")
        print(f"  err={r[4]}")
        print()
