#!/bin/bash
# launch.sh - Launch ShopSense (FastAPI backend + React frontend)

echo "================================"
echo "  ShopSense"
echo "================================"
echo ""

# Check Qdrant
echo "Checking Qdrant..."
if curl -s http://127.0.0.1:6333 > /dev/null; then
    echo "✓ Qdrant running at http://127.0.0.1:6333"
else
    echo "✗ Qdrant not found. Start it with:"
    echo "    docker run -p 6333:6333 qdrant/qdrant"
    exit 1
fi

echo ""

# Start backend
echo "Starting backend (port 8000)..."
cd "$(dirname "$0")"
uvicorn backend.main:app --reload --port 8000 &
BACKEND_PID=$!

# Wait for backend to be ready
for i in {1..10}; do
    if curl -s http://127.0.0.1:8000/health > /dev/null 2>&1; then
        break
    fi
    sleep 1
done
echo "✓ Backend running at http://127.0.0.1:8000"

echo ""

# Start frontend
echo "Starting frontend (port 5173)..."
cd frontend && npm run dev &
FRONTEND_PID=$!

echo ""
echo "================================"
echo "  Backend:  http://127.0.0.1:8000"
echo "  Frontend: http://127.0.0.1:5173"
echo "================================"
echo ""
echo "Press Ctrl+C to stop all services"

# Cleanup on exit
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT TERM
wait
