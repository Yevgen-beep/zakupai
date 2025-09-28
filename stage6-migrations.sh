#!/bin/bash
# stage6-migrations.sh - Автоматическое выполнение миграций для всех сервисов Stage6
set -e

COMPOSE_CMD="docker compose -f docker-compose.yml -f docker-compose.override.stage6.yml --profile stage6"
SERVICES=("billing" "calc" "doc" "embedding" "etl" "risk")

echo "🚀 Stage6 Migrations Automation Script"
echo "======================================"
echo

# Функция для выполнения команд Alembic в контейнере
run_alembic() {
    local service=$1
    local cmd=$2
    local runner_name="migration-runner-${service}"

    echo "📦 ${service^^} Service - Running: alembic ${cmd}"
    echo "----------------------------------------"

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
