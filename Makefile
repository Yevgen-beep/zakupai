# Makefile for ZakupAI
SHELL := /bin/bash
COMPOSE := docker compose
DB_CONT := zakupai-db
PYTHON_EXEC ?= python3
DB_USER ?= ${POSTGRES_USER}
DB_NAME ?= ${DB_NAME_OVERRIDE:-zakupai}

.PHONY: help up down restart ps logs build pull dbsh test lint fmt smoke smoke-calc smoke-risk smoke-doc smoke-emb seed gateway-up smoke-gw migrate alembic-rev alembic-stamp test-sec e2e workflows-up workflows-down setup-workflows test-priority1 chroma-up chroma-test etl-test test-priority2 webui-test stage6-up stage6-down stage6-smoke stage6-status stage6-logs monitoring-test monitoring-test-ci monitoring-test-keep

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

# Priority 1 Integration Commands
test-priority1: ## Test Priority 1 integration (API Gateway + ChromaDB)
	@echo "🚀 Testing Priority 1 integration (optimized with fail-fast)..."
	@if [ -f .venv/bin/activate ]; then \
		source .venv/bin/activate && python -m pytest tests/test_priority1.py -q --maxfail=1 --disable-warnings -v; \
	else \
		$(PYTHON_EXEC) -m pytest tests/test_priority1.py -q --maxfail=1 --disable-warnings -v; \
	fi

chroma-up: ## Start ChromaDB and related services
	$(COMPOSE) up -d chromadb embedding-api goszakup-api
	@echo "✅ ChromaDB services started:"
	@echo "   ChromaDB: http://localhost:8010"
	@echo "   Embedding API: http://localhost:7010"
	@echo "   Goszakup API Gateway: http://localhost:7005"

chroma-test: ## Quick ChromaDB connectivity test
	@echo "🔍 Testing ChromaDB connectivity..."
	@curl -f http://localhost:8010/api/v2/heartbeat 2>/dev/null && echo "✅ ChromaDB OK" || echo "❌ ChromaDB failed"
	@curl -f http://localhost:7010/health && echo "✅ Embedding API OK" || echo "❌ Embedding API failed"
	@curl -f http://localhost:7005/health && echo "✅ Goszakup API OK" || echo "❌ Goszakup API failed"

etl-migrate: ## Run Alembic migrations for ETL service
	@echo "🗄️  Running ETL service migrations..."
	@cd services/etl-service && $(PYTHON_EXEC) -m alembic upgrade head

etl-test: ## Run pytest tests for ETL service
	@echo "🧪 Running ETL service tests..."
	@cd services/etl-service && $(PYTHON_EXEC) -m pytest test_upload.py -v

test-priority2: ## Test Priority 2 integration (ETL service OCR pipeline + ChromaDB)
	@echo "🚀 Testing Priority 2 integration..."
	@echo "🗄️  Starting required services..."
	@$(COMPOSE) up -d db chromadb embedding-api
	@echo "⏳ Waiting for services to be ready..."
	@timeout 60 bash -c "until docker compose exec db pg_isready -U zakupai; do sleep 2; done"
	@timeout 60 bash -c "until curl -fsS http://localhost:8010/api/v2/heartbeat 2>/dev/null; do sleep 2; done"
	@timeout 60 bash -c "until curl -fsS http://localhost:7010/health 2>/dev/null; do sleep 2; done"
	@echo "🗄️  Running migrations..."
	@$(MAKE) etl-migrate
	@echo "📋 Running ETL service tests..."
	@cd services/etl-service && $(PYTHON_EXEC) -m pytest test_upload.py -v
	@echo "🧪 Running integration tests..."
	@bash services/etl-service/test_etl_upload.sh
	@echo "🔍 Testing ChromaDB search functionality..."
	@curl -s -X POST http://localhost:7010/search \
	  -H 'content-type: application/json' \
	  -d '{"query":"тест OCR","top_k":5,"collection":"etl_documents"}' | jq '.'
	@echo "✅ Priority 2 integration tests completed!"

test-priority3: ## Test Priority 3 E2E workflow (Goszakup API → ETL → ChromaDB → Telegram + Web UI)
	@echo "🚀 Testing Priority 3 E2E workflow..."
	@echo "🗄️  Starting all required services..."
	@$(COMPOSE) up -d db chromadb embedding-api etl-service goszakup-api web-ui n8n
	@echo "⏳ Waiting for services to be ready..."
	@timeout 90 bash -c "until docker compose exec db pg_isready -U zakupai; do sleep 2; done"
	@timeout 90 bash -c "until curl -fsS http://localhost:8010/api/v2/heartbeat 2>/dev/null; do sleep 2; done"
	@timeout 90 bash -c "until curl -fsS http://localhost:7010/health 2>/dev/null; do sleep 2; done"
	@timeout 90 bash -c "until curl -fsS http://localhost:7011/health 2>/dev/null; do sleep 2; done"
	@timeout 90 bash -c "until curl -fsS http://localhost:7005/health 2>/dev/null; do sleep 2; done"
	@timeout 90 bash -c "until curl -fsS http://localhost:8082/health 2>/dev/null; do sleep 2; done"
	@echo "🗄️  Running migrations..."
	@$(MAKE) etl-migrate
	@echo "🧪 Running E2E workflow tests..."
	@bash services/etl-service/test_e2e_workflow.sh
	@echo "🔍 Testing URL upload functionality..."
	@bash services/etl-service/test_etl_upload.sh
	@echo "🌐 Running Web UI E2E tests..."
	@$(MAKE) webui-test
	@echo "✅ Priority 3 E2E workflow tests completed!"

n8n-up: ## Start n8n workflow automation service
	@echo "🔄 Starting n8n workflow service..."
	@$(COMPOSE) up -d n8n
	@echo "✅ n8n available at: http://localhost:5678"
	@echo "📋 Import workflow from: n8n/workflows/goszakup-etl-workflow.json"

webui-test: ## Run E2E tests for Web UI (pytest + bash script)
	@echo "🧪 Running Web UI E2E tests..."
	@cd web && $(PYTHON_EXEC) -m pytest test_e2e_webui.py -v
	@echo "🔍 Running Web UI smoke tests..."
	@bash web/test_e2e_webui.sh

# =============================================================================
# STAGE6: ЕДИНЫЙ БОЕВОЙ СТЕК (ЯДРО + МОНИТОРИНГ)
# =============================================================================

stage6-up: ## Start full Stage6 stack (core + monitoring)
	@echo "🚀 Starting Stage6 stack (core + monitoring)..."
	$(COMPOSE) -f docker-compose.yml -f docker-compose.override.stage6.yml --profile stage6 up -d --build
	@echo "✅ Stage6 stack started!"
	@echo "   📊 Grafana: http://localhost:3001 (admin/admin)"
	@echo "   📈 Prometheus: http://localhost:9090"
	@echo "   🚨 Alertmanager: http://localhost:9093"
	@echo "   🌐 ZakupAI Gateway: http://localhost:8080"
	@echo "   📱 Web UI: http://localhost:8082"
	@echo "   🔧 Node Exporter: http://localhost:19100/metrics"
	@echo "   📊 cAdvisor: http://localhost:8081"

stage6-down: ## Stop Stage6 stack
	@echo "🛑 Stopping Stage6 stack..."
	$(COMPOSE) -f docker-compose.yml -f docker-compose.override.stage6.yml --profile stage6 down
	@echo "✅ Stage6 stack stopped!"

stage6-smoke: ## Run Stage6 smoke tests
	@echo "🧪 Running Stage6 smoke tests..."
	@bash stage6-smoke.sh
	@echo "✅ Stage6 smoke tests completed!"

stage6-status: ## Show Stage6 services status
	@echo "📊 Stage6 Stack Status:"
	@echo "======================"
	@$(COMPOSE) -f docker-compose.yml -f docker-compose.override.stage6.yml --profile stage6 ps --format "table {{.Name}}\t{{.State}}\t{{.Status}}\t{{.Ports}}"

stage6-logs: ## Show Stage6 services logs
	@echo "📋 Stage6 Services Logs (last 50 lines):"
	@echo "========================================"
	@$(COMPOSE) -f docker-compose.yml -f docker-compose.override.stage6.yml --profile stage6 logs --tail=50

monitoring-test: ## Run Stage6 monitoring validation tests (full stack test)
	@bash stage6-monitoring-test.sh

monitoring-test-ci: ## Run monitoring tests in CI mode (assumes stack is running)
	@bash stage6-monitoring-test.sh --ci

monitoring-test-keep: ## Run monitoring tests and keep stack running
	@bash stage6-monitoring-test.sh --keep-up

# =============================================================================
# ALEMBIC MIGRATION TARGETS
# =============================================================================

mig-revision: ## Create new Alembic revision (usage: make mig-revision SERVICE=billing-service m="message")
ifndef SERVICE
	$(error SERVICE is required. Usage: make mig-revision SERVICE=billing-service m="message")
endif
ifndef m
	$(error Message is required. Usage: make mig-revision SERVICE=$(SERVICE) m="your message")
endif
	cd services/$(SERVICE) && alembic revision -m "$(m)"

mig-upgrade: ## Run Alembic upgrade to head (usage: make mig-upgrade SERVICE=billing-service)
ifndef SERVICE
	$(error SERVICE is required. Usage: make mig-upgrade SERVICE=billing-service)
endif
	cd services/$(SERVICE) && alembic upgrade head

mig-downgrade: ## Run Alembic downgrade (usage: make mig-downgrade SERVICE=billing-service r="revision")
ifndef SERVICE
	$(error SERVICE is required. Usage: make mig-downgrade SERVICE=billing-service r="revision")
endif
ifndef r
	$(error Revision is required. Usage: make mig-downgrade SERVICE=$(SERVICE) r="-1")
endif
	cd services/$(SERVICE) && alembic downgrade $(r)

mig-stamp: ## Stamp current database as head revision (usage: make mig-stamp SERVICE=billing-service)
ifndef SERVICE
	$(error SERVICE is required. Usage: make mig-stamp SERVICE=billing-service)
endif
	cd services/$(SERVICE) && alembic stamp head

mig-sql: ## Generate SQL for upgrade (usage: make mig-sql SERVICE=billing-service)
ifndef SERVICE
	$(error SERVICE is required. Usage: make mig-sql SERVICE=billing-service)
endif
	cd services/$(SERVICE) && alembic upgrade head --sql
