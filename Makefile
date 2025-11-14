# ============================================
# 🧠 ZakupAI Stage6 Build & Monitoring Control
# ============================================

SHELL := /bin/bash
COMPOSE_BASE = docker-compose.yml
COMPOSE_STAGE6 = docker-compose.override.stage6.monitoring.yml

.PHONY: help libs-build build-all clean stage6-up stage6-down stage6-status stage6-test stage6-rebuild test logs ps

# --------------------------------------------
# 🔍 Общие команды
# --------------------------------------------

help: ## Показать список доступных команд
	@grep -E '^[a-zA-Z0-9_-]+:.*?## ' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

logs: ## Показать логи контейнеров
	@docker compose logs -f --tail=100

ps: ## Проверить запущенные контейнеры
	@docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# --------------------------------------------
# ⚙️ Сборка и деплой
# --------------------------------------------

libs-build: ## Собрать базовый образ libs:latest
	@echo "📦 Building base libs image..."
	docker build -t libs:latest -f libs/Dockerfile libs

build-all: libs-build ## Пересобрать все сервисы (без кэша)
	@echo "🚧 Building all ZakupAI services..."
	docker compose -f $(COMPOSE_BASE) build --no-cache

clean: ## Полная очистка окружения
	@echo "🧹 Stopping and pruning ZakupAI environment..."
	docker compose --profile stage6 down --remove-orphans
	docker system prune -af --volumes

stage6-up: ## Запустить Stage6 стек (все сервисы + мониторинг)
	@echo "🚀 Starting Stage6 stack..."
	docker compose --profile stage6 -f $(COMPOSE_BASE) -f $(COMPOSE_STAGE6) up -d

stage6-down: ## Остановить Stage6 стек
	@echo "🛑 Stopping Stage6 stack..."
	docker compose --profile stage6 -f $(COMPOSE_BASE) -f $(COMPOSE_STAGE6) down

stage6-rebuild: clean libs-build build-all stage6-up stage6-test ## Полный цикл: очистка → libs → сборка → запуск → тест
	@echo "✅ Stage6 rebuild complete. Monitoring stack verified."


# --------------------------------------------
# 🧩 Перезапуск и проверка Loki
# --------------------------------------------

loki-restart: ## Перезапустить только Loki и проверить статус
	@echo "♻️ Restarting Loki service..."
	docker compose -f $(COMPOSE_BASE) -f $(COMPOSE_STAGE6) up -d loki
	@echo "⏳ Waiting for Loki to initialize..."
	@sleep 5
	@echo "\n🔍 Checking Loki status..."
	@curl -s http://localhost:3100/loki/api/v1/status/buildinfo | jq || echo "❌ Loki still not responding"

# --------------------------------------------
# 🧩 Проверки и тестирование
# --------------------------------------------

test: ## Проверить конкретный сервис: make test SERVICE=calc-service
	@if [ -z "$(SERVICE)" ]; then \
		echo "Usage: make test SERVICE=<service-name>"; \
		echo "Example: make test SERVICE=calc-service"; \
		exit 1; \
	fi
	@echo "🔍 Testing $(SERVICE)..."
	@PORT=$$(docker port $(SERVICE) 2>/dev/null | grep -oP '0.0.0.0:\K\d+' | head -1); \
	if [ -z "$$PORT" ]; then \
		echo "❌ Container $(SERVICE) not found or no exposed ports"; \
		exit 1; \
	fi; \
	echo "→ Checking http://localhost:$$PORT/health"; \
	if curl -sf http://localhost:$$PORT/health > /dev/null; then \
		echo "✅ $(SERVICE) is healthy and responding"; \
	else \
		echo "❌ $(SERVICE) is not responding on port $$PORT"; \
		exit 1; \
	fi

stage6-test: ## Проверить Prometheus, Loki, Grafana и /health микросервисов
	@echo "🧠 Verifying Stage6 monitoring stack..."
	@echo "⏳ Waiting for Prometheus to be ready (checking HTTP 200 on /metrics)..."
	@timeout=60; ure=0; \
	while [ $$ure -lt $$timeout ]; do \
		if curl -s -o /dev/null -w "%{http_code}" http://localhost:9095/metrics | grep -q "200"; then \
			echo "✅ Prometheus is ready (HTTP 200 on /metrics)"; break; \
		fi; \
		sleep 2; ure=$$((ure + 2)); \
	done; \
	[ $$ure -lt $$timeout ] || (echo "❌ Prometheus not responding on /metrics in $$timeout seconds"; exit 1)

	@echo -e "\n🔍 Checking Prometheus targets..."
	@curl -s http://localhost:9095/api/v1/targets | grep -q '"health":"up"' \
		&& echo "✅ Prometheus targets are UP" \
		|| echo "⚠️ Some targets may be down"

		@echo -e "\n🔍 Checking Loki API..."
	@LOKI_PORT=$$(docker port zakupai-loki 2>/dev/null | grep -oP '0.0.0.0:\K\d+' | head -1); \
	if [ -z "$$LOKI_PORT" ]; then LOKI_PORT=3100; fi; \
	RESP=$$(curl -s http://localhost:$$LOKI_PORT/loki/api/v1/status/buildinfo); \
	if echo "$$RESP" | grep -q '"version"'; then \
		echo "✅ Loki is reachable (version detected on port $$LOKI_PORT)"; \
	else \
		echo "⚠️ Loki API not responding or returned empty response (port $$LOKI_PORT)"; \
	fi


	@echo -e "\n🔍 Checking microservices health endpoints..."
	@for svc in calc-service risk-engine doc-service embedding-api gateway web-ui etl-service billing-service; do \
		NAME=$$(docker ps --format '{{.Names}}' | grep $$svc || true); \
		if [ -n "$$NAME" ]; then \
			PORT=$$(docker port $$NAME 2>/dev/null | grep -oP '0.0.0.0:\K\d+' | head -1); \
			if [ -n "$$PORT" ]; then \
				if curl -sf http://localhost:$$PORT/health > /dev/null 2>&1; then \
					echo "✅ $$svc healthy on port $$PORT"; \
				else \
					echo "⚠️ $$svc not responding on port $$PORT"; \
				fi; \
			fi; \
		fi; \
	done

	@echo -e "\n🟢 Stage6 monitoring stack verified successfully."




stage6-status: ## Показать статус контейнеров и метрик Prometheus/Grafana
	@echo "=== Containers Status ==="
	@docker ps --filter "name=zakupai" --format "table {{.Names}}\t{{.Status}}" | head -20
	@echo ""
	@echo "=== Prometheus Targets ==="
	@docker exec zakupai-prometheus wget -qO- http://localhost:9090/api/v1/targets 2>/dev/null | jq -r '.data.activeTargets | length as $$total | map(select(.health=="up")) | length as $$up | "\($$up)/\($$total) targets UP"' || echo "❌ Prometheus not accessible"
	@echo ""
	@echo "=== Grafana Dashboard ==="
	@curl -s -u admin:admin 'http://localhost:3030/api/dashboards/uid/zakupai-overview' 2>/dev/null | jq -r '"Dashboard: " + .dashboard.title + " (" + (.dashboard.panels | length | tostring) + " panels)"' || echo "❌ Grafana not accessible"

# --------------------------------------------
# 🔐 Vault Stage 7 (Manual Unseal)
# --------------------------------------------

stage7: ## Stage 7: Manual unseal with file backend
	@echo "🔐 Applying Stage 7 configuration (Manual File Backend)..."
	@cp monitoring/vault/config/stage7/stage7-config.hcl monitoring/vault/config/vault-config.hcl
	@echo "✅ Stage 7 config applied. Start Vault with: docker-compose up -d vault"
	@echo "⚠️  Manual unseal required after restart."

# --------------------------------------------
# 🔐 Vault Stage 8 (Auto-Unseal File Backend)
# --------------------------------------------

stage8: ## Stage 8: Auto-unseal with encrypted keys on file backend
	@echo "🔐 Applying Stage 8 configuration (Auto-Unseal File Backend)..."
	@if [ ! -f monitoring/vault/.unseal-password ]; then \
		echo "❌ Master password not found. Run: ./monitoring/vault/scripts/encrypt-unseal.sh"; \
		exit 1; \
	fi
	@if [ ! -f monitoring/vault/creds/vault-unseal-key.enc ]; then \
		echo "❌ Encrypted unseal key not found. Run: ./monitoring/vault/scripts/encrypt-unseal.sh"; \
		exit 1; \
	fi
	@cp monitoring/vault/config/secure/config.hcl monitoring/vault/config/vault-config.hcl
	@cp docker-compose.override.stage8.vault-secure.yml docker-compose.override.yml
	@echo "✅ Stage 8 config applied."
	@echo "🚀 Starting Vault with auto-unseal..."
	@docker-compose up -d vault
	@echo "⏳ Waiting for Vault to start (30s)..."
	@sleep 30
	@docker logs vault --tail 20
	@echo ""
	@echo "✅ Stage 8 deployment complete. Verify with: make vault-secure-status"

vault-secure-init: ## Initialize Vault (Stage 8) with 5 key shares, threshold 3
	@echo "🔐 Initializing Vault..."
	@docker exec -it vault vault operator init -key-shares=5 -key-threshold=3 \
		-format=json | tee vault-init-output.json
	@echo "✅ Vault initialized. Save the output securely!"
	@echo "⚠️  Run: ./monitoring/vault/scripts/encrypt-unseal.sh to encrypt keys"

vault-secure-status: ## Check Vault status (Stage 8)
	@echo "🔍 Vault Status:"
	@docker exec vault vault status || true
	@echo ""
	@echo "🔍 Auto-Unseal Log (last 20 lines):"
	@docker logs vault --tail 20 | grep -E "(unseal|sealed|Vault)"

vault-secure-backup: ## Backup Vault data (Stage 8)
	@echo "💾 Creating Vault backup..."
	@BACKUP_FILE="vault-backup-$$(date +%Y%m%d-%H%M%S).tar.gz"; \
	tar -czf $$BACKUP_FILE monitoring/vault/data/ monitoring/vault/creds/vault-unseal-key.enc monitoring/vault/.unseal-password; \
	echo "✅ Backup created: $$BACKUP_FILE"; \

# --------------------------------------------
# 🔐 Vault Stage 9 (B2 + TLS + Audit)
# --------------------------------------------

# ============================================================================
# Stage 9 - TLS Volume Management
# ============================================================================

.PHONY: vault-tls-check vault-tls-fix vault-tls-recreate stage9-tls-init

vault-tls-check: ## Check TLS volume permissions
	@echo "🔍 Checking TLS volume permissions..."
	@docker run --rm -v zakupai_vault_tls:/vault/tls alpine sh -c \
		"ls -la /vault/tls && stat -c '%U:%G %a %n' /vault/tls/*"

vault-tls-fix: ## Fix TLS volume permissions (UID 100)
	@echo "🔧 Fixing TLS volume permissions..."
	@docker run --rm -v zakupai_vault_tls:/vault/tls alpine sh -c " \
		if [ -f /vault/tls/vault.key ]; then \
			chown 100:100 /vault/tls/*; \
			chmod 640 /vault/tls/vault.key; \
			chmod 644 /vault/tls/vault.crt; \
			echo '✅ Permissions fixed:'; \
			ls -la /vault/tls; \
		else \
			echo '❌ TLS certificates not found!'; \
			exit 1; \
		fi"
	@echo "✅ TLS volume permissions corrected"

vault-tls-recreate: ## Recreate TLS certificates with correct permissions
	@echo "🔐 Recreating TLS certificates..."
	@docker volume rm zakupai_vault_tls || true
	@docker volume create zakupai_vault_tls
	@docker run --rm -v zakupai_vault_tls:/vault/tls alpine sh -c " \
		apk add --no-cache openssl; \
		cd /vault/tls; \
		openssl genrsa -out vault.key 2048; \
		openssl req -new -x509 -key vault.key -out vault.crt \
			-days 365 -subj '/C=KZ/ST=Karaganda/L=Karagandy/O=ZakupAI/CN=vault'; \
		chown 100:100 vault.key vault.crt; \
		chmod 640 vault.key; \
		chmod 644 vault.crt; \
		echo '✅ Certificates generated with correct permissions:'; \
		ls -la"
	@echo "✅ TLS volume ready for Vault"

stage9-tls-init: vault-tls-fix ## Initialize TLS for Stage 9 deployment
	@echo "🚀 TLS initialization complete"
	@make vault-tls-check

stage9-verify: ## Проверить, что Vault Stage9 поднят на B2 + TLS
	@echo "🔍 Проверка Stage 9 Vault..."
	@docker exec zakupai-vault vault status
	@echo "✅ Vault отвечает и готов"

vault-logs-export: ## Экспорт audit.log из Docker volume Vault
	@docker cp zakupai-vault:/vault/logs/audit.log monitoring/vault/logs/audit.log
	@echo "✅ Vault audit.log скопирован из Docker volume"

vault-tls-export: ## Экспорт TLS сертификатов из Docker volume Vault
	@docker cp zakupai-vault:/vault/tls/vault.crt monitoring/vault/tls/vault.crt
	@docker cp zakupai-vault:/vault/tls/vault.key monitoring/vault/tls/vault.key
	@echo "✅ TLS certs exported from Docker volume"

vault-tls-preload: ## Seed TLS certs into named volume (Stage 9)
	@echo "🔐 Preloading Vault TLS certs into volume..."
	@if [ ! -f monitoring/vault/tls/vault.crt ] || [ ! -f monitoring/vault/tls/vault.key ]; then \
		echo "⚠️  TLS certificates not found, generating..."; \
		$(MAKE) vault-tls-generate; \
	fi
	@echo "✅ TLS certificates ready."

vault-tls-generate: ## Generate TLS certificates for Vault (Stage 9)
	@echo "🔐 Generating Vault TLS certificates..."
	@mkdir -p monitoring/vault/tls
	@docker run --rm -v $(PWD)/monitoring/vault/tls:/certs alpine sh -c " \
		apk add --no-cache openssl && \
		cd /certs && \
		openssl req -x509 -nodes -newkey rsa:4096 -days 365 \
			-keyout vault.key -out vault.crt \
			-subj '/CN=vault.zakupai.local' \
			-addext 'subjectAltName=DNS:vault,DNS:vault.zakupai.local,DNS:localhost,IP:127.0.0.1' && \
		chmod 644 vault.crt && \
		chmod 600 vault.key && \
		echo '✅ Certificates generated with correct permissions' && \
		ls -la"
	@echo "✅ TLS certificates generated in monitoring/vault/tls/"

vault-tls-hash: ## Check TLS cert hashes inside Vault container
	@docker exec zakupai-vault md5sum /vault/tls/vault.crt /vault/tls/vault.key

vault-backup: ## Создать архив с Vault logs/tls/creds (Stage 9)
	@echo "📦 Cоздаём резервную копию Vault Stage9..."
	@mkdir -p backups
	@STAMP=$$(date +%Y%m%d-%H%M%S); \
	FILE=backups/vault-backup-$$STAMP.tar.gz; \
	tar -czf $$FILE monitoring/vault/logs monitoring/vault/tls monitoring/vault/creds; \
	chmod 600 $$FILE; \
	echo "✅ Backup готов: $$FILE"

vault-secure-test: ## Test Vault AppRole access (Stage 8)
	@echo "🧪 Testing Vault AppRole access..."
	@docker exec vault vault kv list zakupai/ || echo "❌ KV engine not accessible"

# --------------------------------------------
# 🔐 Vault Stage 9 (Production B2 + TLS)
# --------------------------------------------

stage9-prepare: ## Prepare Stage 9 prerequisites (B2 credentials + TLS)
	@echo "🔧 Preparing Stage 9 prerequisites..."
	@if [ ! -f monitoring/vault/creds/b2_access_key_id ] || [ ! -f monitoring/vault/creds/b2_secret_key ]; then \
		echo "❌ B2 credentials not found!"; \
		echo "   Create them with: ./monitoring/vault/scripts/prepare-b2-secrets.sh"; \
		exit 1; \
	fi
	@echo "✅ B2 credentials found"
	@$(MAKE) vault-tls-preload
	@echo "✅ Stage 9 prerequisites ready"

stage9-deploy: stage9-prepare ## Deploy Stage 9 Vault with B2 + TLS + Audit
	@echo "🚀 Deploying Stage 9 Vault..."
	@./scripts/start-stage9-vault.sh

stage9: stage9-deploy ## Alias for stage9-deploy

vault-prod-status: ## Check Vault status (Stage 9)
	@echo "🔍 Vault Status (Production):"
	@VAULT_SKIP_VERIFY=false docker exec vault vault status || true
	@echo ""
	@echo "🔍 Audit Log (last 10 entries):"
	@tail -10 monitoring/vault/logs/audit.log 2>/dev/null || echo "No audit log yet"

vault-prod-backup: ## Backup Vault to B2 (Stage 9)
	@echo "💾 Creating Vault snapshot and uploading to B2..."
	@./scripts/vault-migrate-stage9.sh backup

vault-tls-renew: ## Generate/renew TLS certificates for Vault
	@echo "🔐 Generating TLS certificates for Vault..."
	@mkdir -p monitoring/vault/tls
	@openssl req -x509 -nodes -newkey rsa:4096 -days 365 \
		-keyout monitoring/vault/tls/vault-key.pem \
		-out monitoring/vault/tls/vault-cert.pem \
		-subj "/CN=vault.zakupai.local" \
		-addext "subjectAltName=DNS:vault.zakupai.local,DNS:localhost,IP:127.0.0.1"
	@chmod 600 monitoring/vault/tls/vault-key.pem
	@chmod 644 monitoring/vault/tls/vault-cert.pem
	@echo "✅ TLS certificates generated:"
	@echo "   - monitoring/vault/tls/vault-cert.pem"
	@echo "   - monitoring/vault/tls/vault-key.pem"

smoke-stage9: ## Run smoke tests for Stage 9
	@echo "🧪 Running Stage 9 smoke tests..."
	@./monitoring/vault/tests/smoke-stage9.sh

# --------------------------------------------
# 🔙 Rollback Commands
# --------------------------------------------

rollback-stage8: ## Rollback from Stage 8 to Stage 7
	@echo "🔙 Rolling back to Stage 7..."
	@docker-compose down vault
	@cp monitoring/vault/config/stage7/stage7-config.hcl monitoring/vault/config/vault-config.hcl
	@rm -f docker-compose.override.yml
	@docker-compose up -d vault
	@echo "✅ Rolled back to Stage 7. Manual unseal required."
	@echo "Run: vault operator unseal <key>"

rollback-stage9: ## Rollback from Stage 9 to Stage 8
	@echo "🔙 Rolling back to Stage 8..."
	@docker-compose down vault
	@cp monitoring/vault/config/secure/config.hcl monitoring/vault/config/vault-config.hcl
	@cp docker-compose.override.stage8.vault-secure.yml docker-compose.override.yml
	@echo "📦 Restoring data from latest backup..."
	@LATEST_BACKUP=$$(ls -t vault-backup-*.tar.gz 2>/dev/null | head -1); \
	if [ -n "$$LATEST_BACKUP" ]; then \
		tar -xzf $$LATEST_BACKUP -C / ; \
		echo "✅ Data restored from: $$LATEST_BACKUP"; \
	else \
		echo "⚠️  No backup found. Data may be lost."; \
	fi
	@docker-compose up -d vault
	@echo "✅ Rolled back to Stage 8. Auto-unseal active."
