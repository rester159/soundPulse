"""One-shot: disable track_stat_* endpoint configs AND purge
pending track_history jobs. After Chartmetric's internal-API-tier
gate was discovered, track_history needs to be fully shut down so
it stops burning quota on a class of calls our plan can't make.
"""
import os
import psycopg2

dsn = os.environ["DATABASE_URL"]
if dsn.startswith("postgresql+asyncpg://"):
    dsn = "postgresql://" + dsn[len("postgresql+asyncpg://"):]
dsn = dsn.replace("?ssl=", "?sslmode=").replace("&ssl=", "&sslmode=")

with psycopg2.connect(dsn) as conn, conn.cursor() as cur:
    # 1. Flip all track_stat_* config rows to disabled.
    cur.execute("""
        UPDATE chartmetric_endpoint_config
        SET enabled = false,
            notes = COALESCE(notes, '') || ' [disabled 2026-04-15: internal-API-tier gate]',
            updated_at = now()
        WHERE endpoint_key LIKE 'track_stat_%'
          AND enabled = true
    """)
    cfg_n = cur.rowcount
    print(f"disabled {cfg_n} track_stat_* config rows")

    # 2. Mark pending track_history jobs completed with a purge tag.
    cur.execute("""
        UPDATE chartmetric_request_queue
        SET completed_at = now(),
            response_status = 0,
            last_error = 'purged: track_history disabled (tier gate)'
        WHERE completed_at IS NULL
          AND handler = 'track_history'
    """)
    q_n = cur.rowcount
    print(f"purged {q_n} pending track_history queue rows")

    conn.commit()
