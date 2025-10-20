#!/usr/bin/env bash
set -euo pipefail

echo "=== 🧩 ZakupAI Stage6 Visualization Auto-Fix ==="
echo "[1] Checking running containers..."
docker ps --format "table {{.Names}}\t{{.Status}}" | grep zakupai || true

echo
echo "[2] Generating continuous traffic for 90 seconds..."
./stage6-continuous-traffic.sh &
TRAFFIC_PID=$!
for i in {1..9}; do
  printf "   • cycle %d/9...\n" "$i"
  sleep 10
done
kill $TRAFFIC_PID >/dev/null 2>&1 || true
echo "✅ Traffic generation complete."

echo
echo "[3] Restarting Prometheus and Grafana..."
docker compose \
  -f docker-compose.yml \
  -f docker-compose.override.stage6.yml \
  -f docker-compose.override.stage6.monitoring.yml \
  restart prometheus grafana >/dev/null

echo "⏳ Waiting 45s for scrape cycles..."
sleep 45

echo
echo "[4] Checking Prometheus targets..."
TARGETS=$(curl -s http://localhost:9095/api/v1/targets | jq '.data.activeTargets | length')
echo "Active targets: ${TARGETS}"

echo
echo "[5] Verifying http_requests_total metrics..."
REQS=$(curl -s 'http://localhost:9095/api/v1/query?query=sum(http_requests_total)by(job)' | jq '.data.result | length')
if [[ "$REQS" -gt 0 ]]; then
  echo "✅ Found ${REQS} metric series for http_requests_total"
else
  echo "❌ Still no metrics — check FastAPI endpoints or /metrics exposure."
fi

echo
echo "[6] Checking instantaneous request rates (irate)..."
IRATE_OUTPUT=$(curl -s 'http://localhost:9095/api/v1/query?query=sum(irate(http_requests_total[2m]))by(job)' | jq -r '.data.result[]? | "\(.metric.job): \(.value[1]) req/s"')
if [[ -z "$IRATE_OUTPUT" ]]; then
  echo "⚠️  No irate data yet (Prometheus needs at least 2 scrape cycles with delta)."
else
  echo "$IRATE_OUTPUT"
fi

echo
echo "[7] Checking Grafana datasource..."
curl -s -u admin:admin http://localhost:3030/api/datasources | jq '.[] | select(.name=="Prometheus") | {name, url, isDefault}'

echo
echo "[8] Final step — open Grafana dashboard"
echo "   → http://localhost:3030/d/zakupai-overview"
echo
echo "🎯 Expected after 60–90 seconds:"
echo "   - All service panels: green"
echo "   - Availability ≈ 100%"
echo "   - Error ratio = 0%"
echo
echo "=== ✅ Stage6 Visualization Auto-Fix Completed ==="
