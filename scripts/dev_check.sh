#!/usr/bin/env bash
set -e
for p in 8001 8002 8003 8004; do
  echo ">>> :$p"; curl -s http://localhost:$p/health || true; echo
done
