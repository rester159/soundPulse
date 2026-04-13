FROM python:3.11-slim

# Demucs needs ffmpeg + libsndfile. Install system deps first.
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsndfile1 \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install numpy FIRST from pypi so torch's from_numpy() has a working
# numpy C-API target. Installing numpy after torch (or letting demucs
# pull it transitively) leaves torch 2.2's numpy binding in a broken
# state and every call to torch.from_numpy() raises
# 'RuntimeError: Numpy is not available'. This bit the first build.
RUN pip install --no-cache-dir "numpy>=1.26,<2.0"

# Install CPU-only torch + torchaudio (~400MB vs 1GB+ CUDA default).
# The cpu index only has torch — numpy is already installed above
# from pypi.
RUN pip install --no-cache-dir \
    --index-url https://download.pytorch.org/whl/cpu \
    torch==2.2.0 torchaudio==2.2.0

# Demucs + the worker's HTTP + env loader deps
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
