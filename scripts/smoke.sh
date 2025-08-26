#!/bin/bash
curl -s -X POST http://localhost:8001/calc/vat -H 'content-type: application/json' -d '{"amount":112000,"vat_rate":12,"include_vat":true,"lot_id":1}'
curl -s -X POST http://localhost:8001/calc/margin -H 'content-type: application/json' -d '{"lot_price":1500000,"cost":420000,"logistics":50000,"vat_rate":12,"price_includes_vat":true,"lot_id":1}'
curl -s -X POST http://localhost:8001/calc/penalty -H 'content-type: application/json' -d '{"contract_sum":1500000,"days_overdue":7,"daily_rate_pct":0.1,"lot_id":1}'
curl -s -X POST http://localhost:8002/risk/score -H 'content-type: application/json' -d '{"lot_id":1}'
curl -s http://localhost:8002/risk/explain/1
curl -s -X POST http://localhost:8003/tldr -H 'content-type: application/json' -d '{"lot_id":1}' | jq '.lines|length'
curl -s -X POST http://localhost:8003/letters/generate -H 'content-type: application/json' -d '{"template":"guarantee","context":{"supplier_name":"ТОО Ромашка","lot_title":"Поставка картриджей","lot_id":1,"contact":"+7 777 000 00 00"}}' | jq '.html|length'
curl -s -X POST http://localhost:8003/render/html -H 'content-type: application/json' -d '{"template":"tldr","context":{"title":"Демо","lines":["Строка 1","Строка 2"]}}' | jq '.html|length'
curl -s -X POST http://localhost:8003/render/pdf -H 'content-type: application/json' -d '{"template":"tldr","context":{"title":"PDF Smoke","lines":["Line1","Line2"]}}' > /tmp/smoke.pdf && test $(stat -c%s /tmp/smoke.pdf) -gt 1000 && echo "PDF smoke OK" || echo "PDF smoke FAIL"
curl -s -X POST http://localhost:8004/index -H 'content-type: application/json' -d '{"ref_id":"smoke:1","text":"Test embedding document for smoke test"}' | jq '.id'
curl -s -X POST http://localhost:8004/search -H 'content-type: application/json' -d '{"query":"test document", "top_k": 1}' | jq '.total_found'
docker exec zakupai-db psql -U zakupai -d zakupai -c "SELECT count(*) FROM finance_calcs;"
docker exec zakupai-db psql -U zakupai -d zakupai -c "SELECT count(*) FROM risk_evaluations;"
docker exec zakupai-db psql -U zakupai -d zakupai -c "SELECT count(*) FROM embeddings;"