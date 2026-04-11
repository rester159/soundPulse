"""Railway startup script — runs migrations, seeds data, then starts the API.

AUD-039: previously both subprocess.run() calls used check=False, which
silently ignored failures and let the API start with an outdated schema or
unseeded genres. Now we fail fast: a failed migration or failed seed aborts
startup with a non-zero exit code so Railway restarts the container instead
of running on broken state.
"""
import os
import subprocess
import sys


def main() -> None:
    print("Running database migrations...")
    try:
        subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        print(f"FATAL: alembic upgrade failed (exit {exc.returncode})", file=sys.stderr)
        sys.exit(exc.returncode or 1)

    print("Seeding genre taxonomy...")
    try:
        subprocess.run(
            [sys.executable, "scripts/seed_genres.py"],
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        print(f"FATAL: seed_genres failed (exit {exc.returncode})", file=sys.stderr)
        sys.exit(exc.returncode or 1)

    port = os.environ.get("PORT", "8000")
    print(f"Starting SoundPulse API on port {port}...")
    os.execvp("uvicorn", ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", port])


if __name__ == "__main__":
    main()
