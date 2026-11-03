#!/bin/bash
# launch.sh - start ShopSense (FastAPI backend + React frontend)
#
# Qdrant runs in embedded local mode (QDRANT_PATH in .env), so there is no
# database server to start. Build the data first, see README "Quick start".

set -e
cd "$(dirname "$0")"

echo "Starting backend on http://127.0.0.1:8000 ..."
uvicorn backend.main:app --port 8000 &
BACKEND_PID=$!

echo "Starting frontend on http://127.0.0.1:5173 ..."
(cd frontend && npm run dev) &
FRONTEND_PID=$!

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT TERM
echo ""
echo "Open http://127.0.0.1:5173 — Ctrl+C stops both."
wait
