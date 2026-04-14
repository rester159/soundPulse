"""One-shot: insert a new pending song_stem_jobs row for a given song,
reusing the most recent job's source fields. For retrying a failed
stem extraction without blocking on a new API endpoint deploy.

Usage (requires prod DB access via `railway run`):
    railway run --service soundPulse python scripts/_retry_stem_adhoc.py <song_id> [full|remix_only]

Prints the new job_id on success.

This is the kind of ad-hoc helper L010 warns about: it's fine for a
one-shot but should not be memorized as The Way To Retry. The
durable path is an admin endpoint (follow-up commit).
"""
import os
import sys
import uuid

import psycopg2


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: _retry_stem_adhoc.py <song_id> [full|remix_only]", file=sys.stderr)
        return 2
    try:
        song_id = uuid.UUID(sys.argv[1])
    except ValueError:
        print(f"invalid uuid: {sys.argv[1]!r}", file=sys.stderr)
        return 2
    job_type = sys.argv[2] if len(sys.argv) >= 3 else "full"
    if job_type not in ("full", "remix_only"):
        print(f"invalid job_type: {job_type!r}", file=sys.stderr)
        return 2

    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        print("DATABASE_URL not set (use `railway run`)", file=sys.stderr)
        return 2
    if dsn.startswith("postgresql+asyncpg://"):
        dsn = "postgresql://" + dsn[len("postgresql+asyncpg://"):]
    # Neon's connection strings use asyncpg-style `ssl=require`,
    # psycopg2 wants `sslmode=require`. Normalize so the same DSN
    # works for both drivers.
    dsn = dsn.replace("?ssl=", "?sslmode=").replace("&ssl=", "&sslmode=")

    with psycopg2.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, music_generation_call_id, source_instrumental_id,
                       source_audio_url, status, job_type, created_at
                FROM song_stem_jobs
                WHERE song_id = %s
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (str(song_id),),
            )
            prev = cur.fetchone()
            if prev is None:
                print(f"no existing stem jobs for song {song_id}", file=sys.stderr)
                return 3
            (prev_id, cid, iid, src_url, status, prev_job_type, created_at) = prev
            print(f"previous job id={prev_id} status={status} type={prev_job_type} created={created_at}")
            print(f"  music_generation_call_id={cid}")
            print(f"  source_instrumental_id={iid}")
            print(f"  source_audio_url={src_url}")

            cur.execute(
                """
                INSERT INTO song_stem_jobs
                    (song_id, music_generation_call_id, source_instrumental_id,
                     source_audio_url, status, job_type)
                VALUES (%s, %s, %s, %s, 'pending', %s)
                RETURNING id, created_at
                """,
                (str(song_id), cid, iid, src_url, job_type),
            )
            new_id, new_created = cur.fetchone()
            conn.commit()
            print(f"new job id={new_id} created={new_created} type={job_type}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
