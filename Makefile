# Makefile for ZakupAI
SHELL := /bin/bash
COMPOSE := docker compose
DB_CONT := zakupai-db

.PHONY: help up down restart ps logs build pull dbsh test lint fmt smoke smoke-calc smoke-risk smoke-doc smoke-emb seed gateway-up smoke-gw

help: ## Show available targets
	@grep -E '^[a-zA-Z0-9_-]+:.*?## ' $(MAKEFILE_LIST) | sed -E 's/:.*## /: /' | sort

up: ## Build and start containers
	$(COMPOSE) up -d --build

down: ## Stop and remove containers
	$(COMPOSE) down

restart: ## Restart all containers
	$(COMPOSE) restart

ps: ## Show containers status
	$(COMPOSE) ps

logs: ## Tail logs (all or S=<service>) last 100 lines
	@[ -z "$(S)" ] && $(COMPOSE) logs -f --tail=100 || $(COMPOSE) logs -f --tail=100 $(S)

build: ## Build Docker images
	$(COMPOSE) build

pull: ## Pull Docker images
	$(COMPOSE) pull

dbsh: ## Open psql shell in the DB container
	docker exec -it $(DB_CONT) psql -U zakupai -d zakupai

test: ## Run pytest in all services
	@echo "Running pytest in all services..."
	@find services -maxdepth 2 -name "tests" -type d | while read dir; do \
		service_dir=$$(dirname "$$dir"); \
		echo "Testing $$service_dir"; \
		cd "$$service_dir" && /home/mint/projects/claude_sandbox/zakupai/.venv/bin/python -m pytest -q tests/ || exit 1; \
		cd - >/dev/null; \
	done

lint: ## TODO: ruff/flake8/yamllint/markdownlint
	@echo "TODO: implement linters"

fmt: ## TODO: black/ruff formatters
	@echo "TODO: implement formatters"

smoke: ## Run full smoke script
	./scripts/smoke.sh

smoke-calc: ## Smoke calc-service only
	curl -s -X POST http://localhost:8001/calc/margin \
	  -H 'content-type: application/json' \
	  -d '{"lot_price":1500000,"cost":420000,"logistics":50000,"vat_rate":12,"price_includes_vat":true,"lot_id":1}' \
	| jq '.revenue_net,.profit' ; \
	docker exec $(DB_CONT) psql -U zakupai -d zakupai -c "SELECT count(*) FROM finance_calcs;"

smoke-risk: ## Smoke risk-engine only
	curl -s -X POST http://localhost:8002/risk/score \
	  -H 'content-type: application/json' \
	  -d '{"lot_id":1}' | jq '.saved,.score' ; \
	curl -s http://localhost:8002/risk/explain/1 | jq '.flags' ; \
	docker exec $(DB_CONT) psql -U zakupai -d zakupai -c "SELECT count(*) FROM risk_evaluations;"

smoke-doc: ## Smoke doc-service only
	curl -s -X POST http://localhost:8003/tldr \
	  -H 'content-type: application/json' -d '{"lot_id":1}' | jq '.lines' ; \
	curl -s -X POST http://localhost:8003/letters/generate \
	  -H 'content-type: application/json' \
	  -d '{"template":"guarantee","context":{"supplier_name":"ТОО Ромашка","lot_title":"Поставка картриджей HP","lot_id":1,"contact":"+7 777 000 00 00"}}' \
	| jq '.html|length'

smoke-emb: ## Smoke embedding-api only
	curl -s -X POST http://localhost:8004/index \
	  -H 'content-type: application/json' \
	  -d '{"ref_id":"doc:smoke","text":"Поставка картриджей HP 305A"}' >/dev/null ; \
	curl -s -X POST http://localhost:8004/search \
	  -H 'content-type: application/json' \
	  -d '{"query":"картриджи HP 305A","top_k":1}' | jq '.' ; \
	docker exec $(DB_CONT) psql -U zakupai -d zakupai -c "SELECT count(*) FROM embeddings;"

seed: ## Seed database with test data
	bash scripts/seed.sh

gateway-up: ## Start nginx gateway
	$(COMPOSE) up -d gateway

smoke-gw: ## Test nginx gateway with rate limiting
	curl -fsS http://localhost:8080/calc/health
	curl -fsS http://localhost:8080/risk/health
	curl -fsS http://localhost:8080/doc/health
	curl -fsS http://localhost:8080/emb/health
	@echo "Burst /calc/penalty to hit rate-limit"
	@for i in $$(seq 1 120); do \
		curl -s -o /dev/null -w "%{http_code}\n" \
			-X POST http://localhost:8080/calc/penalty \
			-H 'content-type: application/json' \
			-d '{"contract_sum":1000,"days_overdue":1,"daily_rate_pct":0.1}'; \
	done | sort | uniq -c
