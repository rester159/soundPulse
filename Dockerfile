FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libsndfile1 \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
RUN pip install --no-cache-dir -e ".[dev]" 2>/dev/null || pip install --no-cache-dir .

# Install Chromium for Playwright-based submission adapters (DistroKid,
# TuneCore, CD Baby, Amuse, UnitedMasters, BMI, SoundExchange, Fonzworth
# ASCAP, sync marketplaces, playlist pitching, TikTok upload).
RUN python -m playwright install --with-deps chromium || echo "playwright install skipped — dep will be added in follow-up"

# Cache bust BEFORE COPY . . so Docker invalidates the file copy layer.
# Change this value to force a fresh copy of all source files.
RUN echo "cache-bust-2026-04-13-v3" > /dev/null
COPY . .

EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
