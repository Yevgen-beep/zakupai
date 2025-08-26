#!/bin/bash
curl -s -X POST http://localhost:8001/calc/vat -H 'content-type: application/json' -d '{"amount":112000,"vat_rate":12,"include_vat":true,"lot_id":1}'
curl -s -X POST http://localhost:8001/calc/margin -H 'content-type: application/json' -d '{"lot_price":1500000,"cost":420000,"logistics":50000,"vat_rate":12,"price_includes_vat":true,"lot_id":1}'
curl -s -X POST http://localhost:8001/calc/penalty -H 'content-type: application/json' -d '{"contract_sum":1500000,"days_overdue":7,"daily_rate_pct":0.1,"lot_id":1}'
curl -s -X POST http://localhost:8002/risk/score -H 'content-type: application/json' -d '{"lot_id":1}'
curl -s http://localhost:8002/risk/explain/1
docker exec zakupai-db psql -U zakupai -d zakupai -c "SELECT count(*) FROM finance_calcs;"
docker exec zakupai-db psql -U zakupai -d zakupai -c "SELECT count(*) FROM risk_evaluations;"
