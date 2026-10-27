.PHONY: backend-sync backend-dev backend-check frontend-install frontend-dev frontend-check verify

backend-sync:
	cd backend && uv sync

backend-dev:
	cd backend && uv run uvicorn ai_finance_assistant.api.app:app --reload --host 127.0.0.1 --port 8000

backend-check:
	cd backend && uv run ruff format --check .
	cd backend && uv run ruff check .
	cd backend && uv run mypy
	cd backend && uv run pytest --cov=ai_finance_assistant --cov-report=term-missing

frontend-install:
	cd frontend && pnpm install

frontend-dev:
	cd frontend && pnpm dev

frontend-check:
	cd frontend && pnpm format:check
	cd frontend && pnpm lint
	cd frontend && pnpm typecheck
	cd frontend && pnpm test
	cd frontend && pnpm build

verify: backend-check frontend-check
