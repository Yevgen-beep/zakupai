#!/usr/bin/env bash
set -euo pipefail

echo "=== 🧩 ZakupAI Stage6 Dashboard & Metrics Auto-Fix v3.1 ==="

# Paths
BOT_MAIN="bot/main.py"
DASHBOARD_PATH="monitoring/grafana/provisioning/dashboards/overview/zakupai-overview.json"
BACKUP_SUFFIX=".bak_$(date +%Y%m%d_%H%M%S)"

# Colors
RED=$(tput setaf 1)
GREEN=$(tput setaf 2)
YELLOW=$(tput setaf 3)
RESET=$(tput sgr0)

# 1️⃣ Backup key files
echo "[1] Backing up key configs..."
cp "$BOT_MAIN" "$BOT_MAIN$BACKUP_SUFFIX"
cp "$DASHBOARD_PATH" "$DASHBOARD_PATH$BACKUP_SUFFIX"

# 2️⃣ Ensure node-exporter container is up
echo "[2] Checking node-exporter container..."
if ! docker ps --format '{{.Names}}' | grep -q "node-exporter"; then
  echo "⚙️  Starting node-exporter..."
  docker compose up -d node-exporter-stage6 || docker compose up -d node-exporter
else
  echo "✅ node-exporter already running."
fi

# 3️⃣ Patch zakupai-bot main.py for ProcessCollector / PlatformCollector
echo "[3] Ensuring zakupai-bot exports process metrics..."
if ! grep -q "ProcessCollector" "$BOT_MAIN"; then
  sed -i '/start_http_server(METRICS_PORT)/a \
ProcessCollector()  # adds process_* metrics\nPlatformCollector() # adds platform_* metrics (CPU, mem, etc.)' "$BOT_MAIN"
  echo "✅ Added ProcessCollector & PlatformCollector to $BOT_MAIN"
else
  echo "✅ Bot already exports process metrics."
fi

# 4️⃣ Rebuild zakupai-bot container (showing logs)
echo "[4] Rebuilding zakupai-bot container (this may take a minute)..."
if ! docker compose up -d --build zakupai-bot; then
  echo "${RED}❌ zakupai-bot rebuild failed.${RESET}"
  echo "➡️  Showing last 40 lines of the build log:"
  docker compose logs --tail=40 zakupai-bot || true
  echo "⚠️  Please fix the error (likely in requirements.txt or Dockerfile) and rerun this script."
  exit 1
fi
sleep 5
echo "✅ zakupai-bot rebuild complete."

# 5️⃣ Fix 5xx Error Rate panel to show zeros when empty
echo "[5] Updating 5xx Error Rate panel expression..."
if grep -q "5xx Error Rate" "$DASHBOARD_PATH"; then
  sed -i 's/sum(irate(api_error_ratio_by_service\[5m\]))/sum(irate(api_error_ratio_by_service\[5m\])) or vector(0)/g' "$DASHBOARD_PATH"
  echo "✅ 5xx Error Rate panel patched to show 0 instead of empty."
else
  echo "⚠️  5xx Error Rate panel not found — skipping."
fi

# 6️⃣ Restart Grafana for dashboard reload
echo "[6] Restarting Grafana..."
docker compose restart grafana || {
  echo "${YELLOW}⚠️  Could not restart Grafana automatically. Please restart manually if needed.${RESET}"
}
sleep 10

# 7️⃣ Verify node-exporter job visibility in Prometheus
echo "[7] Checking node-exporter job in Prometheus..."
NODE_STATUS=$(curl -s http://localhost:9090/api/v1/targets \
  | jq -r '.data.activeTargets[] | select(.labels.job | contains("node-exporter")) | "\(.labels.job): \(.health)"' || true)

if [[ -n "$NODE_STATUS" ]]; then
  echo "${GREEN}✅ Node Exporter target found:${RESET}"
  echo "$NODE_STATUS"
else
  echo "${YELLOW}⚠️  Node Exporter job not visible in Prometheus.${RESET}"
  echo "   → Check prometheus.yml scrape_configs or container name."
fi

# 8️⃣ Verify zakupai-bot metrics
echo "[8] Checking zakupai-bot metrics..."
if curl -s http://localhost:8081/metrics | grep -q "process_cpu_seconds_total"; then
  echo "${GREEN}✅ zakupai-bot exports process metrics.${RESET}"
else
  echo "${YELLOW}⚠️ zakupai-bot process metrics not detected. Check logs:${RESET}"
  docker logs --tail=20 zakupai-bot || true
fi

# 9️⃣ Final summary
echo ""
echo "✅ ${GREEN}Stage6 Dashboard & Metrics Fix v3.1 complete!${RESET}"
echo "Backups saved as:"
echo "  $BOT_MAIN$BACKUP_SUFFIX"
echo "  $DASHBOARD_PATH$BACKUP_SUFFIX"
echo ""
echo "💡 Now open Grafana → http://localhost:3030/d/zakupai-overview"
echo "   and verify Node & Bot panels — they should display data within ~1–2 minutes."

