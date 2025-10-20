#!/usr/bin/env bash
# Synthetic traffic generator for Stage6 FastAPI services
# Warms up metrics by hitting /health and sample API endpoints

set -euo pipefail

if ! command -v curl >/dev/null 2>&1; then
  echo "Error: curl not found" >&2
  exit 1
fi

# Service endpoints (host:port)
declare -A services=(
  ["calc-service"]="localhost:8100"
  ["risk-engine"]="localhost:8200"
  ["doc-service"]="localhost:8300"
  ["embedding-api"]="localhost:8400"
  ["etl-service"]="localhost:8500"
  ["billing-service"]="localhost:8600"
  ["goszakup-api"]="localhost:8700"
  ["web-ui"]="localhost:8800"
)

echo "🔥 Starting synthetic traffic warmup for Stage6 services..."
echo "⏱️  Duration: 30 seconds of continuous requests"
echo ""

start_time=$(date +%s)
end_time=$((start_time + 30))
request_count=0
success_count=0
error_count=0

while [ $(date +%s) -lt $end_time ]; do
  for svc_name in "${!services[@]}"; do
    endpoint="${services[$svc_name]}"

    # Health check (always)
    if curl -s -o /dev/null -w "%{http_code}" --max-time 2 "http://${endpoint}/health" | grep -q "^2"; then
      ((success_count++))
    else
      ((error_count++))
    fi
    ((request_count++))

    # Sample API endpoint (some services may 404, that's OK - still generates metrics)
    case "$svc_name" in
      calc-service)
        curl -s -o /dev/null --max-time 2 -X POST "http://${endpoint}/api/v1/calculate" \
          -H "Content-Type: application/json" \
          -d '{"items":[],"method":"FIFO"}' 2>/dev/null || true
        ;;
      risk-engine)
        curl -s -o /dev/null --max-time 2 "http://${endpoint}/api/v1/analyze/000000000000" 2>/dev/null || true
        ;;
      doc-service)
        curl -s -o /dev/null --max-time 2 "http://${endpoint}/api/v1/documents?limit=1" 2>/dev/null || true
        ;;
      goszakup-api)
        curl -s -o /dev/null --max-time 2 "http://${endpoint}/api/v1/ping" 2>/dev/null || true
        ;;
      *)
        # Generic GET to root or /api/v1
        curl -s -o /dev/null --max-time 2 "http://${endpoint}/api/v1" 2>/dev/null || true
        ;;
    esac
    ((request_count++))
  done

  # Brief pause between rounds
  sleep 0.5
done

elapsed=$(($(date +%s) - start_time))
echo ""
echo "✅ Warmup complete!"
echo "   Total requests: $request_count"
echo "   Successful /health: $success_count"
echo "   Failed /health: $error_count"
echo "   Duration: ${elapsed}s"
echo ""
echo "🔍 Verify metrics at:"
echo "   - Prometheus: http://localhost:9095/graph?g0.expr=rate(http_requests_total[1m])"
echo "   - Grafana: http://localhost:3030/d/zakupai-overview"
