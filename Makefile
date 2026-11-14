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
	rotate-qdrant-runtime-key-staging private-edge-up private-edge-down qualify-private-demo \
	live-providers-staging-up live-providers-staging-down

backend-sync: ## Install or synchronize pinned backend dependencies with uv.
	cd backend && uv sync

backend-dev: ## Run the loopback FastAPI development server with automatic reload.
	cd backend && uv run uvicorn ai_finance_assistant.api.app:app --reload --host 127.0.0.1 --port 8000

backend-check: ## Run backend formatting, lint, type, test, and coverage gates.
	cd backend && uv run ruff format --check .
	cd backend && uv run ruff check .
	cd backend && uv run mypy
	cd backend && uv run pytest --cov=ai_finance_assistant --cov-report=term-missing

managed-state-migrate: ## Apply the configured application and checkpoint database migrations.
	cd backend && uv run python -m ai_finance_assistant.persistence.cli migrate

managed-state-status: ## Report configured managed-state schema compatibility without exposing secrets.
	cd backend && uv run python -m ai_finance_assistant.persistence.cli status

managed-state-retention: ## Apply the configured Session, RunEvent, Portfolio, and cache retention policy.
	cd backend && uv run python -m ai_finance_assistant.persistence.cli retention

managed-state-postgres-up: ## Start the disposable loopback PostgreSQL qualification fixture.
	docker compose --profile managed-state up -d postgres-managed-state

managed-state-postgres-status: ## Show the disposable PostgreSQL qualification fixture status.
	docker compose --profile managed-state ps postgres-managed-state

managed-state-postgres-stop: ## Stop the disposable PostgreSQL qualification fixture.
	docker compose --profile managed-state stop postgres-managed-state

managed-state-postgres-check: ## Run managed-persistence integration tests against the loopback PostgreSQL fixture.
	cd backend && AIFA_TEST_POSTGRES_DSN=postgresql://aifa_qualification@127.0.0.1:55432/aifa_qualification uv run pytest -q -m postgres tests/test_managed_persistence.py

delivery-check: ## Verify delivery workflows, release-bundle contracts, and pinned build policy.
	cd backend && uv run pytest -q tests/test_delivery_workflows.py tests/test_release_bundle.py

infrastructure-check: ## Format and validate all Terraform roots and run infrastructure contract tests.
	terraform fmt -check -recursive infrastructure/terraform
	cd infrastructure/terraform/bootstrap && terraform init -backend=false && terraform validate
	cd infrastructure/terraform/shared && terraform init -backend=false && terraform validate
	cd infrastructure/terraform/environments/staging && terraform init -backend=false && terraform validate
	cd infrastructure/terraform/environments/staging-workloads && terraform init -backend=false && terraform validate
	cd infrastructure/terraform/environments/staging-edge && terraform init -backend=false && terraform validate
	cd backend && uv run pytest -q tests/test_staging_infrastructure.py tests/test_private_edge.py tests/test_live_provider_deployment.py tests/test_delivery_workflows.py

container-build: ## Build the local non-root backend and frontend container images.
	docker build --file infrastructure/container/backend/Dockerfile --tag ai-finance-assistant-backend:local .
	docker build --file infrastructure/container/frontend/Dockerfile --tag ai-finance-assistant-frontend:local .

mirror-merged-main-images: ## Mirror both merged-main GHCR images into Artifact Registry by immutable digest.
	./infrastructure/terraform/scripts/mirror-merged-main-images.sh

set-deployment-image-variables: ## Set and verify backend/frontend image variables for DEPLOYMENT_ENVIRONMENT.
	./infrastructure/terraform/scripts/set-deployment-image-variables.sh "$(DEPLOYMENT_ENVIRONMENT)"

knowledge-release-staging: ## Transfer and qualify shared knowledge collections in staging.
	./infrastructure/terraform/scripts/release-shared-knowledge.sh

rotate-qdrant-runtime-key-staging: ## Qualify and rotate the staging Qdrant read-only runtime key.
	./infrastructure/terraform/scripts/rotate-qdrant-runtime-key.sh

private-edge-up: ## Create and qualify the staging HTTPS, IAP, routing, and DNS edge.
	./infrastructure/terraform/scripts/private-edge-up.sh

private-edge-down: ## Remove the staging private edge after its reviewed DNS and audience shutdown.
	./infrastructure/terraform/scripts/private-edge-down.sh

qualify-private-demo: ## Run the owner-authenticated deployed credential-free product qualification.
	./infrastructure/terraform/scripts/qualify-private-demo.sh

live-providers-staging-up: ## Activate and qualify the approved owner-only staging live-provider posture.
	./infrastructure/terraform/scripts/live-providers-staging-up.sh

live-providers-staging-down: ## Restore credential-free staging and remove disposable provider secrets.
	./infrastructure/terraform/scripts/live-providers-staging-down.sh

frontend-install: ## Install pinned frontend dependencies with pnpm.
	cd frontend && pnpm install

frontend-dev: ## Run the Vite development server at the /finance_assistant base path.
	cd frontend && pnpm dev

frontend-check: ## Run frontend formatting, lint, type, unit-test, and production-build gates.
	cd frontend && pnpm format:check
	cd frontend && pnpm lint
	cd frontend && pnpm typecheck
	cd frontend && pnpm test
	cd frontend && pnpm build

qdrant-up: ## Start the persistent loopback Qdrant development service.
	docker compose up -d qdrant

qdrant-status: ## Show the loopback Qdrant development service status.
	docker compose ps qdrant

qdrant-stop: ## Stop loopback Qdrant without deleting its persistent volume.
	docker compose stop qdrant

qdrant-check: ## Run the explicit integration suite against the configured Qdrant URL.
	cd backend && AIFA_TEST_QDRANT_URL=$(QDRANT_URL) uv run pytest -q tests/test_qdrant_integration.py

knowledge-finance: ## Build, evaluate, and activate the versioned Finance knowledge collection.
	cd backend && uv run python -m ai_finance_assistant.knowledge.cli --qdrant-url $(QDRANT_URL) run --kb finance_education --qrels data/knowledge/finance-education/retrieval-cases.v1.json --activate

knowledge-tax: ## Build, evaluate, and activate the versioned Tax knowledge collection.
	cd backend && uv run python -m ai_finance_assistant.knowledge.cli --qdrant-url $(QDRANT_URL) run --kb tax_education --qrels data/knowledge/tax-education/retrieval-cases.v1.json --activate

knowledge-validate: ## Validate both active Finance and Tax knowledge collection contracts.
	cd backend && uv run python -m ai_finance_assistant.knowledge.cli --qdrant-url $(QDRANT_URL) validate --kb finance_education
	cd backend && uv run python -m ai_finance_assistant.knowledge.cli --qdrant-url $(QDRANT_URL) validate --kb tax_education

verify: backend-check frontend-check ## Run the complete backend and frontend deterministic checks.

knowledge-check: verify qdrant-check knowledge-validate ## Run application checks plus Qdrant integration and active-collection validation.

calculations-check: ## Run deterministic Portfolio, Goal, and cash-flow contract tests.
	cd backend && uv run pytest -q tests/test_portfolio_import.py tests/test_portfolio_analysis.py tests/test_goal_projection.py tests/test_cash_flow_contracts.py

providers-check: ## Run deterministic market/news provider formatting, typing, and adapter tests.
	cd backend && uv run ruff format --check src tests
	cd backend && uv run ruff check src tests
	cd backend && uv run mypy
	cd backend && uv run pytest -q tests/test_provider_adapters.py

assistant-check: ## Run six-agent routing, workflow, application, and observability checks.
	cd backend && uv run ruff format --check src tests
	cd backend && uv run ruff check src tests
	cd backend && uv run mypy
	cd backend && uv run pytest -q tests/test_routing.py tests/test_agents.py tests/test_workflow.py tests/test_workflow_application.py tests/test_observability.py

model-check: ## Run credential-free OpenAI adapter, model factory, workflow, and observability checks.
	cd backend && uv run ruff format --check src tests
	cd backend && uv run ruff check src tests
	cd backend && uv run mypy
	cd backend && uv run pytest -q tests/test_openai_model_adapter.py tests/test_model_factory.py tests/test_agents.py tests/test_workflow.py tests/test_workflow_application.py tests/test_observability.py

api-check: ## Run REST/SSE, persistence, provider-cache, health, and API observability checks.
	cd backend && uv run ruff format --check src tests
	cd backend && uv run ruff check src tests
	cd backend && uv run mypy
	cd backend && uv run pytest -q tests/test_http_api.py tests/test_persistence.py tests/test_durable_provider_cache.py tests/test_api_observability.py tests/test_public_http_contract.py tests/test_health.py

product-ui-check: frontend-check ## Run frontend gates plus browser-contract, API, telemetry, and Playwright journeys.
	cd backend && uv run ruff format --check src tests
	cd backend && uv run ruff check src tests
	cd backend && uv run mypy
	cd backend && uv run pytest -q tests/test_browser_telemetry.py tests/test_frontend_contract.py tests/test_http_api.py tests/test_public_http_contract.py
	cd frontend && pnpm test:e2e

inspector-check: frontend-check ## Run frontend gates plus Inspector fidelity, redaction, API, and Playwright checks.
	cd backend && uv run ruff format --check src tests
	cd backend && uv run ruff check src tests
	cd backend && uv run mypy
	cd backend && uv run pytest -q tests/test_inspector_contract.py tests/test_http_api.py tests/test_persistence.py tests/test_api_observability.py tests/test_contracts.py tests/test_redaction.py
	cd frontend && pnpm exec playwright test e2e/execution-inspector.spec.ts

response-cache-up: ## Start the loopback Redis response-cache service.
	docker compose up -d redis-response-cache

response-cache-status: ## Show the loopback Redis response-cache service status.
	docker compose ps redis-response-cache

response-cache-stop: ## Stop the loopback Redis response-cache service.
	docker compose stop redis-response-cache

response-cache-check: ## Run Redis response-cache integration tests against the loopback service.
	cd backend && AIFA_TEST_REDIS_URL=redis://127.0.0.1:6379/0 uv run pytest -q -m redis tests/test_response_cache_redis.py

response-cache-calibrate: ## Evaluate the pinned semantic response-cache similarity threshold.
	cd backend && uv run python -m ai_finance_assistant.response_cache.evaluation --cases data/response-cache/semantic-calibration.v1.json --minimum-similarity 0.92

response-cache-benchmark: ## Benchmark deterministic response-cache outcomes and avoided model work.
	cd backend && AIFA_ENV_FILE=.test.env uv run python -m ai_finance_assistant.response_cache.benchmark --samples 20 --model-delay-ms 10

qualification-check: ## Regenerate the full EVAL-01–EVAL-18 qualification report.
	cd backend && .venv/bin/python -m ai_finance_assistant.evaluation.runner --manifest data/qualification/release-cases.v1.json --repo-root .. --output artifacts/release/qualification-report.v1.json --profile full

mcp-stdio: ## Start the read-only Finance Assistant MCP server over stdio.
	cd backend && uv run python -m ai_finance_assistant.mcp_adapter

release-check: ## Run coverage, full qualification, MCP/release audits, and Compose validation.
	cd frontend && pnpm test:coverage
	$(MAKE) qualification-check
	cd backend && AIFA_REQUIRE_QUALIFICATION_PASS=true uv run pytest -q tests/test_mcp_adapter.py tests/test_release_bundle.py
	docker compose config --quiet

observability-up: ## Start the optional loopback OpenTelemetry Collector debug sink.
	docker compose --profile observability up -d otel-collector

observability-status: ## Show the loopback OpenTelemetry Collector status.
	docker compose --profile observability ps otel-collector

observability-stop: ## Stop the loopback OpenTelemetry Collector.
	docker compose --profile observability stop otel-collector

provider-live-check: ## Run explicitly authorized quota-bounded live market/news provider tests.
	cd backend && AIFA_TEST_ENV_FILE=.env AIFA_RUN_LIVE_PROVIDER_TESTS=true AIFA_PROVIDER_MODE=live uv run pytest -q -m live_provider tests/test_live_provider_adapters.py

model-live-check: ## Run explicitly authorized quota-bounded live OpenAI model tests.
	cd backend && AIFA_TEST_ENV_FILE=.env AIFA_RUN_LIVE_MODEL_TESTS=true AIFA_MODEL_MODE=openai_live uv run pytest -q -m live_model tests/test_live_model_adapter.py

m1-check: knowledge-check ## Compatibility alias for the knowledge capability gate.
m2-check: calculations-check ## Compatibility alias for the deterministic calculations gate.
m3-check: providers-check ## Compatibility alias for the provider-adapter gate.
m4-check: assistant-check ## Compatibility alias for the six-agent workflow gate.
m4-1-check: model-check ## Compatibility alias for the live-model adapter gate.
m5-check: api-check ## Compatibility alias for the REST, SSE, and persistence gate.
m6-check: product-ui-check ## Compatibility alias for the product UI gate.
m6-1-check: ## Run response-cache formatting, typing, API, workflow, evaluation, and benchmark tests.
	cd backend && uv run ruff format --check src tests
	cd backend && uv run ruff check src tests
	cd backend && uv run mypy
	cd backend && uv run pytest -q tests/test_response_cache.py tests/test_response_cache_workflow.py tests/test_response_cache_api.py tests/test_response_cache_evaluation.py tests/test_response_cache_benchmark.py tests/test_health.py tests/test_http_api.py
m7-check: inspector-check ## Compatibility alias for the Inspector fidelity gate.
m8-check: qualification-check ## Compatibility alias for the consolidated qualification gate.
m9-check: release-check ## Compatibility alias for the release-package gate.
