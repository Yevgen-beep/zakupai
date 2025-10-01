#!/usr/bin/env bash
set -euo pipefail

# =============================================================================
# Stage6 Monitoring Test Suite - ZakupAI
# =============================================================================
# Comprehensive validation of monitoring infrastructure:
# - Prometheus, Alertmanager, Grafana, Node Exporter, cAdvisor, Loki, Blackbox
# - Configuration validation with promtool and amtool
# - API checks, metrics validation, log aggregation verification
#
# Usage:
#   ./stage6-monitoring-test.sh           # Full test (start stack, run tests, optionally stop)
#   ./stage6-monitoring-test.sh --ci      # CI mode (assume stack is running)
#   ./stage6-monitoring-test.sh --keep-up # Keep stack running after tests
#   ./stage6-monitoring-test.sh --help    # Show this help
# =============================================================================

# Constants
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly COMPOSE_FILES="-f docker-compose.yml -f docker-compose.override.stage6.yml -f docker-compose.override.stage6.monitoring.yml"
readonly COMPOSE_PROFILE="--profile stage6"

# Service URLs
readonly PROMETHEUS_URL="http://localhost:9090"
readonly ALERTMANAGER_URL="http://localhost:9093"
readonly GRAFANA_URL="http://localhost:3030"
readonly NODE_EXPORTER_URL="http://localhost:19100"
readonly CADVISOR_URL="http://localhost:8081"
readonly LOKI_URL="http://localhost:3100"
readonly BLACKBOX_URL="http://localhost:9115"

# Timeouts
readonly HEALTH_CHECK_TIMEOUT=60
readonly HEALTH_CHECK_INTERVAL=3
readonly MAX_RETRIES=$((HEALTH_CHECK_TIMEOUT / HEALTH_CHECK_INTERVAL))

# Colors
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly CYAN='\033[0;36m'
readonly BOLD='\033[1m'
readonly NC='\033[0m'

# State
TESTS_PASSED=0
TESTS_FAILED=0
START_TIME=$(date +%s)
CI_MODE=false
KEEP_STACK_UP=false

# =============================================================================
# Utility Functions
# =============================================================================

log_info() {
    echo -e "${BLUE}ℹ${NC}  $*"
}

log_success() {
    echo -e "${GREEN}✅${NC} $*"
    TESTS_PASSED=$((TESTS_PASSED + 1))
}

log_error() {
    echo -e "${RED}❌${NC} $*"
    TESTS_FAILED=$((TESTS_FAILED + 1))
}

log_warning() {
    echo -e "${YELLOW}⚠${NC}  $*"
}

log_section() {
    echo ""
    echo -e "${CYAN}${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${CYAN}${BOLD}$*${NC}"
    echo -e "${CYAN}${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

trap_error() {
    local exit_code=$?
    local line_no=$1
    log_error "Script failed at line ${line_no} with exit code ${exit_code}"
    log_warning "Check logs with: docker compose logs <service>"
    exit "${exit_code}"
}

trap 'trap_error ${LINENO}' ERR

compose_cmd() {
    docker compose ${COMPOSE_FILES} ${COMPOSE_PROFILE} "$@"
}

# =============================================================================
# Dependency Checks
# =============================================================================

check_dependencies() {
    log_section "[1/10] Checking Dependencies"

    local required_tools=("curl" "jq" "docker" "promtool" "amtool" "python3")
    local missing_tools=()

    for tool in "${required_tools[@]}"; do
        if command -v "${tool}" >/dev/null 2>&1; then
            log_success "${tool} is installed"
        else
            log_error "${tool} is NOT installed"
            missing_tools+=("${tool}")
        fi
    done

    if [[ ${#missing_tools[@]} -gt 0 ]]; then
        echo ""
        log_error "Missing required tools: ${missing_tools[*]}"
        echo ""
        echo "Installation instructions:"
        echo "  • curl, jq, docker: install via package manager (apt/yum/brew)"
        echo "  • promtool: https://prometheus.io/download/"
        echo "  • amtool: https://github.com/prometheus/alertmanager/releases"
        echo "  • python3: install via package manager"
        exit 1
    fi
}

# =============================================================================
# Docker Stack Management
# =============================================================================

stack_up() {
    log_section "[2/10] Starting Monitoring Stack"

    log_info "Building and starting containers..."
    if compose_cmd up -d --build 2>&1 | tee /tmp/stack_up.log; then
        log_success "Stack started successfully"
    else
        log_error "Failed to start stack"
        cat /tmp/stack_up.log
        exit 1
    fi
}

stack_down() {
    log_section "Stopping Monitoring Stack"

    log_info "Stopping and removing containers..."
    if compose_cmd down 2>&1 | tee /tmp/stack_down.log; then
        log_success "Stack stopped successfully"
    else
        log_error "Failed to stop stack"
        cat /tmp/stack_down.log
    fi
}

# =============================================================================
# Health Check Functions
# =============================================================================

wait_for_http() {
    local name=$1
    local url=$2
    local retry_count=0

    log_info "Waiting for ${name} at ${url}..."

    while [[ ${retry_count} -lt ${MAX_RETRIES} ]]; do
        if curl -fsS "${url}" >/dev/null 2>&1; then
            log_success "${name} is ready"
            return 0
        fi

        retry_count=$((retry_count + 1))
        sleep "${HEALTH_CHECK_INTERVAL}"
    done

    log_error "${name} failed to become ready (timeout: ${HEALTH_CHECK_TIMEOUT}s)"
    return 1
}

wait_for_logs() {
    local container=$1
    local pattern=$2
    local retry_count=0

    log_info "Waiting for pattern '${pattern}' in ${container} logs..."

    while [[ ${retry_count} -lt ${MAX_RETRIES} ]]; do
        if docker logs "${container}" 2>&1 | grep -q "${pattern}"; then
            log_success "Found pattern in ${container}"
            return 0
        fi

        retry_count=$((retry_count + 1))
        sleep "${HEALTH_CHECK_INTERVAL}"
    done

    log_error "Pattern not found in ${container} (timeout: ${HEALTH_CHECK_TIMEOUT}s)"
    return 1
}

check_service_health() {
    log_section "[3/10] Service Health Checks"

    local all_healthy=true

    wait_for_http "Prometheus" "${PROMETHEUS_URL}/-/healthy" || all_healthy=false
    wait_for_http "Alertmanager" "${ALERTMANAGER_URL}/-/healthy" || all_healthy=false
    wait_for_http "Grafana" "${GRAFANA_URL}/api/health" || all_healthy=false
    wait_for_http "Node Exporter" "${NODE_EXPORTER_URL}/metrics" || all_healthy=false
    wait_for_http "cAdvisor" "${CADVISOR_URL}/healthz" || all_healthy=false
    wait_for_http "Loki" "${LOKI_URL}/ready" || all_healthy=false
    wait_for_http "Blackbox Exporter" "${BLACKBOX_URL}/-/healthy" || all_healthy=false

    if [[ "${all_healthy}" == "false" ]]; then
        log_warning "Some services are not healthy, but continuing tests..."
    fi
}

# =============================================================================
# API Validation
# =============================================================================

validate_prometheus_targets() {
    log_section "[4/10] Validating Prometheus Targets"

    log_info "Fetching targets from Prometheus API..."
    local targets_response
    if ! targets_response=$(curl -fsS "${PROMETHEUS_URL}/api/v1/targets" 2>&1); then
        log_error "Failed to fetch Prometheus targets"
        echo "${targets_response}"
        return 1
    fi

    if [[ $(echo "${targets_response}" | jq -r '.status') != "success" ]]; then
        log_error "Prometheus API returned non-success status"
        echo "${targets_response}" | jq '.'
        return 1
    fi

    local expected_jobs=("prometheus" "blackbox-http" "cadvisor" "node-exporter")
    local all_up=true

    for job in "${expected_jobs[@]}"; do
        local job_up_count
        job_up_count=$(echo "${targets_response}" | jq -r ".data.activeTargets[] | select(.labels.job==\"${job}\" and .health==\"up\") | .labels.job" | wc -l)

        if [[ ${job_up_count} -gt 0 ]]; then
            log_success "Job '${job}': ${job_up_count} target(s) UP"
        else
            log_error "Job '${job}': NO targets UP"
            all_up=false
        fi
    done

    [[ "${all_up}" == "true" ]]
}

validate_prometheus_rules() {
    log_section "[5/10] Validating Prometheus Rules"

    log_info "Fetching rules from Prometheus API..."
    local rules_response
    if ! rules_response=$(curl -fsS "${PROMETHEUS_URL}/api/v1/rules" 2>&1); then
        log_error "Failed to fetch Prometheus rules"
        echo "${rules_response}"
        return 1
    fi

    if [[ $(echo "${rules_response}" | jq -r '.status') != "success" ]]; then
        log_error "Prometheus API returned non-success status"
        echo "${rules_response}" | jq '.'
        return 1
    fi

    local expected_groups=("zakupai_infrastructure" "zakupai_application" "zakupai_business")
    local all_loaded=true

    for group in "${expected_groups[@]}"; do
        local group_exists
        group_exists=$(echo "${rules_response}" | jq -r ".data.groups[] | select(.name==\"${group}\") | .name")

        if [[ -n "${group_exists}" ]]; then
            local rule_count
            rule_count=$(echo "${rules_response}" | jq -r ".data.groups[] | select(.name==\"${group}\") | .rules | length")
            log_success "Rule group '${group}': ${rule_count} rule(s) loaded"
        else
            log_error "Rule group '${group}': NOT found"
            all_loaded=false
        fi
    done

    [[ "${all_loaded}" == "true" ]]
}

validate_alertmanager_config() {
    log_section "[6/10] Validating Alertmanager Configuration"

    log_info "Fetching Alertmanager status..."
    local status_response
    if ! status_response=$(curl -fsS "${ALERTMANAGER_URL}/api/v2/status" 2>&1); then
        log_error "Failed to fetch Alertmanager status"
        echo "${status_response}"
        return 1
    fi

    if [[ $(echo "${status_response}" | jq -r '.versionInfo' 2>/dev/null) != "null" ]]; then
        log_success "Alertmanager is operational"
    else
        log_error "Alertmanager status check failed"
        echo "${status_response}" | jq '.'
        return 1
    fi

    log_info "Checking receivers..."
    local receivers_response
    if receivers_response=$(curl -fsS "${ALERTMANAGER_URL}/api/v2/receivers" 2>&1); then
        local receivers_count
        receivers_count=$(echo "${receivers_response}" | jq '. | length' 2>/dev/null || echo 0)

        if [[ ${receivers_count} -gt 0 ]]; then
            log_success "Alertmanager has ${receivers_count} receiver(s) configured"

            # Check for 'default' or 'web.hook' receiver
            local default_receiver
            default_receiver=$(echo "${receivers_response}" | jq -r '.[] | select(.name=="web.hook" or .name=="default") | .name' | head -1)
            if [[ -n "${default_receiver}" ]]; then
                log_success "Default receiver '${default_receiver}' found"
            else
                log_warning "No 'default' or 'web.hook' receiver found"
            fi
        else
            log_warning "No receivers configured in Alertmanager"
        fi
    else
        log_warning "Could not fetch receivers: ${receivers_response}"
    fi
}

# =============================================================================
# Static Configuration Validation
# =============================================================================

validate_static_configs() {
    log_section "[7/10] Static Configuration Validation"

    # Prometheus config
    log_info "Validating Prometheus config..."
    if promtool check config monitoring/prometheus/prometheus.yml >/dev/null 2>&1; then
        log_success "Prometheus config is valid"
    else
        log_error "Prometheus config validation failed"
        promtool check config monitoring/prometheus/prometheus.yml 2>&1 | head -20
    fi

    # Prometheus rules
    if [[ -f monitoring/prometheus/alerts.yml ]]; then
        log_info "Validating Prometheus rules..."
        if promtool check rules monitoring/prometheus/alerts.yml >/dev/null 2>&1; then
            log_success "Prometheus rules are valid"
        else
            log_error "Prometheus rules validation failed"
            promtool check rules monitoring/prometheus/alerts.yml 2>&1 | head -20
        fi
    else
        log_warning "monitoring/prometheus/alerts.yml not found, skipping"
    fi

    # Alertmanager config
    if [[ -f monitoring/alertmanager/alertmanager.yml ]]; then
        log_info "Validating Alertmanager config..."
        if amtool check-config monitoring/alertmanager/alertmanager.yml >/dev/null 2>&1; then
            log_success "Alertmanager config is valid"
        else
            log_error "Alertmanager config validation failed"
            amtool check-config monitoring/alertmanager/alertmanager.yml 2>&1 | head -20
        fi
    else
        log_warning "monitoring/alertmanager/alertmanager.yml not found, skipping"
    fi
}

# =============================================================================
# Loki & Promtail Validation
# =============================================================================

validate_loki_promtail() {
    log_section "[8/10] Validating Loki & Promtail Integration"

    # Check Loki readiness
    log_info "Checking Loki readiness..."
    if curl -fsS "${LOKI_URL}/ready" >/dev/null 2>&1; then
        log_success "Loki is ready"
    else
        log_error "Loki readiness check failed"
        return 1
    fi

    # Query logs via logcli
    log_info "Testing Loki query (recent logs)..."
    local logcli_output
    if logcli_output=$(docker run --rm --network host grafana/logcli:2.9.0 \
        --addr="${LOKI_URL}" \
        query --since=1h --limit=1 '{compose_project="zakupai"}' 2>&1); then

        if echo "${logcli_output}" | grep -q "common labels"; then
            log_success "Loki query successful (logs are flowing)"
        else
            log_warning "Loki query returned no results (logs may not be flowing yet)"
            echo "${logcli_output}" | head -10
        fi
    else
        log_warning "Loki query failed (this may be normal if no logs yet)"
        echo "${logcli_output}" | head -10
    fi
}

# =============================================================================
# Metrics Validation
# =============================================================================

validate_metrics() {
    log_section "[9/10] Running Metrics Tests"

    if [[ ! -f test_monitoring_metrics.py ]]; then
        log_warning "test_monitoring_metrics.py not found, skipping"
        return 0
    fi

    log_info "Executing test_monitoring_metrics.py..."
    local metrics_output
    if metrics_output=$(python3 test_monitoring_metrics.py 2>&1); then
        log_success "Metrics tests passed"
        echo "${metrics_output}" | tail -5
    else
        log_error "Metrics tests failed"
        echo ""
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo "Metrics Test Output:"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo "${metrics_output}"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        return 1
    fi
}

# =============================================================================
# Final Report
# =============================================================================

generate_report() {
    log_section "[10/10] Test Summary Report"

    local end_time
    end_time=$(date +%s)
    local duration=$((end_time - START_TIME))

    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo -e "${BOLD}Test Results Summary${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""

    local total_tests=$((TESTS_PASSED + TESTS_FAILED))
    local pass_rate=0
    if [[ ${total_tests} -gt 0 ]]; then
        pass_rate=$(awk "BEGIN {printf \"%.1f\", (${TESTS_PASSED} / ${total_tests}) * 100}")
    fi

    echo -e "  ${GREEN}✅ Passed:${NC}  ${TESTS_PASSED} / ${total_tests} (${pass_rate}%)"
    echo -e "  ${RED}❌ Failed:${NC}  ${TESTS_FAILED} / ${total_tests}"
    echo -e "  ${BLUE}⏱  Duration:${NC} ${duration}s"
    echo ""

    if [[ ${TESTS_FAILED} -eq 0 ]]; then
        echo -e "${GREEN}${BOLD}🎉 All monitoring tests passed!${NC}"
    else
        echo -e "${RED}${BOLD}⚠️  Some tests failed. See details above.${NC}"
    fi

    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo -e "${BOLD}Debugging Commands${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "  View service logs:"
    echo "    docker compose logs zakupai-prometheus"
    echo "    docker compose logs zakupai-alertmanager"
    echo "    docker compose logs zakupai-loki"
    echo "    docker compose logs zakupai-promtail-stage6"
    echo "    docker compose logs zakupai-grafana"
    echo ""
    echo "  Check service status:"
    echo "    docker compose ps"
    echo ""
    echo "  Access UIs:"
    echo "    Prometheus:   ${PROMETHEUS_URL}"
    echo "    Alertmanager: ${ALERTMANAGER_URL}"
    echo "    Grafana:      ${GRAFANA_URL}"
    echo "    Loki:         ${LOKI_URL}"
    echo ""
}

# =============================================================================
# Main Execution
# =============================================================================

usage() {
    cat <<EOF
${BOLD}Stage6 Monitoring Test Suite - ZakupAI${NC}

${BOLD}USAGE:${NC}
    $0 [OPTIONS]

${BOLD}OPTIONS:${NC}
    --ci            CI mode (skip stack up/down, assume services are running)
    --keep-up       Keep stack running after tests (don't stop)
    -h, --help      Show this help message

${BOLD}EXAMPLES:${NC}
    $0                    # Full test: start stack, run tests, prompt to stop
    $0 --ci               # CI mode: run tests on already-running stack
    $0 --keep-up          # Run tests and keep stack running
    make monitoring-test  # Run via Makefile

${BOLD}REQUIREMENTS:${NC}
    curl, jq, docker, promtool, amtool, python3

${BOLD}DESCRIPTION:${NC}
    Comprehensive validation of Stage6 monitoring infrastructure including:
    • Dependency checks
    • Docker stack management
    • Service health checks (Prometheus, Alertmanager, Grafana, etc.)
    • API validation (targets, rules, receivers)
    • Static config validation (promtool, amtool)
    • Loki/Promtail log aggregation
    • Custom metrics validation

EOF
    exit 0
}

main() {
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --ci)
                CI_MODE=true
                shift
                ;;
            --keep-up)
                KEEP_STACK_UP=true
                shift
                ;;
            -h|--help)
                usage
                ;;
            *)
                log_error "Unknown option: $1"
                usage
                ;;
        esac
    done

    # Header
    echo ""
    echo -e "${CYAN}${BOLD}╔════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}${BOLD}║   Stage6 Monitoring Test Suite - ZakupAI          ║${NC}"
    echo -e "${CYAN}${BOLD}╚════════════════════════════════════════════════════╝${NC}"
    echo ""

    # Step 1: Check dependencies
    check_dependencies

    # Step 2: Start stack (unless in CI mode)
    if [[ "${CI_MODE}" == "false" ]]; then
        stack_up
        sleep 5  # Give services a moment to initialize
    else
        log_info "CI mode: skipping stack startup"
    fi

    # Step 3: Health checks
    check_service_health

    # Step 4-6: API validation
    validate_prometheus_targets || true
    validate_prometheus_rules || true
    validate_alertmanager_config || true

    # Step 7: Static config validation
    validate_static_configs || true

    # Step 8: Loki/Promtail
    validate_loki_promtail || true

    # Step 9: Metrics tests
    validate_metrics || true

    # Step 10: Generate report
    generate_report

    # Cleanup (if not in CI mode and not keeping up)
    if [[ "${CI_MODE}" == "false" ]] && [[ "${KEEP_STACK_UP}" == "false" ]]; then
        echo ""
        read -r -p "Stop monitoring stack? [y/N] " response
        if [[ "${response}" =~ ^[Yy]$ ]]; then
            stack_down
        else
            log_info "Stack left running. Stop manually with: docker compose ${COMPOSE_FILES} ${COMPOSE_PROFILE} down"
        fi
    fi

    # Exit with appropriate code
    if [[ ${TESTS_FAILED} -gt 0 ]]; then
        exit 1
    else
        exit 0
    fi
}

main "$@"
