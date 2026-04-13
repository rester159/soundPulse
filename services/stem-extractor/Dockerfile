FROM python:3.11-slim

# Demucs needs ffmpeg + libsndfile. Install system deps first.
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsndfile1 \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install demucs + CPU-only torch (much smaller than CUDA build, ~400MB)
# We use torch 2.1 CPU wheel explicitly so pip doesn't grab the 1GB+
# CUDA default. demucs itself pulls numpy + julius + dora-search.
RUN pip install --no-cache-dir \
    --index-url https://download.pytorch.org/whl/cpu \
    --extra-index-url https://pypi.org/simple \
    torch==2.2.0 torchaudio==2.2.0

RUN pip install --no-cache-dir \
    demucs==4.0.1 \
    httpx==0.28.1 \
    python-dotenv==1.0.1

# Pre-download the default Demucs model weights at build time so the
# first job doesn't pay a ~500MB cold start. 'htdemucs' is the
# default hybrid-transformer model, best quality for 4-stem separation.
RUN python -c "from demucs.pretrained import get_model; get_model('htdemucs')"

COPY worker.py /app/

ENV NODE_ENV=production
CMD ["python", "-u", "/app/worker.py"]
