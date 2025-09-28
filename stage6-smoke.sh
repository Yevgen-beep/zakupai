#!/usr/bin/env bash
set -e

echo "=== 🔍 Stage6 Smoke Test: ZakupAI ядро + мониторинг ==="

# ---------- Проверка ядра ----------
echo "[1] Gateway health"
curl -sf http://localhost:8080/health && echo "✅ Gateway OK" || echo "❌ Gateway DOWN"

echo "[2] Сервисы через gateway"
for svc in calc risk doc emb etl; do
  echo -n " - $svc: "
  curl -sf http://localhost:8080/$svc/health && echo "✅" || echo "❌"
done

echo "[3] ETL upload PDF"
curl -s -o /dev/null -w "%{http_code}" -X POST \
  -F "file=@./web/test_fixtures/scan1.pdf" \
  http://localhost:8080/etl/upload || echo "❌ ETL upload failed"

echo "[4] Поиск лотов"
curl -s "http://localhost:8080/lots?query=лак" | jq '.'

# ---------- Проверка мониторинга ----------
echo "[5] Prometheus health"
curl -sf http://localhost:9090/-/healthy && echo "✅ Prometheus OK" || echo "❌ Prometheus DOWN"

echo "[6] Alertmanager health"
curl -sf http://localhost:9093/-/healthy && echo "✅ Alertmanager OK" || echo "❌ Alertmanager DOWN"

echo "[7] Node Exporter metrics"
curl -sf http://localhost:19101/metrics | head -10 || echo "❌ Node Exporter DOWN"

echo "[8] Grafana login page"
curl -s -o /dev/null -w "%{http_code}" http://localhost:3001/login || echo "❌ Grafana DOWN"

echo "=== ✅ Stage6 Smoke Test завершён ==="
