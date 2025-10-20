| Check                                | Result         | Comment |
| ------------------------------------ | -------------- | ------- |
| Port 9090 free                       | ✅              | `ss -ltnp | grep :9090` returned no listeners |
| zakupai-prometheus container running | ✅              | `docker compose --profile stage6 up -d prometheus` and `docker ps` show container `5e24e09f5542` up |
| Config validation                    | ✅              | `promtool check config /etc/prometheus/prometheus.yml` succeeded (2 rule files loaded) |
| Active targets count                 | 16             | `/api/v1/targets` reports 16 active targets |
| Loaded jobs                          | billing-service, blackbox-http, cadvisor, calc-service, doc-service, embedding-api, etl-service, gateway, goszakup-api, nginx, node-exporter, prometheus, risk-engine, web-ui, zakupai-bot | Matches expected Stage6 scrape set |
| Scrape errors                        | none           | Last 30 log lines contain no scrape failures |

Stage6 Prometheus fully operational. Host-level Prometheus removed. Containerized instance validated with 16 active targets and full Grafana visibility restored.
