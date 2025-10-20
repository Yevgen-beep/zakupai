# tender-finance-calc

n8n нода для финансовых расчётов по тендерам через ZakupAI calc-service.

## Установка и использование

```bash
# Скопировать в n8n контейнер
docker cp ./tender-finance-calc zakupai-n8n:/home/node/.n8n/custom/

# В контейнере
cd /home/node/.n8n/custom/tender-finance-calc
npm install && npm run build

# Перезапустить n8n
docker restart zakupai-n8n
```

## Функциональность

**3 операции:**

- Calculate VAT (НДС 12%)
- Calculate Margin (прибыль, ROI)
- Calculate Penalty (пени по контракту)

**API endpoints:**

- POST /calc/vat
- POST /calc/margin
- POST /calc/penalty

## Пример workflow

1. Start → Tender Finance Calc → Email/Webhook
1. HTTP Request (лоты) → Tender Finance Calc → Filter profitable
1. Schedule → Tender Finance Calc → Database save
