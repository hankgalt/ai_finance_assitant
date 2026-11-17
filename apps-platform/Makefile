PYTHON ?= $(if $(wildcard .venv/bin/python),.venv/bin/python,python3)

.PHONY: check governance-check contract-check fixture-check runtime-check

check: governance-check contract-check fixture-check runtime-check ## Run every implemented deterministic platform check.

governance-check: ## Verify the standalone project shell without credentials or external services.
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) -m unittest tests.test_governance tests.test_finance_integration_draft

contract-check: ## Verify versioned contracts without credentials or external services.
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) -m unittest tests.test_contracts

fixture-check: ## Verify the deterministic in-process fixture edge without external services.
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) -m unittest tests.test_fixtures

runtime-check: ## Verify the Shared Edge interface without credentials or external network access.
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) -m unittest tests.test_edge_runtime tests.test_proxy tests.test_observability
