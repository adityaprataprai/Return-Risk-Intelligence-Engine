#!/usr/bin/env bash
# ==============================================================================
# Razorpay Return-Risk Intelligence Engine - Local Multi-Service Runner
# ==============================================================================
# Launches all local microservices simultaneously:
#   1. Scoring API (Port 8000)
#   2. Dashboard BFF (Port 8001)
#   3. SHAP Explanation Worker (Background Daemon)
#   4. Next.js Dashboard Frontend (Port 3000)
# ==============================================================================

set -e

PIDS=()

cleanup() {
    echo ""
    echo "===================================================================="
    echo "Shutting down all services..."
    echo "===================================================================="
    for pid in "${PIDS[@]}"; do
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null || true
        fi
    done
    wait 2>/dev/null || true
    echo "All services stopped."
    exit 0
}

trap cleanup SIGINT SIGTERM EXIT

echo "===================================================================="
echo "Starting Razorpay Return-Risk Intelligence Engine"
echo "===================================================================="

# Check if redis-server is available
if command -v redis-server >/dev/null 2>&1; then
    echo "Checking Redis status..."
    if ! redis-cli ping >/dev/null 2>&1; then
        echo "Starting local Redis server..."
        redis-server --daemonize yes
    else
        echo "Local Redis is already running."
    fi
else
    echo "Notice: redis-server not found in PATH; services will use in-memory fallbacks."
fi

# 1. Scoring API
echo "Starting Scoring API on http://0.0.0.0:8000 (Metrics: /metrics)..."
python -m uvicorn src.app:app --host 0.0.0.0 --port 8000 &
PIDS+=($!)

# 2. Dashboard BFF
echo "Starting Dashboard BFF on http://0.0.0.0:8001 (Metrics: /metrics)..."
python -m uvicorn src.dashboard.api:app --host 0.0.0.0 --port 8001 &
PIDS+=($!)

# 3. SHAP Worker
echo "Starting TreeSHAP Worker daemon..."
python scripts/run_shap_worker.py --poll-interval 0.5 &
PIDS+=($!)

# 4. Next.js Frontend
if [ -d "frontend" ]; then
    echo "Starting Next.js Frontend on http://localhost:3000..."
    (cd frontend && npm run dev) &
    PIDS+=($!)
fi

echo "===================================================================="
echo "All services are up and running!"
echo "  - Scoring API:    http://localhost:8000 (Docs: /docs, Metrics: /metrics)"
echo "  - Dashboard BFF:  http://localhost:8001 (Docs: /docs, Metrics: /metrics)"
echo "  - Web Dashboard:  http://localhost:3000"
echo "Press Ctrl+C to terminate all services."
echo "===================================================================="

wait
