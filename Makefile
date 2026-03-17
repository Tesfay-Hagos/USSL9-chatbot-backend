# ULSS 9 Chatbot Backend — Developer Commands

install:
	@command -v uv >/dev/null 2>&1 || { echo "uv is not installed. Installing uv..."; curl -LsSf https://astral.sh/uv/0.8.13/install.sh | sh; source $$HOME/.local/bin/env; }
	uv sync

install-dev:
	uv sync --extra dev

# Run the FastAPI development server
dev:
	@echo "==============================================================================="
	@echo "| 🚀 ULSS 9 Scaligera – Backend (port 8000)                                  |"
	@echo "==============================================================================="
	uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Run production (no reload)
run:
	uv run uvicorn app.main:app --host 0.0.0.0 --port 8000

# Database migrations
db-init:
	uv run alembic upgrade head

db-migrate:
	@read -p "Migration message: " msg; \
	uv run alembic revision --autogenerate -m "$$msg"

db-upgrade:
	uv run alembic upgrade head

db-downgrade:
	uv run alembic downgrade -1

db-history:
	uv run alembic history --verbose

# Reset dashboard data (keeps only admin_users)
db-reset-dashboard:
	uv run python scripts/reset_dashboard_data.py

# Testing
test:
	uv run pytest tests/ -v

test-cov:
	uv run pytest tests/ -v --cov=app --cov-report=term-missing

# Code quality
lint:
	uv sync --extra dev
	uv run ruff check . --diff
	uv run ruff format . --check --diff

lint-fix:
	uv run ruff check . --fix
	uv run ruff format .

# Docker
docker-build:
	docker compose build

docker-up:
	docker compose up -d

docker-down:
	docker compose down

docker-logs:
	docker compose logs -f backend

# Clean up
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	rm -f data/ulss9.db

.PHONY: install install-dev dev run db-init db-migrate db-upgrade db-downgrade db-history db-reset-dashboard test test-cov lint lint-fix docker-build docker-up docker-down docker-logs clean
