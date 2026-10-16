#!/bin/bash
# Starts the three processes of the backend container. If any one stops, the container stops, so Cloud Run
# restarts it instead of leaving a half-working service.
cd /app

/app/.venv/bin/uvicorn demo_store.main:app --host 127.0.0.1 --port 3000 &
/app/.venv/bin/uvicorn session_server.main:app --host 127.0.0.1 --port 8081 &
nginx -g 'daemon off;' &

wait -n
echo "a backend process exited; stopping the container" >&2
exit 1
