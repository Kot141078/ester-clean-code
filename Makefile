# Makefile — udobnye tseli dlya iteratsii G (Observability & Release One-Shot)

SHELL := /bin/bash
BASE_URL ?= http://localhost:5000

.PHONY: help
help:
	@echo "Targets:"
	@echo "  observability-up     - podnyat lokalnuyu nablyudaemost (docker compose)"
	@echo "  observability-down   - ostanovit stek nablyudaemosti"
	@echo "  test-perf            - pytest -m perf -k metrics"
	@echo "  test-smoke           - pytest -m smoke"
	@echo "  helm-apply           - primenit chart s values.observability.yaml"
	@echo "  release-preview      - one-shot reliz v0.1-preview"

.PHONY: observability-up
observability-up:
	bash scripts/observability_up.sh

.PHONY: observability-down
observability-down:
	-docker compose -f docker-compose.observability.yml down

.PHONY: test-perf
test-perf:
	ESTER_BASE_URL=$(BASE_URL) pytest -m perf -k metrics -q

.PHONY: test-smoke
test-smoke:
	ESTER_BASE_URL=$(BASE_URL) pytest -m smoke -q

.PHONY: helm-apply
helm-apply:
	helm upgrade --install ester ./charts/ester -n ester --create-namespace -f values.observability.yaml

.PHONY: release-preview
release-preview:
	bash scripts/release_preview.sh
