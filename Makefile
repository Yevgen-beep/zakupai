# Makefile for ZakupAI
SHELL := /bin/bash
COMPOSE := docker compose
DB_CONT := zakupai-db
PYTHON_EXEC ?= python3
DB_USER ?= ${POSTGRES_USER}
DB_NAME ?= ${DB_NAME_OVERRIDE:-zakupai}

.PHONY: help up down restart ps logs build pull dbsh test lint fmt smoke smoke-calc smoke-risk smoke-doc smoke-emb seed gateway-up smoke-gw migrate alembic-rev alembic-stamp test-sec e2e workflows-up workflows-down setup-workflows

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
	docker exec -it $(DB_CONT) psql -U $(DB_USER) -d $(DB_NAME)

test: ## Run pytest in all services
	@echo "Running pytest in all services..."
	@find services -maxdepth 2 -name "tests" -type d | while read dir; do \
		service_dir=$$(dirname "$$dir"); \
		echo "Testing $$service_dir"; \
		cd "$$service_dir" && $(PYTHON_EXEC) -m pytest -q tests/ || exit 1; \
		cd - >/dev/null; \
	done

lint: ## Run ruff and yamllint
	ruff check services
	yamllint .

fmt: ## Run black, ruff format and isort
	black services
	ruff format services
	isort services

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

migrate: ## Run Alembic migrations
	$(COMPOSE) run --rm migrator

alembic-rev: ## Create new Alembic revision (usage: make alembic-rev m="message")
	$(COMPOSE) run --rm migrator bash -lc 'alembic -c db/alembic.ini revision -m "$(m)"'

alembic-stamp: ## Stamp current database as head revision
	$(COMPOSE) run --rm migrator bash -lc 'alembic -c db/alembic.ini stamp head'

test-sec: ## Run security validation tests only
	@echo "Running security validation tests..."
	@find services -path "*/tests/test_validation.py" -type f | while read file; do \
		service_dir=$$(dirname $$(dirname "$$file")); \
		echo "Testing validation in $$service_dir"; \
		cd "$$service_dir" && $(PYTHON_EXEC) -m pytest -q tests/test_validation.py || exit 1; \
		cd - >/dev/null; \
	done

e2e: ## Run end-to-end pipeline tests
	@echo "🚀 Running ZakupAI E2E Tests..."
	@$(PYTHON_EXEC) scripts/e2e/mock_run.py

backup-now: ## Run database backup immediately (dry-run by default)
	@echo "🗄️  Running database backup..."
	@if docker-compose ps db-backup | grep -q Up; then \
		$(COMPOSE) exec -e DRY_RUN=true db-backup /scripts/backup.sh; \
	else \
		echo "⚠️  Backup service not running, using test simulation..."; \
		./scripts/test_backup.sh; \
	fi

backup-now-real: ## Run database backup immediately (real backup)
	@echo "🗄️  Running REAL database backup..."
	@$(COMPOSE) exec -e DRY_RUN=false db-backup /scripts/backup.sh

backup-logs: ## Show backup service logs
	@$(COMPOSE) logs -f db-backup

# Workflow services
workflows-up: ## Start n8n and Flowise workflow services
	$(COMPOSE) -f docker-compose.workflows.yml --env-file .env.workflows up -d
	@echo "✅ Workflow services started"
	@echo "   n8n: http://localhost:5678"
	@echo "   Flowise: http://localhost:3000"

workflows-down: ## Stop workflow services
	$(COMPOSE) -f docker-compose.workflows.yml down

setup-workflows: ## Setup and configure workflow services
	@echo "🔄 Setting up workflows..."
	./scripts/setup-workflows.sh
