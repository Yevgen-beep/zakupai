#!/usr/bin/env bash
set -euo pipefail

SECONDS=0

for cmd in docker jq curl; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "Missing dependency: $cmd" >&2
    exit 1
  fi
done

compose_cmd=(
  docker compose
  --profile stage6
  -f docker-compose.yml
  -f docker-compose.override.stage6.yml
  -f docker-compose.override.stage6.monitoring.yml
  -f monitoring/vault/docker-compose.override.stage6.vault.yml
)
compose_base_cmd="docker compose --profile stage6 -f docker-compose.yml -f docker-compose.override.stage6.yml -f docker-compose.override.stage6.monitoring.yml -f monitoring/vault/docker-compose.override.stage6.vault.yml"

if command -v tput >/dev/null 2>&1 && [ -t 1 ]; then
  green=$(tput setaf 2)
  red=$(tput setaf 1)
  yellow=$(tput setaf 3)
  blue=$(tput setaf 4)
  bold=$(tput bold)
  reset=$(tput sgr0)
else
  green=""; red=""; yellow=""; blue=""; bold=""; reset=""
fi

OK_MARK="✅"
FAIL_MARK="❌"
WARN_MARK="⚠️"
NA_MARK="➖"

fmt_ok()   { printf "%s%s%s %s" "$green" "$OK_MARK" "$reset" "$1"; }
fmt_fail() { printf "%s%s%s %s" "$red" "$FAIL_MARK" "$reset" "$1"; }
fmt_warn() { printf "%s%s%s %s" "$yellow" "$WARN_MARK" "$reset" "$1"; }
fmt_na()   { printf "%s%s%s %s" "$yellow" "$NA_MARK" "$reset" "$1"; }
fmt_info() { printf "%s%s%s" "$blue" "$1" "$reset"; }

print_banner() {
  local text="$1"
  printf "\n%s%s%s (%s)\n" "$bold" "$text" "$reset" "$(date '+%Y-%m-%d %H:%M:%S')"
}

list_to_string() {
  local -n arr_ref="$1"
  local delim="${2:-, }"
  local joined=""
  for item in "${arr_ref[@]}"; do
    if [[ -n "$item" ]]; then
      if [[ -n "$joined" ]]; then
        joined+="$delim"
      fi
      joined+="$item"
    fi
  done
  printf "%s" "$joined"
}

add_issue() {
  local svc="$1"
  local list_name="$2"
  local seen_name="$3"
  local -n list_ref="$list_name"
  local -n seen_ref="$seen_name"
  if [[ -z "${seen_ref[$svc]:-}" ]]; then
    list_ref+=("$svc")
    seen_ref[$svc]=1
  fi
}

capture_compose_json() {
  local __out_var="$1"; shift
  local err_file raw warnings start_line trimmed first_char array_json
  err_file=$(mktemp)
  raw=$("$@" 2>"$err_file") || { cat "$err_file" >&2; rm -f "$err_file"; return 1; }
  warnings=$(<"$err_file"); rm -f "$err_file"
  # Filter out known benign warnings
  warnings=$(printf "%s" "$warnings" | grep -v 'variable is not set' | grep -v 'Defaulting to a blank string' || true)
  if [[ -n "${warnings//[[:space:]]/}" ]]; then
    printf "%s\n" "$(fmt_warn "docker compose warnings:")"
    printf "%s\n" "$warnings"
  fi
  raw=${raw//$'\r'/}
  start_line=$(printf "%s" "$raw" | grep -n -m1 -E '^[[:space:]]*[\\{\\[]' | cut -d: -f1 || true)
  if [[ -z "$start_line" ]]; then
    printf "%s\n" "$(fmt_fail "Unable to find JSON payload.")"
    return 1
  fi
  trimmed=$(printf "%s" "$raw" | tail -n +"$start_line")
  first_char=$(printf "%s" "$trimmed" | sed -n '1{s/^[[:space:]]*//;s/^\(.\).*/\1/;p}')
  if [[ "$first_char" == "[" ]]; then
    array_json="$trimmed"
  elif [[ "$first_char" == "{" ]]; then
    if ! array_json=$(printf "%s" "$trimmed" | jq -s '.' 2>/dev/null); then
      printf "%s\n" "$(fmt_fail "Failed to fold JSON lines into an array.")"
      return 1
    fi
  else
    printf "%s\n" "$(fmt_fail "Unexpected compose JSON output.")"
    return 1
  fi
  printf -v "$__out_var" '%s' "$array_json"
}


print_banner "🚀 Starting Stage6 network diagnostics"
print_banner "📦 Gathering compose status..."

ps_json=""
if ! capture_compose_json ps_json "${compose_cmd[@]}" ps --format json; then
  echo "Unable to retrieve Stage6 compose status (no JSON output)." >&2
  exit 1
fi

mapfile -t services < <(printf "%s" "$ps_json" | jq -r '.[].Service')
if ((${#services[@]} == 0)); then
  echo "No services discovered in Stage6 profile. Exiting."
  exit 1
fi


probe_source=""
if "${compose_cmd[@]}" exec -T grafana sh -c 'exit 0' >/dev/null 2>&1; then
  probe_source="grafana"
elif "${compose_cmd[@]}" exec -T prometheus sh -c 'exit 0' >/dev/null 2>&1; then
  probe_source="prometheus"
fi

if [[ -n "$probe_source" ]]; then
  printf "%s\n" "$(fmt_info "🔁 Using '$probe_source' container for DNS and internal HTTP probes.")"
else
  printf "%s\n" "$(fmt_warn "No grafana/prometheus probe container detected; DNS/internal health checks will be marked as N/A.")"
fi

print_banner "📡 Querying Prometheus APIs..."
prom_targets_available=false
prom_targets_rc=0
prom_targets_json=""
prom_targets_raw=$(curl -s --max-time 5 http://localhost:9095/api/v1/targets) || prom_targets_rc=$?
if (( prom_targets_rc == 0 )) && [[ -n "$prom_targets_raw" ]]; then
  if prom_targets_json=$(printf "%s" "$prom_targets_raw" | jq '.' 2>/dev/null); then
    prom_targets_available=true
  else
    prom_targets_available=false
    prom_targets_rc=2
  fi
fi

prom_metrics_available=false
prom_metrics_rc=0
prom_metrics_json=""
prom_metrics_raw=$(curl -s --max-time 5 'http://localhost:9095/api/v1/query?query=sum(rate(http_requests_total[1m]))') || prom_metrics_rc=$?
if (( prom_metrics_rc == 0 )) && [[ -n "$prom_metrics_raw" ]]; then
  if prom_metrics_json=$(printf "%s" "$prom_metrics_raw" | jq '.' 2>/dev/null); then
    prom_metrics_available=true
  else
    prom_metrics_available=false
    prom_metrics_rc=2
  fi
fi

print_banner "🧭 Running Stage6 network diagnostics matrix..."

declare -a no_host_port_list=() no_internal_port_list=() dns_fail_list=() host_health_fail_list=() internal_health_fail_list=() prom_fail_list=() failing_services_list=()
declare -A seen_no_host_port=() seen_no_internal_port=() seen_dns_fail=() seen_host_health_fail=() seen_internal_health_fail=() seen_prom_fail=() seen_failing=()

divider=$(printf '%*s' 165 '' | tr ' ' '-')
printf "\n%s\n" "$divider"
printf "%-22s | %-30s | %-24s | %-18s | %-18s | %-20s | %-24s\n" \
  "Service" "HostPorts" "InternalListeningPorts" "DNSfromGrafana" "HostHealth" "InternalHealth" "PrometheusTargetHealth"
printf "%s\n" "$divider"

for svc in "${services[@]}"; do
  svc_state=$(printf "%s" "$ps_json" | jq -r --arg svc "$svc" 'map(select(.Service==$svc)) | if length==0 then "" else .[0].State end')
  svc_state_lower=$(printf "%s" "$svc_state" | tr '[:upper:]' '[:lower:]')

  host_ports_raw=$(printf "%s" "$ps_json" | jq -r --arg svc "$svc" '
    map(select(.Service==$svc))
    | if length==0 then "-"
      else (.[0]
        | (.Publishers // []) as $pubs
        | if ($pubs | length) == 0 then "-"
          else ($pubs | map((.PublishedIP // "0.0.0.0") + ":" + ((.PublishedPort // 0)|tostring) + "->" + ((.TargetPort // 0)|tostring) + "/" + (.Protocol // "tcp")) | join(", "))
          end)
      end
  ')

  published_port=$(printf "%s" "$ps_json" | jq -r --arg svc "$svc" '
    map(select(.Service==$svc))
    | if length==0 then ""
      else (.[0]
        | (.Publishers // []) as $pubs
        | if ($pubs | length) == 0 then ""
          else ($pubs | .[0].PublishedPort // "")
          end)
      end
  ')
  target_port=$(printf "%s" "$ps_json" | jq -r --arg svc "$svc" '
    map(select(.Service==$svc))
    | if length==0 then ""
      else (.[0]
        | (.Publishers // []) as $pubs
        | if ($pubs | length) == 0 then ""
          else ($pubs | .[0].TargetPort // "")
          end)
      end
  ')
  published_ip=$(printf "%s" "$ps_json" | jq -r --arg svc "$svc" '
    map(select(.Service==$svc))
    | if length==0 then ""
      else (.[0]
        | (.Publishers // []) as $pubs
        | if ($pubs | length) == 0 then ""
          else ($pubs | .[0].PublishedIP // "0.0.0.0")
          end)
      end
  ')

  [[ "$published_port" == "null" ]] && published_port=""
  [[ "$target_port" == "null" ]] && target_port=""
  [[ "$published_ip" == "null" ]] && published_ip=""

  if [[ "$host_ports_raw" == "-" || -z "$host_ports_raw" ]]; then
    host_ports_display=$(fmt_warn "none")
    add_issue "$svc" no_host_port_list seen_no_host_port
  else
    host_ports_display=$(fmt_ok "$host_ports_raw")
  fi

  running=false
  if [[ "$svc_state_lower" == running* ]]; then
    running=true
  fi

  if ! $running; then
    internal_ports_display=$(fmt_fail "svc down")
    dns_display=$(fmt_fail "svc down")
    host_health_display=$(fmt_fail "svc down")
    internal_health_display=$(fmt_fail "svc down")
    prom_display=$(fmt_fail "svc down")
    add_issue "$svc" host_health_fail_list seen_host_health_fail
    add_issue "$svc" internal_health_fail_list seen_internal_health_fail
    add_issue "$svc" prom_fail_list seen_prom_fail
    add_issue "$svc" failing_services_list seen_failing
    printf "%-22s | %-30s | %-24s | %-18s | %-18s | %-20s | %-24s\n" \
      "$svc" "$host_ports_display" "$internal_ports_display" "$dns_display" "$host_health_display" "$internal_health_display" "$prom_display"
    continue
  fi

  internal_rc=0
  internal_cmd_output=$("${compose_cmd[@]}" exec -T "$svc" sh -c 'if command -v ss >/dev/null 2>&1; then ss -H -tln; elif command -v netstat >/dev/null 2>&1; then netstat -tnl; elif [ -f /proc/net/tcp ]; then cat /proc/net/tcp; else printf "__NO_SOCKET_TOOL__\n"; fi' 2>&1) || internal_rc=$?
  internal_cmd_output=${internal_cmd_output//$'\r'/}
  internal_ports_raw=""
  if (( internal_rc != 0 )); then
    internal_ports_display=$(fmt_fail "exec rc=$internal_rc")
    add_issue "$svc" no_internal_port_list seen_no_internal_port
    add_issue "$svc" failing_services_list seen_failing
  else
    if [[ "$internal_cmd_output" == *__NO_SOCKET_TOOL__* ]]; then
      internal_ports_display=$(fmt_warn "no-tools")
      add_issue "$svc" no_internal_port_list seen_no_internal_port
    else
      if printf "%s\n" "$internal_cmd_output" | head -n 1 | grep -qi 'local_address'; then
        internal_ports_raw=$(printf "%s\n" "$internal_cmd_output" | tail -n +2 | awk '{split($2,a,":"); print a[2]}' | while read -r hex_port; do
          [[ -z "$hex_port" ]] && continue
          printf "%d\n" "0x$hex_port"
        done | sort -n | uniq | tr '\n' ',' | sed 's/,$//')
      else
        internal_ports_raw=$(printf "%s\n" "$internal_cmd_output" | awk '
          $1 ~ /^(State|Proto|Active)$/ { next }
          NF == 0 { next }
          {
            field=""
            for(i=1;i<=NF;i++){
              if(index($i,":")>0){
                field=$i
                break
              }
            }
            if(field==""){next}
            n=split(field,a,":")
            port=a[n]
            gsub(/[^0-9]/,"",port)
            if(port!=""){ print port }
          }
        ' | sort -n | uniq | tr '\n' ',' | sed 's/,$//')
      fi

      if [[ -z "$internal_ports_raw" ]]; then
        internal_ports_display=$(fmt_fail "none")
        add_issue "$svc" no_internal_port_list seen_no_internal_port
        add_issue "$svc" failing_services_list seen_failing
      else
        internal_ports_display=$(fmt_ok "$internal_ports_raw")
      fi
    fi
  fi

  internal_port_candidate=""
  if [[ "$target_port" =~ ^[0-9]+$ ]] && (( target_port > 0 )); then
    internal_port_candidate="$target_port"
  elif [[ -n "$internal_ports_raw" ]]; then
    internal_port_candidate="${internal_ports_raw%%,*}"
  fi
  internal_port_candidate=${internal_port_candidate// /}

  if [[ "$published_port" =~ ^[0-9]+$ ]] && (( published_port > 0 )); then
    host_ip="$published_ip"
    if [[ -z "$host_ip" || "$host_ip" == "null" || "$host_ip" == "0.0.0.0" ]]; then
      host_ip="localhost"
    fi
    host_url="http://${host_ip}:${published_port}/health"
    host_health_rc=0
    host_health_code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 "$host_url") || host_health_rc=$?
    if (( host_health_rc == 0 )); then
      if [[ "$host_health_code" =~ ^2 ]]; then
        host_health_display=$(fmt_ok "$host_health_code")
      elif [[ "$host_health_code" == "000" ]]; then
        host_health_display=$(fmt_fail "conn lost")
        add_issue "$svc" host_health_fail_list seen_host_health_fail
        add_issue "$svc" failing_services_list seen_failing
      else
        host_health_display=$(fmt_fail "HTTP $host_health_code")
        add_issue "$svc" host_health_fail_list seen_host_health_fail
        add_issue "$svc" failing_services_list seen_failing
      fi
    else
      host_health_display=$(fmt_fail "curl rc=$host_health_rc")
      add_issue "$svc" host_health_fail_list seen_host_health_fail
      add_issue "$svc" failing_services_list seen_failing
    fi
  else
    host_health_display=$(fmt_warn "no-port")
  fi

  if [[ -n "$probe_source" ]]; then
    dns_rc=0
    dns_output=$("${compose_cmd[@]}" exec -T "$probe_source" sh -c "
      svc='$svc'
      if command -v getent >/dev/null 2>&1; then
        if getent hosts \"\$svc\" >/dev/null 2>&1; then
          echo OK
        else
          echo FAIL
          exit 20
        fi
      elif command -v ping >/dev/null 2>&1; then
        if ping -c1 -W1 \"\$svc\" >/dev/null 2>&1; then
          echo OK
        else
          echo FAIL
          exit 21
        fi
      elif command -v python3 >/dev/null 2>&1; then
        if python3 -c \"import socket; socket.gethostbyname('$svc')\" >/dev/null 2>&1; then
          echo OK
        else
          echo FAIL
          exit 22
        fi
      else
        echo NO_TOOL
        exit 99
      fi
    " 2>&1) || dns_rc=$?
    dns_output=$(printf "%s" "$dns_output" | tr -d '\r\n')
    if (( dns_rc == 0 )) && [[ "$dns_output" == "OK" ]]; then
      dns_display=$(fmt_ok "OK")
    elif [[ "$dns_output" == "NO_TOOL" ]]; then
      dns_display=$(fmt_warn "no-tool")
      add_issue "$svc" dns_fail_list seen_dns_fail
    else
      dns_display=$(fmt_fail "${dns_output:-FAIL}")
      add_issue "$svc" dns_fail_list seen_dns_fail
      add_issue "$svc" failing_services_list seen_failing
    fi
  else
    dns_display=$(fmt_na "no-probe")
  fi

  if [[ -n "$probe_source" && "$internal_port_candidate" =~ ^[0-9]+$ ]]; then
    internal_health_rc=0
    internal_output=$("${compose_cmd[@]}" exec -T "$probe_source" sh -c "
      PROBE_URL=\"http://$svc:$internal_port_candidate/health\"
      if command -v curl >/dev/null 2>&1; then
        ec=0
        code=\$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 \"\$PROBE_URL\") || ec=\$?
        echo \"\${code:-000}\"
        exit \$ec
      elif command -v wget >/dev/null 2>&1; then
        if wget -qO- --timeout=5 \"\$PROBE_URL\" >/dev/null 2>&1; then
          echo 200
          exit 0
        else
          echo WGETFAIL
          exit 22
        fi
      else
        echo NO_HTTP_CLIENT
        exit 99
      fi
    " 2>&1) || internal_health_rc=$?
    internal_output=$(printf "%s" "$internal_output" | tr -d '\r\n')
    if (( internal_health_rc == 0 )); then
      if [[ "$internal_output" =~ ^2 ]]; then
        internal_health_display=$(fmt_ok "$internal_output")
      elif [[ "$internal_output" == "000" || -z "$internal_output" ]]; then
        internal_health_display=$(fmt_fail "conn lost")
        add_issue "$svc" internal_health_fail_list seen_internal_health_fail
        add_issue "$svc" failing_services_list seen_failing
      else
        internal_health_display=$(fmt_fail "HTTP $internal_output")
        add_issue "$svc" internal_health_fail_list seen_internal_health_fail
        add_issue "$svc" failing_services_list seen_failing
      fi
    else
      if [[ "$internal_output" == "NO_HTTP_CLIENT" ]]; then
        internal_health_display=$(fmt_warn "no curl/wget")
        add_issue "$svc" internal_health_fail_list seen_internal_health_fail
      else
        internal_health_display=$(fmt_fail "${internal_output:-rc$internal_health_rc}")
        add_issue "$svc" internal_health_fail_list seen_internal_health_fail
        add_issue "$svc" failing_services_list seen_failing
      fi
    fi
  elif [[ -z "$probe_source" ]]; then
    internal_health_display=$(fmt_na "no-probe")
  else
    internal_health_display=$(fmt_warn "no-port")
    add_issue "$svc" no_internal_port_list seen_no_internal_port
  fi

  if [[ "$prom_targets_available" = true && "$internal_port_candidate" =~ ^[0-9]+$ ]]; then
    instance="${svc}:${internal_port_candidate}"
    prom_health=$(printf "%s" "$prom_targets_json" | jq -r --arg instance "$instance" '
      try (.data.activeTargets // [] | map(select(.labels.instance==$instance)) | if length==0 then "" else .[0].health end) catch ""
    ')
    if [[ "$prom_health" == "up" ]]; then
      prom_display=$(fmt_ok "up")
    elif [[ -z "$prom_health" ]]; then
      prom_display=$(fmt_fail "missing")
      add_issue "$svc" prom_fail_list seen_prom_fail
      add_issue "$svc" failing_services_list seen_failing
    else
      prom_display=$(fmt_fail "$prom_health")
      add_issue "$svc" prom_fail_list seen_prom_fail
      add_issue "$svc" failing_services_list seen_failing
    fi
  elif [[ "$prom_targets_available" = true ]]; then
    prom_display=$(fmt_warn "no-port")
    add_issue "$svc" prom_fail_list seen_prom_fail
  else
    if (( prom_targets_rc == 0 )); then
      prom_display=$(fmt_warn "API empty")
    else
      prom_display=$(fmt_warn "API rc=$prom_targets_rc")
    fi
  fi

  printf "%-22s | %-30s | %-24s | %-18s | %-18s | %-20s | %-24s\n" \
    "$svc" "$host_ports_display" "$internal_ports_display" "$dns_display" "$host_health_display" "$internal_health_display" "$prom_display"
done

printf "%s\n" "$divider"

if [[ "$probe_source" == "prometheus" ]]; then
  printf "\n%s\n" "$(fmt_warn "DNS/internal probes executed from 'prometheus' container (Grafana unavailable). Column label preserved for consistency.")"
elif [[ -z "$probe_source" ]]; then
  printf "\n%s\n" "$(fmt_warn "DNS/internal probes skipped; no grafana or prometheus container available.")"
fi

if [[ "$prom_targets_available" = true ]]; then
  print_banner "🎯 Prometheus active targets (job | instance | health)"
  printf "%s\n" "$prom_targets_json" | jq -r '.data.activeTargets[] | "  - \(.labels.job) | \(.labels.instance) | \(.health)"'
else
  print_banner "🎯 Prometheus targets unavailable"
  printf "%s\n" "$(fmt_warn "Targets API request failed (rc=$prom_targets_rc).")"
fi

if [[ "$prom_metrics_available" = true ]]; then
  print_banner "📈 Sample metrics query sum(rate(http_requests_total[1m]))"
  printf "%s\n" "$prom_metrics_json" | jq
else
  print_banner "📈 Metrics query unavailable"
  printf "%s\n" "$(fmt_warn "Metric query failed (rc=$prom_metrics_rc).")"
fi

print_banner "📝 Summary of potential root causes"
summary_reported=false

if ((${#no_host_port_list[@]} > 0)); then
  summary_reported=true
  printf " - %s %s\n" "$(fmt_warn "No host port mapping")" "$(list_to_string no_host_port_list)"
fi
if ((${#no_internal_port_list[@]} > 0)); then
  summary_reported=true
  printf " - %s %s\n" "$(fmt_fail "Service not listening internally")" "$(list_to_string no_internal_port_list)"
fi
if ((${#dns_fail_list[@]} > 0)); then
  summary_reported=true
  printf " - %s %s\n" "$(fmt_fail "Docker DNS resolution failed")" "$(list_to_string dns_fail_list)"
fi
if ((${#host_health_fail_list[@]} > 0)); then
  summary_reported=true
  printf " - %s %s\n" "$(fmt_fail "Host-side /health unreachable")" "$(list_to_string host_health_fail_list)"
fi
if ((${#internal_health_fail_list[@]} > 0)); then
  summary_reported=true
  printf " - %s %s\n" "$(fmt_fail "In-network /health unreachable")" "$(list_to_string internal_health_fail_list)"
fi
if ((${#prom_fail_list[@]} > 0)); then
  summary_reported=true
  printf " - %s %s\n" "$(fmt_fail "Prometheus target down/missing")" "$(list_to_string prom_fail_list)"
fi
if ! $summary_reported; then
  printf "%s\n" "$(fmt_ok "No discrepancies detected across Stage6 services.")"
fi

if ((${#failing_services_list[@]} > 0)); then
  print_banner "🛠️ Recommended next steps"
  echo "For affected services, collect logs and restart if needed:"
  for svc in "${failing_services_list[@]}"; do
    printf "  [%s]\n" "$svc"
    printf "    - %s logs %s --tail 200\n" "$compose_base_cmd" "$svc"
    printf "    - %s restart %s\n" "$compose_base_cmd" "$svc"
  done
fi

printf "\n%s%s%s Completed in %ss\n" "$bold" "✅ Diagnostics complete." "$reset" "$SECONDS"

# Exit with non-zero if critical services failed
exit_code=0
if ((${#failing_services_list[@]} > 0)); then
  # Allow known non-critical services to be down
  critical_failing=()
  for svc in "${failing_services_list[@]}"; do
    case "$svc" in
      alertmanager-bot|zakupai-bot|db-backup|vault) ;;  # known optional
      *) critical_failing+=("$svc") ;;
    esac
  done
  if ((${#critical_failing[@]} > 0)); then
    printf "\n%s\n" "$(fmt_fail "Critical services unhealthy: $(list_to_string critical_failing)")"
    exit_code=1
  fi
fi

exit $exit_code
