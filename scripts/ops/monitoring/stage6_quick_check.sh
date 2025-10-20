#!/bin/bash
# ZakupAI Stage6 Monitoring Quick Health Check
# Usage: bash stage6_quick_check.sh

echo "=== ZakupAI Stage6 Monitoring Health Check ==="
echo ""

echo "🔍 Checking Container Status..."
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep -E "(prometheus|grafana|alertmanager|bot)" | head -10
echo ""

echo "🔍 Checking Prometheus..."
PROM_READY=$(curl -s http://localhost:9090/-/ready 2>&1)
if [[ "$PROM_READY" == *"Ready"* ]]; then
  echo "✅ Prometheus: Ready (http://localhost:9090)"
else
  echo "❌ Prometheus: Not Ready"
fi
echo ""

echo "🔍 Checking Grafana..."
GRAFANA_HEALTH=$(curl -s http://localhost:3030/api/health 2>&1 | jq -r '.database // "error"')
if [[ "$GRAFANA_HEALTH" == "ok" ]]; then
  echo "✅ Grafana: Healthy (http://localhost:3030)"
else
  echo "❌ Grafana: Not Healthy"
fi
echo ""

echo "🔍 Checking Prometheus Targets..."
TARGET_COUNT=$(curl -s http://localhost:9090/api/v1/targets 2>&1 | jq '.data.activeTargets | length' 2>/dev/null)
if [ "$TARGET_COUNT" -ge 15 ]; then
  echo "✅ Prometheus Targets: $TARGET_COUNT active"
else
  echo "⚠️  Prometheus Targets: $TARGET_COUNT active (expected 16)"
fi
echo ""

echo "🔍 Checking zakupai-bot..."
BOT_UP=$(curl -s 'http://localhost:9090/api/v1/query?query=zakupai_bot_up' 2>&1 | jq -r '.data.result[0].value[1] // "0"' 2>/dev/null)
if [ "$BOT_UP" == "1" ]; then
  echo "✅ zakupai-bot: UP and exporting metrics"
else
  echo "❌ zakupai-bot: DOWN or not exporting metrics"
fi
echo ""

echo "🔍 Checking for port conflicts..."
SYSTEM_PROM=$(ps aux | grep -E "/usr/bin/prometheus$" | grep -v grep | wc -l)
if [ "$SYSTEM_PROM" -eq 0 ]; then
  echo "✅ System Prometheus: Not running (no conflicts)"
else
  echo "⚠️  System Prometheus: Running and may conflict on port 9090"
fi
echo ""

echo "✅ Health check complete!"
