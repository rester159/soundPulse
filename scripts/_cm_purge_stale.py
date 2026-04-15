"""Mark pending chart_sweep jobs that don't have latest=true as
completed with a 'stale-purge' error. These were enqueued by the
pre-3700dee planner and will otherwise 400 with 'No date was given'
until they drain naturally.

One-shot — do not re-run unless you know another stale batch needs
the same treatment.
"""
import os
import psycopg2

dsn = os.environ["DATABASE_URL"]
if dsn.startswith("postgresql+asyncpg://"):
    dsn = "postgresql://" + dsn[len("postgresql+asyncpg://"):]
dsn = dsn.replace("?ssl=", "?sslmode=").replace("&ssl=", "&sslmode=")

with psycopg2.connect(dsn) as conn, conn.cursor() as cur:
    cur.execute("""
        UPDATE chartmetric_request_queue
        SET completed_at = now(),
            response_status = 0,
            last_error = 'stale-purge'
        WHERE completed_at IS NULL
          AND handler = 'chart_sweep'
          AND NOT (params ? 'latest')
    """)
    n = cur.rowcount
    conn.commit()
    print(f"purged {n} stale pending chart_sweep rows")
