#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
# Automated checks must not depend on the OCR provider selected in backend/.env.
export OCR_PROVIDER=mock
(cd backend && uv run ruff check app migrations && uv run pytest -q && uv run python -m app.evaluation.run)
(cd frontend && npm run typecheck && npm test && npm run build)
