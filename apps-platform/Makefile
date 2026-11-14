PYTHON ?= python3

.PHONY: check governance-check

check: governance-check ## Run every currently implemented deterministic platform check.

governance-check: ## Verify the standalone project shell without credentials or external services.
	$(PYTHON) -m unittest discover -s tests -p 'test_*.py'
