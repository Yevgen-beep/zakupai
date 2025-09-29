#!/bin/bash
# stage6-migrations.sh - Автоматическое выполнение миграций для всех сервисов Stage6
set -e

COMPOSE_CMD="docker compose -f docker-compose.yml -f docker-compose.override.stage6.yml --profile stage6"
SERVICES=("billing" "calc" "doc" "embedding" "etl" "risk")

# Функция для получения правильного имени runner-а
runner_name_for() {
    local service=$1
    case "$service" in
        billing)    echo "migration-runner-billing-service" ;;
        calc)       echo "migration-runner-calc-service" ;;
        doc)        echo "migration-runner-doc-service" ;;
        embedding)  echo "migration-runner-embedding-api" ;;
        etl)        echo "migration-runner-etl-service" ;;
        risk)       echo "migration-runner-risk-engine" ;;
        *)          echo "migration-runner-${service}" ;;
    esac
}

# Функция для проверки наличия миграций в сервисе
has_migrations() {
    local service=$1
    local service_dir="services/${service}-service"

    # Особый случай для embedding-api
    if [[ "$service" == "embedding" ]]; then
        service_dir="services/embedding-api"
    fi

    if [[ -f "${service_dir}/alembic/env.py" ]]; then
        return 0  # есть миграции
    else
        return 1  # нет миграции
    fi
}

echo "🚀 Stage6 Migrations Automation Script"
echo "======================================"
echo

# Функция для выполнения команд Alembic в контейнере
run_alembic() {
    local service=$1
    local cmd=$2
    local runner_name=$(runner_name_for "$service")
    local service_upper="${service^^}"

    if ! has_migrations "$service"; then
        local service_dir="services/${service}-service"
        if [[ "$service" == "embedding" ]]; then
            service_dir="services/embedding-api"
        fi
        echo "⏭️  ${service_upper} Service - SKIPPING (no alembic/ folder found)"
        echo "----------------------------------------"
        echo "   No alembic/ folder found in ${service_dir}/"
        echo
        return 0
    fi

    echo "📦 ${service_upper} Service - Using runner: ${runner_name}"
    echo "📦 ${service_upper} Service - Running: alembic ${cmd}"
    echo "----------------------------------------"

    # Smoke test: проверка доступности базы данных
    echo "🏥 Database connectivity test..."
    $COMPOSE_CMD run --rm ${runner_name} sh -c "ping -c1 zakupai-db" || {
        echo "❌ Cannot reach zakupai-db from ${runner_name}"
        echo "   Check network configuration and DB service status"
        return 1
    }
    echo "✅ zakupai-db is reachable"

    if [[ "$cmd" == *"--sql"* ]]; then
        echo "🔍 DRY-RUN mode - SQL preview:"
        echo
    fi

    $COMPOSE_CMD run --rm ${runner_name} sh -c "alembic ${cmd}" || {
        echo "❌ Failed to run alembic ${cmd} for ${service}"
        return 1
    }

    echo
}

echo "🔍 Phase 1: Checking current migration status"
echo "============================================="

for service in "${SERVICES[@]}"; do
    run_alembic "$service" "current"
done

echo "🧪 Phase 2: Dry-run migrations (SQL preview)"
echo "============================================"

for service in "${SERVICES[@]}"; do
    run_alembic "$service" "upgrade head --sql"
done

echo "⚠️  IMPORTANT: Review the SQL above before proceeding!"
echo "======================================================"
read -p "Continue with actual migration execution? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ Migration execution cancelled by user"
    exit 0
fi

echo
echo "🚀 Phase 3: Executing migrations"
echo "==============================="

for service in "${SERVICES[@]}"; do
    run_alembic "$service" "upgrade head"
done

echo "✅ Phase 4: Verifying final migration status"
echo "==========================================="

for service in "${SERVICES[@]}"; do
    run_alembic "$service" "current"
done

echo
echo "🎉 All Stage6 migrations completed successfully!"
echo "==============================================="
echo "Summary:"
echo "- Checked initial status for ${#SERVICES[@]} services"
echo "- Performed dry-run SQL preview"
echo "- Executed migrations with user confirmation"
echo "- Verified final status"
echo
echo "💡 Next steps:"
echo "- Start Stage6 services: make stage6-up"
echo "- Run smoke tests: make stage6-smoke"
echo "- Check logs: make stage6-logs"
