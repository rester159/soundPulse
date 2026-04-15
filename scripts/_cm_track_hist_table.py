"""Has track_stat_history ever received any data?"""
import os, psycopg2
dsn = os.environ["DATABASE_URL"]
if dsn.startswith("postgresql+asyncpg://"):
    dsn = "postgresql://" + dsn[len("postgresql+asyncpg://"):]
dsn = dsn.replace("?ssl=", "?sslmode=").replace("&ssl=", "&sslmode=")

with psycopg2.connect(dsn) as c, c.cursor() as cur:
    cur.execute("SELECT COUNT(*), MAX(pulled_at), MIN(pulled_at) FROM track_stat_history")
    total, newest, oldest = cur.fetchone()
    print(f"track_stat_history total rows: {total}")
    print(f"  oldest: {oldest}")
    print(f"  newest: {newest}")

    cur.execute("""
        SELECT platform, metric, COUNT(*) FROM track_stat_history
        GROUP BY platform, metric ORDER BY COUNT(*) DESC LIMIT 10
    """)
    print("\nBy platform + metric:")
    for r in cur.fetchall():
        print(f"  {r[0]:10} {r[1]:20} n={r[2]}")

    cur.execute("""
        SELECT track_id, platform, metric, snapshot_date, value, pulled_at
        FROM track_stat_history ORDER BY pulled_at DESC LIMIT 3
    """)
    print("\nLatest 3 rows:")
    for r in cur.fetchall():
        print(f"  {r[5]} track={str(r[0])[:8]} {r[1]}/{r[2]} date={r[3]} value={r[4]}")
