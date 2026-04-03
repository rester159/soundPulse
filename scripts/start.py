"""Railway startup script — runs migrations, seeds data, then starts the API."""
import os
import subprocess
import sys

def main():
    print("Running database migrations...")
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], check=False)

    print("Seeding genre taxonomy...")
    subprocess.run([sys.executable, "scripts/seed_genres.py"], check=False)

    port = os.environ.get("PORT", "8000")
    print(f"Starting SoundPulse API on port {port}...")
    os.execvp("uvicorn", ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", port])

if __name__ == "__main__":
    main()
