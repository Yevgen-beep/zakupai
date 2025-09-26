#!/bin/bash
# ZakupAI Stage6 turnkey installer: observability stack + security gates
set -euo pipefail
IFS=$'\n\t'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

LOG_PREFIX="[stage6]"
LIBS_CONTEXT_PATH="/home/mint/projects/claude_sandbox/zakupai/libs"
COMPOSE_ARGS=(-f docker-compose.yml -f docker-compose.override.stage6.yml)
COMPOSE_CMD=()

export PATH="$HOME/.local/bin:$PATH"

log_info() { echo "${LOG_PREFIX} INFO: $1"; }
log_warn() { echo "${LOG_PREFIX} WARN: $1"; }
log_error() { echo "${LOG_PREFIX} ERROR: $1" >&2; }

on_err() {
  local exit_code=$?
  trap - ERR
  log_error "Command failed with exit code ${exit_code} at line $1."
  exit "$exit_code"
}
trap 'on_err $LINENO' ERR

abort() {
  trap - ERR
  log_error "$1"
  exit 1
}

ensure_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    abort "Required command '$1' is not available. Install it and re-run."
  fi
}

ensure_prereqs() {
  log_info "Validating required tools..."
  ensure_command python3
  ensure_command docker
  ensure_command curl
  ensure_command head
  ensure_command cmp
}

pip_install_packages() {
  local description="$1"
  shift
  local packages=("$@")
  local pip_opts=(--upgrade)
  local used_user=0

  if [[ -z "${VIRTUAL_ENV-}" ]]; then
    pip_opts+=(--user)
    used_user=1
  fi

  if ! python3 -m pip install "${pip_opts[@]}" "${packages[@]}"; then
    if [[ $used_user -eq 1 ]]; then
      log_warn "pip install with --user failed for ${description}; retrying without --user."
      python3 -m pip install --upgrade "${packages[@]}" || abort "Failed to install ${description} packages."
    else
      abort "Failed to install ${description} packages."
    fi
  fi
}

write_file() {
  local path="$1"
  local tmp
  tmp="$(mktemp)"
  cat >"$tmp"
  mkdir -p "$(dirname "$path")"
  if [ -f "$path" ] && cmp -s "$tmp" "$path"; then
    rm -f "$tmp"
    log_info "No changes needed for $path"
    return
  fi
  mv "$tmp" "$path"
  log_info "Wrote $path"
}

open_url() {
  local url="$1"
  if command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$url" >/dev/null 2>&1 || log_warn "Could not open $url via xdg-open."
  elif command -v open >/dev/null 2>&1; then
    open "$url" >/dev/null 2>&1 || log_warn "Could not open $url via open."
  else
    log_warn "No desktop opener detected. Visit ${url} manually if needed."
  fi
}

create_directories_and_files() {
  log_info "Creating monitoring directories and configuration files..."
  mkdir -p monitoring/grafana/provisioning/datasources

  write_file "docker-compose.override.stage6.yml" <<'EOF'
version: "3.9"

services:
  prometheus:
    image: prom/prometheus:v2.51.0
    container_name: zakupai-prometheus-stage6
    profiles:
      - stage6
    command:
      - --config.file=/etc/prometheus/prometheus.yml
      - --storage.tsdb.path=/prometheus
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - prometheus_data:/prometheus
    ports:
      - "9090:9090"
    healthcheck:
      test: ["CMD-SHELL", "wget --spider --quiet http://localhost:9090/-/ready || exit 1"]
      interval: 30s
      timeout: 10s
      retries: 5
    restart: unless-stopped
    networks:
      - zakupai-network

  node-exporter:
    image: prom/node-exporter:v1.7.0
    container_name: zakupai-node-exporter-stage6
    profiles:
      - stage6
    command:
      - --web.listen-address=:19100
      - --path.procfs=/host/proc
      - --path.sysfs=/host/sys
      - --collector.filesystem.mount-points-exclude=^/(sys|proc|dev|host|etc)($$|/)
    ports:
      - "19100:19100"
    volumes:
      - /proc:/host/proc:ro
      - /sys:/host/sys:ro
      - /:/host/rootfs:ro
    healthcheck:
      test: ["CMD-SHELL", "wget --spider --quiet http://localhost:19100/metrics || exit 1"]
      interval: 30s
      timeout: 10s
      retries: 5
    restart: unless-stopped
    networks:
      - zakupai-network

  loki:
    image: grafana/loki:2.9.6
    container_name: zakupai-loki-stage6
    profiles:
      - stage6
    command:
      - --config.file=/etc/loki/config/config.yml
    volumes:
      - ./monitoring/loki-config.yml:/etc/loki/config/config.yml:ro
    ports:
      - "3100:3100"
    healthcheck:
      test: ["CMD-SHELL", "wget --spider --quiet http://localhost:3100/ready || exit 1"]
      interval: 30s
      timeout: 10s
      retries: 5
    restart: unless-stopped
    networks:
      - zakupai-network

  grafana:
    image: grafana/grafana:10.4.4
    container_name: zakupai-grafana-stage6
    profiles:
      - stage6
    environment:
      GF_SECURITY_ADMIN_USER: admin
      GF_SECURITY_ADMIN_PASSWORD: admin
      GF_SECURITY_ALLOW_EMBEDDING: "true"
      GF_USERS_ALLOW_SIGN_UP: "false"
    ports:
      - "3000:3000"
    volumes:
      - grafana_data:/var/lib/grafana
      - ./monitoring/grafana/provisioning:/etc/grafana/provisioning:ro
    depends_on:
      prometheus:
        condition: service_healthy
      loki:
        condition: service_healthy
    healthcheck:
      test: ["CMD-SHELL", "wget --spider --quiet http://localhost:3000/api/health || exit 1"]
      interval: 30s
      timeout: 10s
      retries: 5
    restart: unless-stopped
    networks:
      - zakupai-network

volumes:
  prometheus_data:
  grafana_data:
EOF

  write_file "monitoring/prometheus.yml" <<'EOF'
global:
  scrape_interval: 15s
  scrape_timeout: 10s

rule_files: []

scrape_configs:
  - job_name: prometheus
    static_configs:
      - targets: ["prometheus:9090"]
        labels:
          service: prometheus
          environment: stage6

  - job_name: node-exporter
    metrics_path: /metrics
    static_configs:
      - targets: ["node-exporter:19100"]
        labels:
          service: node-exporter
          environment: stage6

  - job_name: gateway
    metrics_path: /metrics
    static_configs:
      - targets: ["gateway:80"]
        labels:
          service: gateway
          environment: stage6

  - job_name: risk-engine
    metrics_path: /metrics
    static_configs:
      - targets: ["risk-engine:8000"]
        labels:
          service: risk-engine
          environment: stage6

  - job_name: calc-service
    metrics_path: /metrics
    static_configs:
      - targets: ["calc-service:8000"]
        labels:
          service: calc-service
          environment: stage6

  - job_name: goszakup-api
    metrics_path: /metrics
    static_configs:
      - targets: ["goszakup-api:8001"]
        labels:
          service: goszakup-api
          environment: stage6

  - job_name: doc-service
    metrics_path: /metrics
    static_configs:
      - targets: ["doc-service:8000"]
        labels:
          service: doc-service
          environment: stage6

  - job_name: etl-service
    metrics_path: /metrics
    static_configs:
      - targets: ["etl-service:8000"]
        labels:
          service: etl-service
          environment: stage6

  - job_name: embedding-api
    metrics_path: /metrics
    static_configs:
      - targets: ["embedding-api:8000"]
        labels:
          service: embedding-api
          environment: stage6

  - job_name: billing-service
    metrics_path: /metrics
    static_configs:
      - targets: ["billing-service:8000"]
        labels:
          service: billing-service
          environment: stage6

  - job_name: web-ui
    metrics_path: /metrics
    static_configs:
      - targets: ["web-ui:8000"]
        labels:
          service: web-ui
          environment: stage6
EOF

  write_file "monitoring/loki-config.yml" <<'EOF'
auth_enabled: false

server:
  http_listen_port: 3100
  grpc_listen_port: 9096

common:
  path_prefix: /tmp/loki
  storage:
    filesystem:
      chunks_directory: /tmp/loki/chunks
      rules_directory: /tmp/loki/rules
  replication_factor: 1
  ring:
    kvstore:
      store: inmemory

schema_config:
  configs:
    - from: 2020-10-24
      store: boltdb-shipper
      object_store: filesystem
      schema: v11
      index:
        prefix: loki_index_
        period: 24h

storage_config:
  filesystem:
    directory: /tmp/loki

chunk_store_config:
  max_look_back_period: 168h

limits_config:
  reject_old_samples: true
  reject_old_samples_max_age: 168h
  allow_structured_metadata: true

table_manager:
  retention_deletes_enabled: true
  retention_period: 720h

compactor:
  working_directory: /tmp/loki/compactor
  shared_store: filesystem

analytics:
  reporting_enabled: false

pipeline_stages:
  - json:
      expressions:
        service: service
        procurement_type: procurement_type
        anti_dumping: anti_dumping
  - labels:
      service:
      procurement_type:
      anti_dumping:
EOF

  write_file "monitoring/grafana/provisioning/datasources/datasources.yml" <<'EOF'
apiVersion: 1

datasources:
  - name: Prometheus
    uid: zakupai-prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
    editable: false
    jsonData:
      timeInterval: 15s

  - name: Loki
    uid: zakupai-loki
    type: loki
    access: proxy
    url: http://loki:3100
    editable: false
    jsonData:
      maxLines: 1000
EOF

  write_file ".pre-commit-config.yaml" <<'EOF'
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer

  - repo: https://github.com/PyCQA/bandit
    rev: 1.7.6
    hooks:
      - id: bandit
        name: bandit (services)
        args:
          - -r
          - services
        additional_dependencies: []
EOF
}

fix_gateway_build_error() {
  log_info "Updating docker-compose build contexts for shared libs..."
  if [ ! -f "docker-compose.yml" ]; then
    abort "docker-compose.yml not found in $SCRIPT_DIR."
  fi

  local result
  result="$(LIBS_PATH="$LIBS_CONTEXT_PATH" python3 - <<'PY'
import os
from pathlib import Path

compose_path = Path("docker-compose.yml")
text = compose_path.read_text()
libs_path = os.environ["LIBS_PATH"]
changed = False

if "- libs=./libs" in text:
    text = text.replace("- libs=./libs", f"- libs={libs_path}")
    changed = True

relative_block = """    build:
      context: ./services/billing-service
      additional_contexts:
        - libs=./libs"""
absolute_block = f"""    build:
      context: ./services/billing-service
      additional_contexts:
        - libs={libs_path}"""

simple_line = "    build: ./services/billing-service"

if absolute_block not in text:
    if relative_block in text:
        text = text.replace(relative_block, absolute_block)
        changed = True
    elif simple_line in text:
        text = text.replace(simple_line, absolute_block)
        changed = True

if changed:
    compose_path.write_text(text)
print("changed" if changed else "unchanged")
PY
)"
  if [[ "$result" == "changed" ]]; then
    log_info "docker-compose.yml updated with absolute libs contexts."
  else
    log_info "docker-compose.yml already uses absolute libs contexts."
  fi
}

update_dockerfiles() {
  log_info "Normalizing Dockerfiles for shared library usage..."
  local output
  output="$(python3 - <<'PY'
from pathlib import Path

targets = [
    "services/gateway/Dockerfile",
    "services/risk-engine/Dockerfile",
    "services/calc-service/Dockerfile",
    "services/goszakup-api/Dockerfile",
    "services/doc-service/Dockerfile",
    "services/etl-service/Dockerfile",
    "services/embedding-api/Dockerfile",
    "services/billing-service/Dockerfile",
    "bot/Dockerfile",
]

for target in targets:
    path = Path(target)
    if not path.exists():
        print(f"missing:{target}")
        continue
    lines = path.read_text().splitlines()
    changed = False

    has_req_copy = any(line.strip() == "COPY requirements.txt /app/requirements.txt" for line in lines)
    if not has_req_copy:
        for idx, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("COPY requirements.txt"):
                lines[idx] = "COPY requirements.txt /app/requirements.txt"
                changed = True
                has_req_copy = True
                break
        if not has_req_copy:
            for idx, line in enumerate(lines):
                stripped = line.strip()
                if stripped.startswith("RUN") and "pip install" in stripped and "requirements.txt" in stripped:
                    lines.insert(idx, "COPY requirements.txt /app/requirements.txt")
                    changed = True
                    has_req_copy = True
                    break
        if not has_req_copy:
            for idx, line in enumerate(lines):
                if line.strip().startswith("WORKDIR"):
                    lines.insert(idx + 1, "COPY requirements.txt /app/requirements.txt")
                    changed = True
                    has_req_copy = True
                    break

    for idx, line in enumerate(lines):
        if "-r requirements.txt" in line:
            new_line = line.replace("-r requirements.txt", "-r /app/requirements.txt")
            if new_line != line:
                lines[idx] = new_line
                changed = True

    libs_line = "COPY --from=libs /zakupai_common /app/libs/zakupai_common"
    has_libs_copy = any(line.strip() == libs_line for line in lines)
    if not has_libs_copy:
        replaced = False
        for idx, line in enumerate(lines):
            if "COPY libs/zakupai_common" in line and "--from=libs" not in line:
                lines[idx] = libs_line
                changed = True
                replaced = True
                break
        if not replaced:
            for idx, line in enumerate(lines):
                stripped = line.strip()
                if stripped.startswith("COPY ."):
                    lines.insert(idx + 1, libs_line)
                    changed = True
                    break

    if changed:
        path.write_text("\n".join(lines) + "\n")
        print(f"updated:{target}")
PY
)"
  if [ -n "$output" ]; then
    while IFS= read -r line; do
      case "$line" in
        updated:*) log_info "Updated ${line#updated:}" ;;
        missing:*) log_warn "Skipped missing Dockerfile ${line#missing:}" ;;
      esac
    done <<<"$output"
  fi
}

add_metrics_dependencies() {
  log_info "Adding prometheus instrumentation dependency to service requirements..."
  local output
  output="$(python3 - <<'PY'
from pathlib import Path

pkg = "prometheus-fastapi-instrumentator>=6.0.0"
files = [
    "services/gateway/requirements.txt",
    "services/risk-engine/requirements.txt",
    "services/calc-service/requirements.txt",
    "services/goszakup-api/requirements.txt",
    "services/doc-service/requirements.txt",
    "services/etl-service/requirements.txt",
    "services/embedding-api/requirements.txt",
    "services/billing-service/requirements.txt",
]

for file in files:
    path = Path(file)
    if not path.exists():
        print(f"missing:{file}")
        continue
    lines = path.read_text().splitlines()
    if any(line.strip().startswith("prometheus-fastapi-instrumentator") for line in lines):
        print(f"skip:{file}")
        continue
    if lines and lines[-1].strip() != "":
        lines.append("")
    lines.append(pkg)
    path.write_text("\n".join(lines) + "\n")
    print(f"updated:{file}")
PY
)"
  if [ -n "$output" ]; then
    while IFS= read -r line; do
      case "$line" in
        updated:*) log_info "Added instrumentation dependency to ${line#updated:}" ;;
        skip:*) log_info "Dependency already present in ${line#skip:}" ;;
        missing:*) log_warn "Missing requirements file ${line#missing:}" ;;
      esac
    done <<<"$output"
  fi
}

instrument_fastapi_services() {
  log_info "Injecting Prometheus /metrics endpoint into FastAPI services..."
  local output
  output="$(python3 - <<'PY'
from pathlib import Path

services = [
    "services/gateway",
    "services/risk-engine",
    "services/calc-service",
    "services/goszakup-api",
    "services/doc-service",
    "services/etl-service",
    "services/embedding-api",
    "services/billing-service",
]
import_line = "from prometheus_fastapi_instrumentator import Instrumentator"
instrumentation_line = 'Instrumentator().instrument(app).expose(app, endpoint="/metrics")'

def find_fastapi_end(lines, start_idx):
    depth = 0
    for idx in range(start_idx, len(lines)):
        line = lines[idx]
        depth += line.count("(")
        depth -= line.count(")")
        if depth <= 0 and ")" in line:
            return idx
    return start_idx

for service in services:
    path = Path(service) / "main.py"
    if not path.exists():
        print(f"missing:{path}")
        continue
    lines = path.read_text().splitlines()
    original_lines = list(lines)

    if import_line not in lines:
        insert_idx = 0
        for idx, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith(("import ", "from ")) and not line.startswith((" ", "\t")):
                insert_idx = idx + 1
        lines.insert(insert_idx, import_line)

    if instrumentation_line not in lines:
        app_idx = next((idx for idx, line in enumerate(lines) if "app = FastAPI" in line), None)
        if app_idx is None:
            print(f"warn:{path}:unable_to_locate_app")
        else:
            end_idx = find_fastapi_end(lines, app_idx)
            insert_idx = end_idx + 1
            insert_block = []
            if insert_idx > 0 and lines[insert_idx - 1].strip() != "":
                insert_block.append("")
            insert_block.append(instrumentation_line)
            if insert_idx < len(lines) and lines[insert_idx].strip() != "":
                insert_block.append("")
            lines[insert_idx:insert_idx] = insert_block

    if lines != original_lines:
        path.write_text("\n".join(lines) + "\n")
        print(f"updated:{path}")
PY
)"
  if [ -n "$output" ]; then
    while IFS= read -r line; do
      case "$line" in
        updated:*) log_info "Instrumented ${line#updated:}" ;;
        missing:*) log_warn "Missing service module ${line#missing:}" ;;
        warn:*) log_warn "${line#warn:}" ;;
      esac
    done <<<"$output"
  fi
}

adjust_web_ui_metrics() {
  if [ ! -f "web/main.py" ]; then
    log_warn "web/main.py not found; skipping web-ui metrics check."
    return
  fi
  local result
  result="$(python3 - <<'PY'
from pathlib import Path

main_path = Path("web/main.py")
text = main_path.read_text()
changed = False

target = "instrumentator.instrument(app).expose(app, endpoint=\"/metrics\")"
if "Instrumentator" in text and target not in text and "instrumentator.instrument(app).expose(app)" in text:
    text = text.replace("instrumentator.instrument(app).expose(app)", target)
    changed = True

if changed:
    main_path.write_text(text)
    print("updated")
else:
    print("unchanged")
PY
)"
  if [[ "$result" == "updated" ]]; then
    log_info "Updated web/main.py to expose metrics at /metrics."
  else
    log_info "web/main.py already exposes metrics at /metrics."
  fi
}

normalize_instrumentation_layout() {
  log_info "Normalizing metrics instrumentation layout across FastAPI services..."
  local output
  output="$(python3 - <<'PY'
from pathlib import Path

services = [
    "services/gateway",
    "services/risk-engine",
    "services/calc-service",
    "services/goszakup-api",
    "services/doc-service",
    "services/etl-service",
    "services/embedding-api",
    "services/billing-service",
]
import_line = "from prometheus_fastapi_instrumentator import Instrumentator"
instrumentation_line = 'Instrumentator().instrument(app).expose(app, endpoint="/metrics")'

for service in services:
    path = Path(service) / "main.py"
    if not path.exists():
        print(f"missing:{path}")
        continue
    lines = path.read_text().splitlines()
    original = list(lines)

    lines = [line for line in lines if line.strip() != import_line]
    import_indices = [
        idx for idx, line in enumerate(lines)
        if line and not line.startswith((" ", "\t")) and line.strip().startswith(("import ", "from "))
    ]
    insert_idx = import_indices[-1] + 1 if import_indices else 0
    lines.insert(insert_idx, import_line)

    lines = [line for line in lines if line.strip() != instrumentation_line]

    app_idx = next((idx for idx, line in enumerate(lines) if "app = FastAPI" in line), None)
    if app_idx is None:
        print(f"warn:{path}:fastapi_app_not_found")
        if lines != original:
            path.write_text("\n".join(lines) + "\n")
            print(f"normalized:{path}")
        continue

    depth = 0
    end_idx = app_idx
    for idx in range(app_idx, len(lines)):
        line = lines[idx]
        depth += line.count("(")
        depth -= line.count(")")
        if depth <= 0 and ")" in line:
            end_idx = idx
            break

    insert_idx = end_idx + 1
    insert_segment = []
    if insert_idx > 0 and lines[insert_idx - 1].strip() != "":
        insert_segment.append("")
    insert_segment.append(instrumentation_line)
    if insert_idx < len(lines) and lines[insert_idx].strip() != "":
        insert_segment.append("")
    lines[insert_idx:insert_idx] = insert_segment

    if lines != original:
        path.write_text("\n".join(lines) + "\n")
        print(f"normalized:{path}")
PY
)"
  if [ -n "$output" ]; then
    while IFS= read -r line; do
      case "$line" in
        normalized:*) log_info "Normalized ${line#normalized:}" ;;
        missing:*) log_warn "Missing service module ${line#missing:}" ;;
        warn:*) log_warn "${line#warn:}" ;;
      esac
    done <<<"$output"
  fi
}

apply_bandit_remediations() {
  log_info "Applying deterministic fixes for known Bandit findings..."
  python3 - <<'PY'
from pathlib import Path
import re

flowise_path = Path("web/flowise_week4_2.py")
if flowise_path.exists():
    text = flowise_path.read_text()
    import_line = "from sqlalchemy import text"
    if "bindparam" not in text and import_line in text:
        text = text.replace(import_line, "from sqlalchemy import bindparam, text")
    old_block = """        if requested_sources:
            # Filter by requested sources
            placeholders = ",".join([f"'{source}'" for source in requested_sources])
            query = text(  # nosec B608
                f\"\"\"
                SELECT * FROM supplier_sources
                WHERE active = true AND name IN ({placeholders})
                ORDER BY name
            \"\"\"
            )
        else:
            query = text(
                \"\"\"
                SELECT * FROM supplier_sources
                WHERE active = true
                ORDER BY name
            \"\"\"
            )

        result = db_session.execute(query).fetchall()
"""
    if old_block in text:
        new_block = """        if requested_sources:
            query = (
                text(
                    \"\"\"
                SELECT * FROM supplier_sources
                WHERE active = true AND name IN :requested_names
                ORDER BY name
            \"\"\"
                ).bindparams(bindparam("requested_names", expanding=True))
            )
            params = {"requested_names": requested_sources}
        else:
            query = text(
                \"\"\"
                SELECT * FROM supplier_sources
                WHERE active = true
                ORDER BY name
            \"\"\"
            )
            params = {}

        result = db_session.execute(query, params).fetchall()
"""
        text = text.replace(old_block, new_block)
        flowise_path.write_text(text)

mock_path = Path("web/mock_data.py")
if mock_path.exists():
    text = mock_path.read_text()
    if "_secure_random = random.SystemRandom()" not in text and "import random" in text:
        text = text.replace("import random\n", "import random\n\n_secure_random = random.SystemRandom()\n", 1)
    def replacer(match: re.Match) -> str:
        return f"_secure_random.{match.group(1)}"
    text = re.sub(r"\brandom\.(randint|uniform)\b", replacer, text)
    mock_path.write_text(text)

tests_path = Path("web/test_e2e_webui.py")
if tests_path.exists():
    lines = tests_path.read_text().splitlines()
    changed = False
    for idx, line in enumerate(lines):
        stripped = line.lstrip()
        if stripped.startswith("assert") and "# nosec" not in stripped:
            lines[idx] = f"{line}  # nosec B101"
            changed = True
    if changed:
        tests_path.write_text("\n".join(lines) + "\n")
PY
}

install_security_tooling() {
  log_info "Ensuring Bandit and pre-commit are available..."
  if ! python3 -m pip --version >/dev/null 2>&1; then
    log_warn "pip for python3 not found; bootstrapping via ensurepip."
    if ! python3 -m ensurepip --upgrade >/dev/null 2>&1; then
      abort "Failed to bootstrap pip for python3."
    fi
  fi

  if [[ -n "${VIRTUAL_ENV-}" ]]; then
    python3 -m pip install --upgrade pip >/dev/null 2>&1 || log_warn "Unable to upgrade pip (continuing with existing version)."
  else
    python3 -m pip install --user --upgrade pip >/dival 2>&1 || log_warn "Unable to upgrade pip (continuing with existing version)."
  fi

  pip_install_packages "pre-commit and bandit" pre-commit bandit
}

run_security_checks() {
  log_info "Installing pre-commit hooks..."
  pre-commit install

  log_info "Running Bandit security scan (services/*/main.py)..."
  shopt -s nullglob
  local bandit_targets=(services/*/main.py)
  if [ ${#bandit_targets[@]} -eq 0 ]; then
    log_warn "No FastAPI main modules found to scan."
  else
    if ! bandit -r "${bandit_targets[@]}"; then
      log_warn "Bandit recursion over explicit files failed; retrying by directory..."
      local service_dirs=()
      local path
      for path in "${bandit_targets[@]}"; do
        service_dirs+=("$(dirname "$path")")
      done
      if ! bandit -r "${service_dirs[@]}"; then
        abort "Bandit reported issues. Resolve them before re-running."
      fi
    fi
  fi
  shopt -u nullglob

  log_info "Running pre-commit hooks across repository..."
  if ! pre-commit run --all-files; then
    abort "pre-commit checks failed. Review output, fix issues, and re-run."
  fi
}

detect_compose_command() {
  if command -v docker >/dev/null 2>&1 && docker compose version >/dival 2>&1; then
    COMPOSE_CMD=(docker compose)
  elif command -v docker-compose >/dival 2>&1; then
    COMPOSE_CMD=(docker-compose)
  else
    abort "Docker Compose v2 or v1 is required."
  fi
}

launch_and_verify() {
  detect_compose_command
  log_info "Building and launching Stage6 observability stack..."
  "${COMPOSE_CMD[@]}" "${COMPOSE_ARGS[@]}" --profile stage6 up -d --build

  log_info "Waiting up to 30 seconds for observability containers to become healthy..."
  local containers attempts delay all_ready container status metrics_output
  containers=("zakupai-prometheus-stage6" "zakupai-node-exporter-stage6" "zakupai-loki-stage6" "zakupai-grafana-stage6")
  attempts=6
  delay=5
  all_ready=0

  for ((attempt=1; attempt<=attempts; attempt++)); do
    all_ready=1
    for container in "${containers[@]}"; do
      if ! docker inspect "$container" >/dival 2>&1; then
        log_warn "Container $container not found yet (attempt $attempt/$attempts)."
        all_ready=0
        continue
      fi
      status="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$container" 2>/dival || true)"
      status="${status//$'\n'/}"
      if [[ -z "$status" ]]; then
        log_warn "Unable to determine status for $container (attempt $attempt/$attempts)."
        all_ready=0
        continue
      fi
      if [[ "$status" != "healthy" && "$status" != "running" ]]; then
        all_ready=0
        log_warn "$container status: $status (attempt $attempt/$attempts)"
      fi
    done
    if [[ $all_ready -eq 1 ]]; then
      break
    fi
    sleep "$delay"
  done

  if [[ $all_ready -ne 1 ]]; then
    "${COMPOSE_CMD[@]}" "${COMPOSE_ARGS[@]}" ps prometheus node-exporter loki grafana || true
    abort "One or more observability containers are not healthy. Check logs and rerun the script."
  fi

  log_info "Containers are running:"
  "${COMPOSE_CMD[@]}" "${COMPOSE_ARGS[@]}" ps prometheus node-exporter loki grafana

  log_info "Checking Node Exporter metrics endpoint..."
  if ! metrics_output="$(curl --fail --silent --show-error http://localhost:19100/metrics)"; then
    abort "Failed to fetch metrics from node-exporter at http://localhost:19100/metrics."
  fi
  printf '%s\n' "$metrics_output" | head -n 20

  log_info "Checking Loki readiness endpoint..."
  if ! curl --fail --silent --show-error http://localhost:3100/ready >/dival; then
    abort "Loki readiness check failed."
  fi

  log_info "Validating Prometheus configuration with promtool..."
  if command -v promtool >/dival 2>&1; then
    promtool check config monitoring/prometheus.yml
  else
    log_warn "promtool not found locally; running promtool via docker."
    docker run --rm -v "$SCRIPT_DIR/monitoring/prometheus.yml:/config/prometheus.yml:ro" prom/prometheus:v2.51.0 promtool check config /config/prometheus.yml
  fi

  log_info "Attempting to open observability dashboards..."
  open_url "http://localhost:9090/targets"
  open_url "http://localhost:3000"
  echo "Grafana login: admin / admin"
}

main() {
  ensure_prereqs
  create_directories_and_files
  fix_gateway_build_error
  update_dockerfiles
  add_metrics_dependencies
  instrument_fastapi_services
  adjust_web_ui_metrics
  normalize_instrumentation_layout
  apply_bandit_remediations
  install_security_tooling
  run_security_checks
  launch_and_verify
  log_info "Stage6 observability stack setup complete. Check http://localhost:9090/targets for targets UP."
}

main "$@"
