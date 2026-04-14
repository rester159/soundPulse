FROM python:3.11-slim

# REBUILD MARKER: bump when you need to force Railway to re-evaluate
# the cached Dockerfile layers. Increment this integer.
#   rev: 2 — pin librosa 0.10.2.post1 + scipy<1.14 + mdx_extra_q default
ARG REBUILD_REV=2

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

# Demucs + the worker's HTTP + env loader deps.
# We deliberately do NOT install diffq / use mdx_extra_q — the
# quantized variant needs gcc at build time (for the bitpack C
# extension) which bloats this image, and the plain htdemucs model
# works fine within the 1800s Demucs timeout set in worker.py.
RUN pip install --no-cache-dir \
    demucs==4.0.1 \
    httpx==0.28.1 \
    python-dotenv==1.0.1

# librosa for the tempo-lock pre-pass (BPM detection), the
# entry-point pre-pass (pyin pitch verification, agglomerative
# segmentation, spectral flatness), and the instrumental analysis
# cache (key detection, duration). Pulls scipy + numba + soundfile;
# ~200 MB install but bulletproof for MIR tasks.
#
# PIN: 0.10.2.post1 is the first release that handles scipy>=1.13.
# The old 0.10.1 broke at runtime with
#   "module 'scipy.signal' has no attribute 'hann'"
# because scipy 1.13 removed the deprecated top-level hann import.
# Belt-and-braces: also pin scipy to a known-good range.
RUN pip install --no-cache-dir "scipy>=1.11,<1.14" "librosa==0.10.2.post1"

# silero-vad for the Suno-side vocal entry detection. ~2 MB PyTorch
# JIT model bundled with the wheel (no torch.hub fetch at runtime),
# rejects Demucs drum/bass bleed that naive RMS threshold picks up.
# PyTorch is already installed above — this is pure Python glue.
RUN pip install --no-cache-dir silero-vad==5.1

# Pre-download the default Demucs model weights at build time so the
# first job doesn't pay a ~500MB cold start. htdemucs is the
# hybrid-transformer model, best quality for 4-stem separation.
# On Railway's shared vCPU expect ~5-15 min per 3min song; the
# worker's DEMUCS_TIMEOUT_SEC=1800 default covers this.
RUN python -c "from demucs.pretrained import get_model; get_model('htdemucs')"

COPY worker.py /app/

ENV NODE_ENV=production
CMD ["python", "-u", "/app/worker.py"]
