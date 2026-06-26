UV ?= uv

.PHONY: help install setup run web lint format types test check hooks release clean

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'

install: ## Install deps + wire git hooks (one command)
	$(UV) sync
	@if [ -d .git ]; then \
		$(UV) run pre-commit install --install-hooks --hook-type pre-commit --hook-type commit-msg; \
	fi
	@test -f .env || cp .env.example .env
	@echo "Installed. Next: make setup"

setup: ## Run the interactive setup wizard
	$(UV) run mika setup

run: ## Run the Discord bot
	$(UV) run mika run

web: ## Run the localhost settings & overview page
	$(UV) run mika web

lint: ## ruff lint + format check
	$(UV) run ruff check .
	$(UV) run ruff format --check .

format: ## Auto-format and auto-fix
	$(UV) run ruff format .
	$(UV) run ruff check --fix .

types: ## Type-check with mypy
	$(UV) run mypy src

test: ## Run the test suite
	$(UV) run pytest

check: lint types test ## Run all gates (pre-commit equivalent)

hooks: ## Run all pre-commit hooks on every file
	$(UV) run pre-commit run --all-files

clean: ## Remove caches
	rm -rf .ruff_cache .mypy_cache .pytest_cache
	find . -type d -name __pycache__ -not -path './mikabot(JS)/*' -prune -exec rm -rf {} +

release: ## Build the customer release zip (excludes dev/secrets/userbot)
	$(UV) run python scripts/package.py
