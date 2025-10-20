| Check                          | Result            | Details |
| ------------------------------ | ----------------- | ------- |
| Container ID                   | 5e24e09f5542      | `prom/prometheus:v2.45.0` (`zakupai-prometheus`) from `docker ps` |
| Compose Profile                | stage6            | Listed in `docker compose --profile stage6 ps` |
| Config path (inside container) | /etc/prometheus/prometheus.yml | `--config.file` flag present in container command |
| MD5 Match                      | ✅                | Host `a558715b3dcc32648e9417817ced186b` equals container hash |
| Active Targets                 | 16                | `/api/v1/targets` reports 16 active targets |
| Loaded Jobs                    | 15 jobs           | billing-service, blackbox-http, cadvisor, calc-service, doc-service, embedding-api, etl-service, gateway, goszakup-api, nginx, node-exporter, prometheus, risk-engine, web-ui, zakupai-bot |
| Systemd Prometheus             | Running           | `prometheus.service` active (PID 962) using `/etc/prometheus/prometheus.yml` |
| Port 9090 Owner                | prometheus PID 962 | Host systemd Prometheus bound to 0.0.0.0:9090 (`ss -ltnp`) |
| Promtool Validation            | ✅                | `promtool check config /etc/prometheus/prometheus.yml` succeeded (2 rule files, 9 rules) |

## Final Diagnosis

- **Active instance:** Both the Compose service (`zakupai-prometheus`) and a host-level `prometheus.service` are running. Grafana’s datasource (`http://prometheus:9090`) reaches the Compose instance and already sees 16 targets (`docker exec zakupai-grafana wget -qO- ... | jq`).
- **Why only 2 targets appeared:** Inspecting `http://localhost:9090` hits the host systemd Prometheus, which still ships with the stock `/etc/prometheus/prometheus.yml` containing only `prometheus` and `node` scrapes. That instance reports “2/16 targets” while the containerized instance correctly scrapes all 16 endpoints.
- **Fix to apply:** Stop and disable the host service so it no longer occupies port 9090, then keep the Compose service running:
  1. `sudo systemctl stop prometheus && sudo systemctl disable prometheus`
  2. `docker compose --profile stage6 up -d zakupai-prometheus` (restarts the intended Stage6 Prometheus if needed)

Once the host service is removed, `http://localhost:9090` can be published by the container if desired, and all Grafana dashboards will align with the container’s fully populated target list.
