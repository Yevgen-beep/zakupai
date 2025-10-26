#!/usr/bin/env bash
# Continuous traffic generator for Stage6 monitoring validation
# Runs indefinitely, hit Ctrl+C to stop

ports=(7001 7002 7003 7004 7005 7010 7011)

echo "🔥 Starting continuous traffic to Stage6 services..."
echo "⏱️  Interval: 1 request/service every 2 seconds"
echo "Press Ctrl+C to stop"
echo ""

count=0
while true; do
  for port in "${ports[@]}"; do
    curl -s "http://localhost:$port/docs" >/dev/null 2>&1 &
  done
  ((count++))
  printf "\r✅ Batch #%d sent (total: %d requests)" "$count" "$((count * ${#ports[@]}))"
  sleep 2
done
