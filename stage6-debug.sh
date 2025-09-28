#!/bin/bash
echo "=== 🐳 Stage6 Debug Report ==="

echo -e "\n[1] 📋 Контейнеры ZakupAI:"
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep zakupai-

echo -e "\n[2] 🌐 Gateway:"
docker logs zakupai-gateway --tail=50 2>&1 | sed 's/^/  /'

echo -e "\n[3] 🔢 Calc-service:"
docker logs zakupai-calc-service --tail=50 2>&1 | sed 's/^/  /'

echo -e "\n[4] ⚖️ Risk-engine:"
docker logs zakupai-risk-engine --tail=50 2>&1 | sed 's/^/  /'

echo -e "\n[5] 📄 Doc-service:"
docker logs zakupai-doc-service --tail=50 2>&1 | sed 's/^/  /'

echo -e "\n[6] 🧩 Embedding-API:"
docker logs zakupai-embedding-api --tail=50 2>&1 | sed 's/^/  /'

echo -e "\n[7] 📥 ETL-service:"
docker logs zakupai-etl-service --tail=50 2>&1 | sed 's/^/  /'

echo -e "\n--- 🔍 Мониторинг ---"

echo -e "\n[8] 📈 Prometheus:"
docker logs zakupai-prometheus --tail=30 2>&1 | sed 's/^/  /'

echo -e "\n[9] 📊 Grafana:"
docker logs zakupai-grafana --tail=30 2>&1 | sed 's/^/  /'

echo -e "\n[10] 🚨 Alertmanager:"
docker logs zakupai-alertmanager --tail=30 2>&1 | sed 's/^/  /'

echo -e "\n[11] 📦 Loki:"
docker logs zakupai-loki --tail=30 2>&1 | sed 's/^/  /'

echo -e "\n[12] 🔒 Vault:"
docker logs zakupai-vault --tail=30 2>&1 | sed 's/^/  /'

echo -e "\n=== ✅ Конец Stage6 Debug Report ==="
