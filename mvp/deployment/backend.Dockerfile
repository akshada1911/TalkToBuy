# The backend: the session server (voice + tools) and the demo store (catalogue, cart, payment) in ONE
# container, behind a small nginx that routes /v1/* to the session server and everything else to the store.
# Build from mvp/:  docker build -f deployment/backend.Dockerfile -t talktobuy-backend .
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends nginx bash \
    && rm -rf /var/lib/apt/lists/* && pip install --no-cache-dir uv==0.12.24
WORKDIR /app
ENV UV_LINK_MODE=copy UV_PROJECT_ENVIRONMENT=/app/.venv TTB_NO_DOTENV=1 PYTHONUNBUFFERED=1 PORT=8080
COPY pyproject.toml uv.lock ./
COPY services/session-server/pyproject.toml services/session-server/pyproject.toml
COPY services/demo-store/pyproject.toml services/demo-store/pyproject.toml
RUN mkdir -p services/demo-store/src/demo_store services/session-server/src/session_server \
    && uv sync --frozen --no-dev --package session-server --package demo-store --no-install-workspace
COPY contracts contracts
COPY prompts prompts
COPY services/session-server services/session-server
COPY services/demo-store services/demo-store
RUN uv sync --frozen --no-dev --package session-server --package demo-store
COPY deployment/nginx-backend.conf /etc/nginx/nginx.conf
COPY deployment/start-backend.sh /start-backend.sh
RUN chmod +x /start-backend.sh
EXPOSE 8080
CMD ["/start-backend.sh"]
