#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
PROJECT_ROOT="$PWD"
if [[ ! -d backend/.venv ]]; then (cd backend && uv sync --python 3.12); fi
if [[ ! -d frontend/node_modules ]]; then (cd frontend && npm ci); fi
(cd backend && uv run alembic upgrade head)
(cd backend && uv run uvicorn app.main:app --host 127.0.0.1 --port 8000) &
BACKEND_PID=$!
(cd frontend && npm run dev) &
FRONTEND_PID=$!
trap 'kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true' EXIT INT TERM
printf 'GradeKade: http://localhost:3000\nAPI docs: http://127.0.0.1:8000/docs\n'
wait
