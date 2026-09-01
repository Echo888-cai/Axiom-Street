#!/bin/sh
set -eu

# Only the API should migrate. API and worker share this image; running
# `alembic upgrade head` in both entrypoints races on alembic_version.
if [ "${1:-}" = "uvicorn" ]; then
  alembic upgrade head
fi
exec "$@"
