# Makefile for ZakupAI Stage6
SHELL := /bin/bash

.PHONY: help test stage6-status

help:
	@echo "Available targets:"
	@echo "  make test SERVICE=<name>  - Test service health"
	@echo "  make stage6-status        - Show Stage6 stack status"

test:
	@if [ -z "$(SERVICE)" ]; then echo "Usage: make test SERVICE=<service-name>"; exit 1; fi
	@echo "Testing $(SERVICE)..."
	@PORT=$$(docker port zakupai-$(SERVICE) 2>/dev/null | grep -oP '0.0.0.0:\K\d+' | head -1); \
	if [ -z "$$PORT" ]; then echo "❌ Container not found"; exit 1; fi; \
	echo "Checking http://localhost:$$PORT/health"; \
	if curl -sf http://localhost:$$PORT/health > /dev/null; then \
		echo "✅ $(SERVICE) is healthy"; \
	else \
		echo "❌ $(SERVICE) not responding"; exit 1; \
	fi

stage6-status:
	@echo "=== Prometheus Targets ==="
	@docker exec zakupai-prometheus wget -qO- http://localhost:9090/api/v1/targets 2>/dev/null | jq -r '.data.activeTargets | map(select(.health=="up")) | length as $$up | .data.activeTargets | length as $$total | "\($$up)/\($$total) UP"' || echo "Error"
	@echo "=== Grafana Dashboard ==="
	@curl -s -u admin:admin http://localhost:3030/api/dashboards/uid/zakupai-overview 2>/dev/null | jq -r '"\(.dashboard.title) - \(.dashboard.panels | length) panels"' || echo "Error"
