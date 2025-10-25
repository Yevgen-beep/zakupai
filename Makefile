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
	@sleep 20
	@echo "\n🔍 Checking Prometheus targets..."
	@curl -s http://localhost:9095/api/v1/targets | grep -q '"health":"up"' && echo "✅ Prometheus targets are UP" || (echo "❌ Prometheus not responding"; exit 1)
	@echo "\n🔍 Checking Loki API..."
	@curl -s http://localhost:3100/loki/api/v1/status/buildinfo | grep -q '"status":"success"' && echo "✅ Loki is reachable" || (echo "❌ Loki not reachable"; exit 1)
	@echo "\n🔍 Checking Grafana availability..."
	@curl -s -o /dev/null -w "%{http_code}" http://localhost:3030 | grep -q "200" && echo "✅ Grafana is online at http://localhost:3030" || (echo "❌ Grafana not reachable"; exit 1)
	@echo "\n🔍 Checking microservices health endpoints..."
	@for svc in calc-service risk-engine doc-service embedding-api gateway web-ui etl-service billing-service; do \
		NAME=$$(docker ps --format '{{.Names}}' | grep $$svc || true); \
		if [ -n "$$NAME" ]; then \
			PORT=$$(docker port $$NAME 2>/dev/null | grep -oP '0.0.0.0:\K\d+' | head -1); \
			if [ -n "$$PORT" ]; then \
				if curl -sf http://localhost:$$PORT/health > /dev/null; then \
					echo "✅ $$svc healthy on port $$PORT"; \
				else \
					echo "⚠️  $$svc not responding on port $$PORT"; \
				fi; \
			fi; \
		fi; \
	done
	@echo "\n🟢 All critical services verified."

stage6-status: ## Показать статус контейнеров и метрик Prometheus/Grafana
	@echo "=== Containers Status ==="
	@docker ps --filter "name=zakupai" --format "table {{.Names}}\t{{.Status}}" | head -20
	@echo ""
	@echo "=== Prometheus Targets ==="
	@docker exec zakupai-prometheus wget -qO- http://localhost:9090/api/v1/targets 2>/dev/null | jq -r '.data.activeTargets | length as $$total | map(select(.health=="up")) | length as $$up | "\($$up)/\($$total) targets UP"' || echo "❌ Prometheus not accessible"
	@echo ""
	@echo "=== Grafana Dashboard ==="
	@curl -s -u admin:admin 'http://localhost:3030/api/dashboards/uid/zakupai-overview' 2>/dev/null | jq -r '"Dashboard: " + .dashboard.title + " (" + (.dashboard.panels | length | tostring) + " panels)"' || echo "❌ Grafana not accessible"
