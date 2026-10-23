#!/usr/bin/env bash
# Launch the Retake backend (FastAPI on :8000) and frontend (Vite on :5173).
# Usage: ./start.sh [--reload]
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
PY="$ROOT/backend/.venv/bin/python"

[ -x "$PY" ] || { echo "Backend venv not found. See README: Setup -> Backend." >&2; exit 1; }
command -v npm >/dev/null || { echo "npm not found. Install Node.js 20+ (see README)." >&2; exit 1; }
[ -f "$ROOT/.env" ] || { cp "$ROOT/.env.example" "$ROOT/.env"; echo "Created .env from .env.example"; }
[ -d "$ROOT/frontend/node_modules" ] || (cd "$ROOT/frontend" && npm install)

RELOAD=""
[ "${1:-}" = "--reload" ] && RELOAD="--reload"

(cd "$ROOT/backend" && exec "$PY" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --timeout-graceful-shutdown 3 $RELOAD) &
BACKEND_PID=$!
trap 'kill $BACKEND_PID 2>/dev/null || true' EXIT INT TERM

echo "Backend PID $BACKEND_PID. Open http://localhost:5173"
cd "$ROOT/frontend" && npm run dev
