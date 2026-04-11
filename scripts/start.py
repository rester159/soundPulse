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
    # L006: invoke as a MODULE (`-m scripts.seed_genres`), NOT as a bare
    # script path. Running `python scripts/seed_genres.py` puts `scripts/`
    # on sys.path[0] instead of the project root, breaking the
    # `from shared.genre_taxonomy import ...` import inside. This had been
    # silently failing on every deploy — AUD-039 (`check=True`) made it
    # loud and broke Railway deploys for 4 commits straight.
    # seed_genres.py's own docstring says `Usage: python -m scripts.seed_genres`.
    try:
        subprocess.run(
            [sys.executable, "-m", "scripts.seed_genres"],
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
