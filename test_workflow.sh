#!/bin/bash

# Тестирование workflow для поиска лотов госзакупок РК

echo "Тестирование поиска по слову 'лак':"
curl -X POST https://n8n.exomind.site/webhook/goszakup-search \
  -H "Content-Type: application/json" \
  -d '{"query":"лак"}' | jq .

echo ""
echo "Тестирование поиска по слову 'мебель':"
curl -X POST https://n8n.exomind.site/webhook/goszakup-search \
  -H "Content-Type: application/json" \
  -d '{"query":"мебель"}' | jq .

echo ""
echo "Тестирование поиска по слову 'компьютер':"
curl -X POST https://n8n.exomind.site/webhook/goszakup-search \
  -H "Content-Type: application/json" \
  -d '{"query":"компьютер"}' | jq .
