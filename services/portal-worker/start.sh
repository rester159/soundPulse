#!/bin/bash
set -e

echo "[portal-worker] Starting Xvfb on :99..."
Xvfb :99 -screen 0 1440x900x24 -ac &
sleep 1

echo "[portal-worker] Xvfb ready, launching worker..."
exec node /app/worker.mjs
