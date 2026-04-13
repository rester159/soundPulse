FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libsndfile1 \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
RUN pip install --no-cache-dir -e ".[dev]" 2>/dev/null || pip install --no-cache-dir .

# NOTE: Playwright-based submission adapters (ASCAP, DistroKid, etc) run
# in a SEPARATE Railway service (services/portal-worker/) based on
# BlackTip, NOT in this API container. Do NOT add Chromium here — the
# portal flows never execute inside the Python API process.

# Cache bust BEFORE COPY . . so Docker invalidates the file copy layer.
RUN echo "cache-bust-2026-04-13-v4" > /dev/null
COPY . .

EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
