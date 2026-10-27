QDRANT_URL ?= http://127.0.0.1:6333

.PHONY: backend-sync backend-dev backend-check frontend-install frontend-dev frontend-check \
	qdrant-up qdrant-status qdrant-stop qdrant-check knowledge-finance knowledge-tax \
	knowledge-validate verify m1-check

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

qdrant-up:
	docker compose up -d qdrant

qdrant-status:
	docker compose ps qdrant

qdrant-stop:
	docker compose stop qdrant

qdrant-check:
	cd backend && AIFA_TEST_QDRANT_URL=$(QDRANT_URL) uv run pytest -q tests/test_qdrant_integration.py

knowledge-finance:
	cd backend && uv run python -m ai_finance_assistant.knowledge.cli --qdrant-url $(QDRANT_URL) run --kb finance_education --qrels data/knowledge/qrels.finance.v1.json --activate

knowledge-tax:
	cd backend && uv run python -m ai_finance_assistant.knowledge.cli --qdrant-url $(QDRANT_URL) run --kb tax_education --qrels data/knowledge/qrels.tax.v1.json --activate

knowledge-validate:
	cd backend && uv run python -m ai_finance_assistant.knowledge.cli --qdrant-url $(QDRANT_URL) validate --kb finance_education
	cd backend && uv run python -m ai_finance_assistant.knowledge.cli --qdrant-url $(QDRANT_URL) validate --kb tax_education

verify: backend-check frontend-check

m1-check: verify qdrant-check knowledge-validate
