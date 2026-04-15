import os, psycopg2
dsn = os.environ["DATABASE_URL"]
if dsn.startswith("postgresql+asyncpg://"):
    dsn = "postgresql://" + dsn[len("postgresql+asyncpg://"):]
dsn = dsn.replace("?ssl=", "?sslmode=").replace("&ssl=", "&sslmode=")

with psycopg2.connect(dsn) as conn, conn.cursor() as cur:
    cur.execute("""
        UPDATE chartmetric_request_queue
        SET completed_at = now(),
            response_status = 0,
            last_error = 'purged: stale youtube platform before youtube_channel rename'
        WHERE completed_at IS NULL
          AND handler = 'artist_stats'
          AND handler_context->>'platform' = 'youtube'
    """)
    print(f"purged {cur.rowcount} stale artist_stats/youtube rows")
    conn.commit()
