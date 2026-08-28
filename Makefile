.PHONY: help install dev test lint format clean

help:
	@echo "FBA Sourcer - Make Targets"
	@echo ""
	@echo "Setup:"
	@echo "  make install       Install dependencies with UV"
	@echo ""
	@echo "Development:"
	@echo "  make dev           Run FastAPI dev server (localhost:8000)"
	@echo ""
	@echo "Quality:"
	@echo "  make test          Run pytest with coverage"
	@echo "  make lint          Check code with ruff"
	@echo "  make format        Format code with ruff"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean         Remove __pycache__, .pytest_cache, etc"
	@echo ""

install:
	uv sync

dev:
	uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

test:
	uv run pytest tests/ -v --cov=app --cov-report=term-missing

lint:
	uv run ruff check app/ tests/

format:
	uv run ruff format app/ tests/

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name *.egg-info -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name ".coverage" -delete 2>/dev/null || true
	@echo "Cleaned cache and build files"