#!/bin/bash
set -e

echo "[tunebat-crawler] Starting Xvfb on :99..."
Xvfb :99 -screen 0 1440x900x24 -ac &
sleep 1

echo "[tunebat-crawler] Xvfb ready, launching crawler..."
exec node /app/crawler.mjs
