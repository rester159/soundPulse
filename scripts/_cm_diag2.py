"""Narrower-window diagnostic: status breakdown for the last 5 min
only, so we can tell whether the fetcher is truly in live mode
after the env-var deploy."""
import os
import sys
import psycopg2


def normalize_dsn(dsn: str) -> str:
    if dsn.startswith("postgresql+asyncpg://"):
        dsn = "postgresql://" + dsn[len("postgresql+asyncpg://"):]
    return dsn.replace("?ssl=", "?sslmode=").replace("&ssl=", "&sslmode=")


def main() -> int:
    dsn = os.environ["DATABASE_URL"]
    with psycopg2.connect(normalize_dsn(dsn)) as conn:
        with conn.cursor() as cur:
            for window, label in [("5 minutes", "5min"), ("2 minutes", "2min")]:
                print(f"\n=== Last {label} ===")
                cur.execute(f"""
                    SELECT handler, response_status, COUNT(*) AS n
                    FROM chartmetric_request_queue
                    WHERE completed_at > now() - interval '{window}'
                    GROUP BY handler, response_status
                    ORDER BY handler, response_status NULLS LAST
                """)
                rows = cur.fetchall()
                if not rows:
                    print("  (no completions)")
                for row in rows:
                    print(f"  handler={row[0]:24} status={str(row[1]):5} n={row[2]}")

            print("\n=== Quota state ===")
            cur.execute("SELECT adaptive_multiplier, last_429_at, updated_at FROM chartmetric_quota_state WHERE id=1")
            row = cur.fetchone()
            if row:
                print(f"  adaptive_multiplier = {row[0]}")
                print(f"  last_429_at         = {row[1]}")
                print(f"  updated_at          = {row[2]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
