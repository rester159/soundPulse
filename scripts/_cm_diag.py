"""Diagnostic: which Chartmetric scrapers are still enabled in
scraper_configs, and which endpoints in the last hour's queue are
actually 429'ing.
"""
import os
import sys
import psycopg2


def normalize_dsn(dsn: str) -> str:
    if dsn.startswith("postgresql+asyncpg://"):
        dsn = "postgresql://" + dsn[len("postgresql+asyncpg://"):]
    return dsn.replace("?ssl=", "?sslmode=").replace("&ssl=", "&sslmode=")


def main() -> int:
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        print("DATABASE_URL not set", file=sys.stderr)
        return 2
    with psycopg2.connect(normalize_dsn(dsn)) as conn:
        with conn.cursor() as cur:
            print("=" * 60)
            print("LEGACY SCRAPER STATE (should all be disabled except new)")
            print("=" * 60)
            cur.execute("""
                SELECT id, enabled, interval_hours, last_status, last_run_at
                FROM scraper_configs
                WHERE id LIKE 'chartmetric%'
                ORDER BY id
            """)
            for row in cur.fetchall():
                print(f"  {row[0]:38} enabled={str(row[1]):5} interval={row[2]}h status={row[3]} last_run={row[4]}")

            print()
            print("=" * 60)
            print("QUEUE: response_status breakdown, last 1h")
            print("=" * 60)
            cur.execute("""
                SELECT response_status, handler, COUNT(*) AS n
                FROM chartmetric_request_queue
                WHERE completed_at > now() - interval '1 hour'
                GROUP BY response_status, handler
                ORDER BY handler, response_status NULLS LAST
            """)
            for row in cur.fetchall():
                print(f"  handler={row[1]:24} status={str(row[0]):5} n={row[2]}")

            print()
            print("=" * 60)
            print("QUEUE: top errored URLs, last 1h (status != 200-299 and != NULL)")
            print("=" * 60)
            cur.execute("""
                SELECT response_status, LEFT(url, 80) AS u, COUNT(*) AS n,
                       MAX(last_error) AS sample_err
                FROM chartmetric_request_queue
                WHERE completed_at > now() - interval '1 hour'
                  AND (response_status IS NULL OR response_status NOT BETWEEN 200 AND 299)
                GROUP BY response_status, LEFT(url, 80)
                ORDER BY n DESC
                LIMIT 15
            """)
            for row in cur.fetchall():
                print(f"  status={str(row[0]):5} n={row[2]:6} url={row[1]}")
                if row[3]:
                    print(f"    err={row[3][:200]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
