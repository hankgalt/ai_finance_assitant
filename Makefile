QDRANT_URL ?= http://127.0.0.1:6333
DEPLOYMENT_ENVIRONMENT ?= staging

.PHONY: backend-sync backend-dev backend-check frontend-install frontend-dev frontend-check \
	qdrant-up qdrant-status qdrant-stop qdrant-check knowledge-finance knowledge-tax \
	knowledge-validate knowledge-check calculations-check providers-check assistant-check \
	model-check api-check product-ui-check inspector-check qualification-check release-check \
	verify m1-check m2-check m3-check m4-check m4-1-check \
	m5-check m6-check m7-check provider-live-check model-live-check observability-up observability-status \
	observability-stop response-cache-up response-cache-status response-cache-stop \
	response-cache-check response-cache-calibrate response-cache-benchmark m6-1-check m8-check \
	mcp-stdio m9-check managed-state-migrate managed-state-status managed-state-retention \
	managed-state-postgres-up managed-state-postgres-status managed-state-postgres-stop \
	managed-state-postgres-check delivery-check infrastructure-check container-build \
	mirror-merged-main-images set-deployment-image-variables knowledge-release-staging \
	rotate-qdrant-runtime-key-staging private-edge-up private-edge-down qualify-private-demo

backend-sync:
	cd backend && uv sync

backend-dev:
	cd backend && uv run uvicorn ai_finance_assistant.api.app:app --reload --host 127.0.0.1 --port 8000

backend-check:
	cd backend && uv run ruff format --check .
	cd backend && uv run ruff check .
	cd backend && uv run mypy
	cd backend && uv run pytest --cov=ai_finance_assistant --cov-report=term-missing

managed-state-migrate:
	cd backend && uv run python -m ai_finance_assistant.persistence.cli migrate

managed-state-status:
	cd backend && uv run python -m ai_finance_assistant.persistence.cli status

managed-state-retention:
	cd backend && uv run python -m ai_finance_assistant.persistence.cli retention

managed-state-postgres-up:
	docker compose --profile managed-state up -d postgres-managed-state

managed-state-postgres-status:
	docker compose --profile managed-state ps postgres-managed-state

managed-state-postgres-stop:
	docker compose --profile managed-state stop postgres-managed-state

managed-state-postgres-check:
	cd backend && AIFA_TEST_POSTGRES_DSN=postgresql://aifa_qualification@127.0.0.1:55432/aifa_qualification uv run pytest -q -m postgres tests/test_managed_persistence.py

delivery-check:
	cd backend && uv run pytest -q tests/test_delivery_workflows.py tests/test_release_bundle.py

infrastructure-check:
	terraform fmt -check -recursive infrastructure/terraform
	cd infrastructure/terraform/bootstrap && terraform init -backend=false && terraform validate
	cd infrastructure/terraform/shared && terraform init -backend=false && terraform validate
	cd infrastructure/terraform/environments/staging && terraform init -backend=false && terraform validate
	cd infrastructure/terraform/environments/staging-workloads && terraform init -backend=false && terraform validate
	cd infrastructure/terraform/environments/staging-edge && terraform init -backend=false && terraform validate
	cd backend && uv run pytest -q tests/test_staging_infrastructure.py tests/test_private_edge.py tests/test_delivery_workflows.py

container-build:
	docker build --file infrastructure/container/backend/Dockerfile --tag ai-finance-assistant-backend:local .
	docker build --file infrastructure/container/frontend/Dockerfile --tag ai-finance-assistant-frontend:local .

mirror-merged-main-images:
	./infrastructure/terraform/scripts/mirror-merged-main-images.sh

set-deployment-image-variables:
	./infrastructure/terraform/scripts/set-deployment-image-variables.sh "$(DEPLOYMENT_ENVIRONMENT)"

knowledge-release-staging:
	./infrastructure/terraform/scripts/release-shared-knowledge.sh

rotate-qdrant-runtime-key-staging:
	./infrastructure/terraform/scripts/rotate-qdrant-runtime-key.sh

private-edge-up:
	./infrastructure/terraform/scripts/private-edge-up.sh

private-edge-down:
	./infrastructure/terraform/scripts/private-edge-down.sh

qualify-private-demo:
	./infrastructure/terraform/scripts/qualify-private-demo.sh

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
	cd backend && uv run python -m ai_finance_assistant.knowledge.cli --qdrant-url $(QDRANT_URL) run --kb finance_education --qrels data/knowledge/finance-education/retrieval-cases.v1.json --activate

knowledge-tax:
	cd backend && uv run python -m ai_finance_assistant.knowledge.cli --qdrant-url $(QDRANT_URL) run --kb tax_education --qrels data/knowledge/tax-education/retrieval-cases.v1.json --activate

knowledge-validate:
	cd backend && uv run python -m ai_finance_assistant.knowledge.cli --qdrant-url $(QDRANT_URL) validate --kb finance_education
	cd backend && uv run python -m ai_finance_assistant.knowledge.cli --qdrant-url $(QDRANT_URL) validate --kb tax_education

verify: backend-check frontend-check

knowledge-check: verify qdrant-check knowledge-validate

calculations-check:
	cd backend && uv run pytest -q tests/test_portfolio_import.py tests/test_portfolio_analysis.py tests/test_goal_projection.py tests/test_cash_flow_contracts.py

providers-check:
	cd backend && uv run ruff format --check src tests
	cd backend && uv run ruff check src tests
	cd backend && uv run mypy
	cd backend && uv run pytest -q tests/test_provider_adapters.py

assistant-check:
	cd backend && uv run ruff format --check src tests
	cd backend && uv run ruff check src tests
	cd backend && uv run mypy
	cd backend && uv run pytest -q tests/test_routing.py tests/test_agents.py tests/test_workflow.py tests/test_workflow_application.py tests/test_observability.py

model-check:
	cd backend && uv run ruff format --check src tests
	cd backend && uv run ruff check src tests
	cd backend && uv run mypy
	cd backend && uv run pytest -q tests/test_openai_model_adapter.py tests/test_model_factory.py tests/test_agents.py tests/test_workflow.py tests/test_workflow_application.py tests/test_observability.py

api-check:
	cd backend && uv run ruff format --check src tests
	cd backend && uv run ruff check src tests
	cd backend && uv run mypy
	cd backend && uv run pytest -q tests/test_http_api.py tests/test_persistence.py tests/test_durable_provider_cache.py tests/test_api_observability.py tests/test_public_http_contract.py tests/test_health.py

product-ui-check: frontend-check
	cd backend && uv run ruff format --check src tests
	cd backend && uv run ruff check src tests
	cd backend && uv run mypy
	cd backend && uv run pytest -q tests/test_browser_telemetry.py tests/test_frontend_contract.py tests/test_http_api.py tests/test_public_http_contract.py
	cd frontend && pnpm test:e2e

inspector-check: frontend-check
	cd backend && uv run ruff format --check src tests
	cd backend && uv run ruff check src tests
	cd backend && uv run mypy
	cd backend && uv run pytest -q tests/test_inspector_contract.py tests/test_http_api.py tests/test_persistence.py tests/test_api_observability.py tests/test_contracts.py tests/test_redaction.py
	cd frontend && pnpm exec playwright test e2e/execution-inspector.spec.ts

response-cache-up:
	docker compose up -d redis-response-cache

response-cache-status:
	docker compose ps redis-response-cache

response-cache-stop:
	docker compose stop redis-response-cache

response-cache-check:
	cd backend && AIFA_TEST_REDIS_URL=redis://127.0.0.1:6379/0 uv run pytest -q -m redis tests/test_response_cache_redis.py

response-cache-calibrate:
	cd backend && uv run python -m ai_finance_assistant.response_cache.evaluation --cases data/response-cache/semantic-calibration.v1.json --minimum-similarity 0.92

response-cache-benchmark:
	cd backend && AIFA_ENV_FILE=.test.env uv run python -m ai_finance_assistant.response_cache.benchmark --samples 20 --model-delay-ms 10

qualification-check:
	cd backend && .venv/bin/python -m ai_finance_assistant.evaluation.runner --manifest data/qualification/release-cases.v1.json --repo-root .. --output artifacts/release/qualification-report.v1.json --profile full

mcp-stdio:
	cd backend && uv run python -m ai_finance_assistant.mcp_adapter

release-check:
	cd frontend && pnpm test:coverage
	$(MAKE) qualification-check
	cd backend && AIFA_REQUIRE_QUALIFICATION_PASS=true uv run pytest -q tests/test_mcp_adapter.py tests/test_release_bundle.py
	docker compose config --quiet

observability-up:
	docker compose --profile observability up -d otel-collector

observability-status:
	docker compose --profile observability ps otel-collector

observability-stop:
	docker compose --profile observability stop otel-collector

provider-live-check:
	cd backend && AIFA_TEST_ENV_FILE=.env AIFA_RUN_LIVE_PROVIDER_TESTS=true AIFA_PROVIDER_MODE=live uv run pytest -q -m live_provider tests/test_live_provider_adapters.py

model-live-check:
	cd backend && AIFA_TEST_ENV_FILE=.env AIFA_RUN_LIVE_MODEL_TESTS=true AIFA_MODEL_MODE=openai_live uv run pytest -q -m live_model tests/test_live_model_adapter.py

m1-check: knowledge-check
m2-check: calculations-check
m3-check: providers-check
m4-check: assistant-check
m4-1-check: model-check
m5-check: api-check
m6-check: product-ui-check
m6-1-check:
	cd backend && uv run ruff format --check src tests
	cd backend && uv run ruff check src tests
	cd backend && uv run mypy
	cd backend && uv run pytest -q tests/test_response_cache.py tests/test_response_cache_workflow.py tests/test_response_cache_api.py tests/test_response_cache_evaluation.py tests/test_response_cache_benchmark.py tests/test_health.py tests/test_http_api.py
m7-check: inspector-check
m8-check: qualification-check
m9-check: release-check
