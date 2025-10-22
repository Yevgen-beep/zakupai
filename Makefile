# Makefile for ZakupAI Stage6
SHELL := /bin/bash

.PHONY: help test stage6-up stage6-down stage6-status

help: ## Show available targets
	@grep -E '^[a-zA-Z0-9_-]+:.*?## ' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

test: ## Test a specific service health: make test SERVICE=calc-service
	@if [ -z "$(SERVICE)" ]; then \
		echo "Usage: make test SERVICE=<service-name>"; \
		echo "Example: make test SERVICE=calc-service"; \
		exit 1; \
	fi
	@echo "Testing $(SERVICE)..."
	@PORT=$$(docker port $(SERVICE) 2>/dev/null | grep -oP '0.0.0.0:\K\d+' | head -1); \
	if [ -z "$$PORT" ]; then \
		echo "❌ Container $(SERVICE) not found or no exposed ports"; \
		exit 1; \
	fi; \
	echo "Checking http://localhost:$$PORT/health"; \
	if curl -sf http://localhost:$$PORT/health > /dev/null; then \
		echo "✅ $(SERVICE) is healthy and responding"; \
	else \
		echo "❌ $(SERVICE) is not responding on port $$PORT"; \
		exit 1; \
	fi

stage6-up: ## Start Stage6 monitoring stack
	docker compose --profile stage6 -f docker-compose.yml -f docker-compose.override.stage6.yml -f docker-compose.override.stage6.monitoring.yml up -d

stage6-down: ## Stop Stage6 monitoring stack
	docker compose --profile stage6 -f docker-compose.yml -f docker-compose.override.stage6.yml -f docker-compose.override.stage6.monitoring.yml down

stage6-status: ## Show Stage6 stack status
	@echo "=== Containers Status ==="
	@docker ps --filter "name=zakupai" --format "table {{.Names}}\t{{.Status}}" | head -20
	@echo ""
	@echo "=== Prometheus Targets ==="
	@docker exec zakupai-prometheus wget -qO- http://localhost:9090/api/v1/targets 2>/dev/null | jq -r '.data.activeTargets | length as $$total | map(select(.health=="up")) | length as $$up | "\($$up)/\($$total) targets UP"' || echo "❌ Prometheus not accessible"
	@echo ""
	@echo "=== Grafana Dashboard ==="
	@curl -s -u admin:admin 'http://localhost:3030/api/dashboards/uid/zakupai-overview' 2>/dev/null | jq -r '"Dashboard: " + .dashboard.title + " (" + (.dashboard.panels | length | tostring) + " panels)"' || echo "❌ Grafana not accessible"
