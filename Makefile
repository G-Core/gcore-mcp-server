.PHONY: run lint format typecheck test install dev-install clean help setup install-local-deps bump-major bump-minor bump-patch

help:
	@echo "Available commands:"
	@echo "  make setup        - Create .env file from sample if not exists"
	@echo "  make run          - Run the server"
	@echo "  make lint         - Lint the code"
	@echo "  make format       - Format the code"
	@echo "  make typecheck    - Run type checking"
	@echo "  make test         - Run tests"
	@echo "  make install      - Install dependencies"
	@echo "  make dev-install  - Install development dependencies"
	@echo "  make install-local-deps - Install local cloud-api package"
	@echo "  make clean        - Clean generated files"
	@echo "  make bump-major   - Bump major version (X.0.0)"
	@echo "  make bump-minor   - Bump minor version (0.X.0)"
	@echo "  make bump-patch   - Bump patch version (0.0.X)"

setup:
	@if [ ! -f .env ]; then \
		echo "Creating .env file from .env.sample"; \
		cp .env.sample .env; \
		echo "Please edit .env with your actual credentials"; \
	else \
		echo ".env file already exists"; \
	fi

run: setup install-local-deps
	set -o allexport; source .env; set +o allexport && PYTHONPATH=$(PWD):$(PWD)/cloud-api .venv/bin/uvicorn gcore_mcp_server.server:app --reload

lint:
	uv run ruff check .

format:
	uv run ruff format .

typecheck:
	uv run pyright

test: setup
	set -o allexport; source .env; set +o allexport && uv run pytest

install:
	uv add -e .

dev-install:
	uv add -e ".[dev]"

install-local-deps:
	cd cloud-api && uv pip install -e . && cd ..
	uv pip install -e .

clean:
	rm -rf __pycache__
	rm -rf .pytest_cache
	rm -rf .ruff_cache
	rm -rf .pyright
	find . -name "*.pyc" -delete 

# Version bumping commands
bump-major:
	@echo "Bumping major version..."
	@VERSION=$$(grep -m 1 "version = " pyproject.toml | sed -E 's/version = "([0-9]+)\.([0-9]+)\.([0-9]+)"/\1.\2.\3/'); \
	MAJOR=$$(echo $$VERSION | cut -d. -f1); \
	NEW_VERSION=$$((MAJOR+1)).0.0; \
	sed -i.bak "s/version = \"$$VERSION\"/version = \"$$NEW_VERSION\"/" pyproject.toml && rm pyproject.toml.bak; \
	echo "Version bumped to $$NEW_VERSION"

bump-minor:
	@echo "Bumping minor version..."
	@VERSION=$$(grep -m 1 "version = " pyproject.toml | sed -E 's/version = "([0-9]+)\.([0-9]+)\.([0-9]+)"/\1.\2.\3/'); \
	MAJOR=$$(echo $$VERSION | cut -d. -f1); \
	MINOR=$$(echo $$VERSION | cut -d. -f2); \
	NEW_VERSION=$$MAJOR.$$((MINOR+1)).0; \
	sed -i.bak "s/version = \"$$VERSION\"/version = \"$$NEW_VERSION\"/" pyproject.toml && rm pyproject.toml.bak; \
	echo "Version bumped to $$NEW_VERSION"

bump-patch:
	@echo "Bumping patch version..."
	@VERSION=$$(grep -m 1 "version = " pyproject.toml | sed -E 's/version = "([0-9]+)\.([0-9]+)\.([0-9]+)"/\1.\2.\3/'); \
	MAJOR=$$(echo $$VERSION | cut -d. -f1); \
	MINOR=$$(echo $$VERSION | cut -d. -f2); \
	PATCH=$$(echo $$VERSION | cut -d. -f3); \
	NEW_VERSION=$$MAJOR.$$MINOR.$$((PATCH+1)); \
	sed -i.bak "s/version = \"$$VERSION\"/version = \"$$NEW_VERSION\"/" pyproject.toml && rm pyproject.toml.bak; \
	echo "Version bumped to $$NEW_VERSION" 