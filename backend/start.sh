#!/bin/sh
set -eu

case "${APP_PROCESS:-api}" in
  api)
    alembic upgrade head
    exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
    ;;
  worker)
    exec python -m app.modules.max_integration.worker
    ;;
  scheduler)
    exec python -m app.modules.matching.scheduler
    ;;
  *)
    echo "Unsupported APP_PROCESS: ${APP_PROCESS}" >&2
    exit 64
    ;;
esac
