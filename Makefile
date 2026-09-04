.PHONY: install test run-api lint format clean help dev-setup

help:
	@echo "Available commands:"
	@echo "  make install    - Install project dependencies"
	@echo "  make dev-setup  - Verify local environment setup"
	@echo "  make test       - Run test suite"
	@echo "  make run-api    - Run FastAPI development server"
	@echo "  make lint       - Run linter checks"
	@echo "  make clean      - Clean cache and temp files"

install:
	pip install -e ".[dev]"

dev-setup:
	python scripts/dev_setup.py

test:
	pytest tests/ -v

run-api:
	uvicorn src.app:app --host 0.0.0.0 --port 8000 --reload

lint:
	ruff check . || true

format:
	black src/ tests/ scripts/ || true

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
