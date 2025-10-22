#!/usr/bin/env bash
# ===========================================================
# 🧪 ZakupAI Sequential Test Pipeline
# Запускает тесты по всем сервисам в логическом порядке.
# ===========================================================

set -euo pipefail
mkdir -p logs/tests
LOG_FILE="logs/tests/pipeline.log"
echo "🧪 ZakupAI Test Pipeline started at $(date)" > "$LOG_FILE"
echo "===================================================" >> "$LOG_FILE"

# -------- функции ----------
run_test() {
    local SERVICE="$1"
    echo "-----------------------------------------------------------------" | tee -a "$LOG_FILE"
    echo "🔍 Testing ${SERVICE} ..." | tee -a "$LOG_FILE"
    local START=$(date +%s)
    if pytest "services/${SERVICE}/tests/" -q --tb=short > "logs/tests/${SERVICE}.log" 2>&1; then
        local DURATION=$(( $(date +%s) - START ))
        echo "✅ ${SERVICE} - OK (${DURATION}s)" | tee -a "$LOG_FILE"
    else
        local DURATION=$(( $(date +%s) - START ))
        echo "❌ ${SERVICE} - FAILED (${DURATION}s)" | tee -a "$LOG_FILE"
        echo "─── LOG SNIPPET ───" >> "$LOG_FILE"
        tail -n 10 "logs/tests/${SERVICE}.log" | tee -a "$LOG_FILE"
        echo "────────────────────" >> "$LOG_FILE"
        # 🔴 можно снять комментарий, чтобы прерывать на первой ошибке:
        # exit 1
    fi
}

# -------- порядок запуска ----------
echo "🧩 1️⃣ calc-service (baseline)" | tee -a "$LOG_FILE"
run_test "calc-service"

echo "🧩 2️⃣ billing-service" | tee -a "$LOG_FILE"
run_test "billing-service"

echo "🧩 3️⃣ doc-service" | tee -a "$LOG_FILE"
run_test "doc-service"

echo "🧩 4️⃣ etl-service" | tee -a "$LOG_FILE"
run_test "etl-service"

echo "🧩 5️⃣ embedding-api" | tee -a "$LOG_FILE"
run_test "embedding-api"

echo "🧩 6️⃣ risk-engine" | tee -a "$LOG_FILE"
run_test "risk-engine"

# -------- итог ----------
echo "===================================================" | tee -a "$LOG_FILE"
echo "🏁 All tests completed at $(date)" | tee -a "$LOG_FILE"
echo "📊 Summary saved to: $LOG_FILE"
