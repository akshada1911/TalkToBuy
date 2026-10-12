# Build from mvp/:  docker build -f infra/session-server.Dockerfile -t session-server .
FROM python:3.12-slim
RUN pip install --no-cache-dir uv==0.12.24
WORKDIR /app
ENV UV_LINK_MODE=copy UV_PROJECT_ENVIRONMENT=/app/.venv TTB_NO_DOTENV=1 PORT=8080
COPY pyproject.toml uv.lock ./
COPY services/session-server/pyproject.toml services/session-server/pyproject.toml
COPY services/demo-store/pyproject.toml services/demo-store/pyproject.toml
RUN mkdir -p services/demo-store/src/demo_store services/session-server/src/session_server \
    && uv sync --frozen --no-dev --package session-server --no-install-workspace
COPY contracts contracts
COPY prompts prompts
COPY services/session-server services/session-server
RUN uv sync --frozen --no-dev --package session-server
CMD ["sh", "-c", "uv run --no-sync --package session-server uvicorn session_server.main:app --host 0.0.0.0 --port ${PORT}"]
