.PHONY: install dev-backend dev-frontend lint format typecheck test check docker-up docker-down clean

install:
	uv sync --extra dev
	cd frontend && npm install
	uv run pre-commit install

dev-backend:
	uv run uvicorn app.main:app --reload

dev-frontend:
	cd frontend && npm run dev

lint:
	uv run ruff check .

format:
	uv run ruff format .

typecheck:
	uv run mypy app

test:
	uv run pytest

check: lint typecheck test

docker-up:
	docker compose up --build

docker-down:
	docker compose down

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	rm -rf .pytest_cache .mypy_cache .ruff_cache
