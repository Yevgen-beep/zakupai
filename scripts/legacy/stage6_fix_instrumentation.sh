#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

SERVICES=(
  calc-service
  risk-engine
  doc-service
  embedding-api
  etl-service
  billing-service
  goszakup-api
  gateway
)

ensure_tooling() {
  local tools=(python3 docker jq curl)
  for tool in "${tools[@]}"; do
    if ! command -v "$tool" >/dev/null 2>&1; then
      echo "❌ Required tool '$tool' is not installed or not in PATH."
      exit 1
    fi
  done
}

add_instrumentator_snippet() {
  local service="$1"
  local main_py="services/${service}/main.py"
  local req_file="services/${service}/requirements.txt"
  local import_stmt="from prometheus_fastapi_instrumentator import Instrumentator"
  local req_entry="prometheus-fastapi-instrumentator>=6.1.0"

  echo "→ Updating ${main_py}"
  python3 - "$service" <<'PY'
import sys
from pathlib import Path

service = sys.argv[1]
path = Path(f"services/{service}/main.py")
text = path.read_text()
import_stmt = "from prometheus_fastapi_instrumentator import Instrumentator"
instrument_snippet = [
    "",
    "instrumentator = Instrumentator(",
    "    should_group_status_codes=False,",
    '    excluded_handlers=["/metrics", "/health"],',
    ")",
    "instrumentator.instrument(app)",
    "",
]

if import_stmt not in text:
    lines = text.splitlines()
    inserted_import = False
    for idx, line in enumerate(lines):
        if line.startswith("from prometheus_client import"):
            lines.insert(idx + 1, import_stmt)
            inserted_import = True
            break
    if not inserted_import:
        for idx, line in enumerate(lines):
            if line.startswith("import ") or line.startswith("from "):
                continue
            lines.insert(idx, import_stmt)
            inserted_import = True
            break
    if not inserted_import:
        lines.insert(0, import_stmt)
else:
    lines = text.splitlines()

target = "add_prometheus_middleware(app, SERVICE_NAME)"
snippet_present = any("Instrumentator(" in line for line in lines)
if not snippet_present:
    for idx, line in enumerate(lines):
        if target in line:
            insert_idx = idx + 1
            while insert_idx < len(lines) and not lines[insert_idx].strip():
                insert_idx += 1
            lines[insert_idx:insert_idx] = instrument_snippet
            break

path.write_text("\n".join(lines) + "\n")
PY

  echo "→ Ensuring dependency in ${req_file}"
  python3 - "$service" <<'PY'
import sys
from pathlib import Path

service = sys.argv[1]
req_path = Path(f"services/{service}/requirements.txt")
entry = "prometheus-fastapi-instrumentator>=6.1.0"
lines = [line.rstrip("\n") for line in req_path.read_text().splitlines()]
if not any(line.strip().startswith("prometheus-fastapi-instrumentator") for line in lines):
    lines.append(entry)
req_path.write_text("\n".join(lines) + "\n")
PY
}

wait_for_services() {
  local max_attempts=30
  local delay=10
  for ((attempt=1; attempt<=max_attempts; attempt++)); do
    local json
    if ! json="$(docker compose ps --format json 2>/dev/null)"; then
      echo "⚠️  Unable to read docker compose status. Retrying..."
      sleep "$delay"
      continue
    fi
    local unhealthy
    unhealthy="$(echo "$json" | jq '[.[] | select((.State|test("running")==false) or (.Health != "" and .Health != "healthy"))] | length')"
    if [[ "$unhealthy" == "0" ]]; then
      echo "✅ All services are running/healthy."
      return 0
    fi
    echo "⏳ Waiting for services to become healthy (attempt ${attempt}/${max_attempts})..."
    sleep "$delay"
  done

  echo "❌ Services did not become healthy in time."
  docker compose ps
  return 1
}

run_validations() {
  echo "→ Querying Prometheus for http_requests_total series count..."
  local metrics_count
  metrics_count="$(curl -s http://localhost:9095/api/v1/query?query=http_requests_total | jq '.data.result | length')"
  echo "   http_requests_total series: ${metrics_count}"

  echo "→ Listing Prometheus target health..."
  curl -s http://localhost:9095/api/v1/targets | jq '.data.activeTargets[] | {job: .labels.job, health: .health}'

  echo "→ Checking Grafana health endpoint..."
  curl -s http://localhost:3030/api/health || true

  echo ""
  if [[ "${metrics_count}" != "0" ]]; then
    echo "Grafana dashboards populated ✅"
  else
    echo "⚠️  Metrics still missing—check Prometheus query and dashboards."
  fi
}

main() {
  ensure_tooling

  echo "### Updating FastAPI instrumentation ###"
  for service in "${SERVICES[@]}"; do
    add_instrumentator_snippet "$service"
  done

  echo ""
  echo "### Rebuilding targeted services ###"
  docker compose build "${SERVICES[@]}"

  echo ""
  echo "### Restarting Stage6 stack ###"
  docker compose up -d

  echo ""
  echo "### Waiting for services to become healthy ###"
  wait_for_services

  echo ""
  echo "### Generating synthetic traffic ###"
  ./scripts/traffic-gen.sh

  echo ""
  echo "### Validating Prometheus & Grafana ###"
  run_validations
}

main "$@"
