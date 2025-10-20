## Prometheus Target Audit

| Job              | Instance                        | `service` label | Health |
| ---------------- | -------------------------------- | --------------- | ------ |
| billing-service  | billing-service:8000             | billing         | up     |
| blackbox-http    | http://gateway:80/health         | —               | up     |
| blackbox-http    | https://ows.goszakup.gov.kz/v3/ru/ping | —         | up     |
| cadvisor         | cadvisor:8080                    | —               | up     |
| calc-service     | calc-service:8000                | calc            | up     |
| doc-service      | doc-service:8000                 | doc             | up     |
| embedding-api    | embedding-api:8000               | embedding       | up     |
| etl-service      | etl-service:8000                 | etl             | up     |
| gateway          | gateway:80                       | gateway         | up     |
| goszakup-api     | goszakup-api:8001                | goszakup        | up     |
| nginx            | nginx-exporter:9113              | nginx-exporter  | up     |
| node-exporter    | node-exporter-stage6:9100        | —               | up     |
| prometheus       | prometheus:9090                  | —               | up     |
| risk-engine      | risk-engine:8000                 | risk            | up     |
| web-ui           | web-ui:8000                      | web-ui          | up     |
| zakupai-bot      | zakupai-bot:8081                 | bot             | up     |

## HTTP Metric Sampling Per Service

All FastAPI services expose the metric families (`http_requests_total`, `http_request_duration_seconds_*`, etc.), but only the `gateway` target currently emits time series samples. Example excerpts gathered via the Prometheus container:

| Service     | Sample observation (`http_requests_total`) | Finding |
| ----------- | ------------------------------------------ | ------- |
| calc-service | Only `# HELP` / `# TYPE` lines present; no samples exported | No traffic has hit the service → counter never created |
| risk-engine | Same as above                              | No traffic observed |
| doc-service | Same as above                              | No traffic observed |
| embedding-api | Same as above                            | No traffic observed |
| etl-service | Same as above                              | No traffic observed |
| billing-service | Same as above                          | No traffic observed |
| goszakup-api | Same as above                             | No traffic observed |
| web-ui      | Same as above                              | No traffic observed |
| zakupai-bot | Metric family absent entirely              | Bot exposes other metrics only |
| gateway     | `http_requests_total{method="GET",endpoint="/stub_status",status_code="200",service="gateway"} 653` | Active sample stream present |

Consequence: PromQL queries used in Grafana panels such as `sum by (service) (rate(http_requests_total{service=~"$service"}[5m]))` return empty vectors for every service except `gateway`. The fallback `or vector(0)` does not attach service labels, so Grafana renders “No data” for stat/time-series panels expecting per-service series.

## PromQL Consistency Checks

- `http://localhost:9090/api/v1/series?match[]=up` → all 16 targets reported with `job` **and** short-form `service` labels (e.g., `service="calc"`).
- `http://localhost:9090/api/v1/series?match[]=http_requests_total` → only the `gateway` series is present.
- `POST /api/v1/query` with `query=up{job="calc-service"}` → returns `value=1`, confirming the scrape succeeds despite Grafana’s red tiles.
- `POST /api/v1/query` with `query=max by (job) (http_requests_total)` → returns data solely for `job="gateway"`.

This proves that service dashboards expecting request-rate/latency data are looking at the correct label set, but the underlying metrics do not exist for most services.

## Grafana Dashboards & Queries

- Datasource (`/etc/grafana/provisioning/datasources/datasources.yml`) points to `http://prometheus:9090` (Stage6 container alias).
- API dashboards (`monitoring/grafana/provisioning/dashboards/apis/*.json`) rely on:
  - `sum by (service) (rate(http_requests_total{service=~"$service"}[5m]))`
  - `sum by (service) (rate(http_requests_total{service=~"$service", status_code=~"5.."}[5m]))`
  - `histogram_quantile(0.95, sum by (le, service) (rate(http_request_duration_seconds_bucket{service=~"$service"}[5m])))`
- Because only the `gateway` job emits these series, templated panels for calc-service, risk-engine, doc-service, etc., evaluate to empty result sets → Grafana marks them as red / “No data”.

## Gateway & ETL Sanity Checks

- `docker inspect zakupai-gateway` shows the healthcheck is failing (`Status: unhealthy`, `ExitCode: 8`). Logs reveal repeated `HEAD /health` requests returning HTTP 405. The application only accepts GET, so the built-in healthcheck (`wget --spider http://localhost/health`) never succeeds. Actual GET health calls from other containers return `{"status":"ok"}`.
- ETL container can reach `https://ows.goszakup.gov.kz/v3/ru/ping` (returns expected 404 JSON), indicating outbound dependencies are reachable.
- Blackbox exporter probes for gateway and goszakup API both report `probe_success=1`.

## Root Cause & Recommendations

| Finding | Diagnosis | Confidence | Recommended action |
| ------- | --------- | ---------- | ------------------ |
| Service dashboards red / “No data” | Prometheus scrapes succeed, but FastAPI apps haven’t served any requests since startup, so `http_requests_total` and latency histograms never create samples (except gateway). Grafana queries therefore match no series. | High | Seed synthetic traffic (smoke tests or load generators) for each Stage6 API, or adjust dashboards to fall back to `up{job="…"}` / expose `service` label via recording rules so zero activity still renders. |
| Gateway container marked unhealthy | Healthcheck performs HTTP HEAD; application rejects HEAD on `/health`, causing perpetual failures despite healthy service. | High | Update Compose healthcheck to use `curl -f http://localhost/health` (GET) or enable HEAD support in the app. |
| Prometheus `service` label naming | Relabel rules set `service` to short tokens (`calc`, `risk`, etc.), which align with Grafana variable values. No mismatch detected. | Medium | Document label scheme; ensure new dashboards reference short-form values. |

### Summary

Stage6 Prometheus is healthy and scrapes every job, but Grafana’s service-level panels rely on request-rate and latency metrics that never materialize because no client traffic hits those FastAPI services. Injecting minimal HTTP requests (or adjusting dashboard logic to tolerate idle services) will restore green status. Additionally, fix the gateway healthcheck (use GET) to clear the “unhealthy” flag, avoiding confusion during future audits.
