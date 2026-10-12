# TalkToBuy MVP task runner (macOS/Linux). Windows: scripts/tasks.ps1 exposes the same targets.
UV ?= uv

.PHONY: install dev test test-safety gen-types check-generated lint

install:
	$(UV) sync --all-packages
	npm install

dev:
	@echo "Starting store :3000, session server :8080, shop :5173 (Ctrl+C stops all)"
	$(UV) run --package demo-store uvicorn demo_store.main:app --port 3000 --reload & \
	$(UV) run --package session-server uvicorn session_server.main:app --port 8080 --reload & \
	npm run -w apps/shop dev; kill 0

test:
	$(UV) run pytest -m "not safety and not live"
	npm test

test-safety:
	$(UV) run pytest -m safety

gen-types:
	$(UV) run python scripts/gen_types.py

check-generated:
	$(UV) run python scripts/gen_types.py --check

lint:
	$(UV) run ruff check services scripts
	$(UV) run ruff format --check services scripts
