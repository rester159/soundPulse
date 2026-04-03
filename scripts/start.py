"""Railway startup script — runs migrations, seeds data, starts API + Celery."""
import os
import subprocess
import sys

def main():
    print("Running database migrations...")
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], check=False)

    print("Seeding genre taxonomy...")
    subprocess.run([sys.executable, "scripts/seed_genres.py"], check=False)

    # Start Celery worker in background (handles scraper tasks + training)
    print("Starting Celery worker...")
    worker = subprocess.Popen(
        ["celery", "-A", "scrapers.celery_app", "worker",
         "--loglevel=info", "--concurrency=2"],
        stdout=sys.stdout, stderr=sys.stderr,
    )

    # Start Celery beat in background (cron scheduler)
    print("Starting Celery beat...")
    beat = subprocess.Popen(
        ["celery", "-A", "scrapers.celery_app", "beat",
         "--loglevel=info"],
        stdout=sys.stdout, stderr=sys.stderr,
    )

    port = os.environ.get("PORT", "8000")
    print(f"Starting SoundPulse API on port {port}...")
    print(f"Worker PID: {worker.pid}, Beat PID: {beat.pid}")

    # Start uvicorn as the main process (Railway monitors this)
    os.execvp("uvicorn", ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", port])

if __name__ == "__main__":
    main()
