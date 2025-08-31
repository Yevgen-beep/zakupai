# n8n и Flowise Integration

## Обзор

ZakupAI интегрируется с n8n и Flowise для создания визуальных AI-воркфлоу и автоматизации бизнес-процессов. Эта интеграция позволяет пользователям создавать сложные пайплайны обработки тендеров без программирования.

## Архитектура интеграции

```
┌─────────────────────────────────────────────────────────────────┐
│                    AI Automation Stack                          │
├─────────────────────────────────────────────────────────────────┤
│ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐                 │
│ │   Flowise   │ │     n8n     │ │  ZakupAI    │                 │
│ │  :3000      │ │   :5678     │ │  Services   │                 │
│ │             │ │             │ │             │                 │
│ │ Visual AI   │ │ Workflow    │ │ • Calc      │                 │
│ │ Workflows   │ │ Engine      │ │ • Risk      │                 │
│ │             │ │             │ │ • Doc       │                 │
│ └──────┬──────┘ └──────┬──────┘ │ • Billing   │                 │
│        │               │        │ • Embedding │                 │
│        └───────────────┼────────┘             │                 │
│                        │                      │                 │
├────────────────────────┼──────────────────────┼─────────────────┤
│              ┌─────────▼──────┐    ┌─────────▼──────┐          │
│              │ Custom Nodes   │    │ Custom Tools   │          │
│              │ (n8n)         │    │ (Flowise)      │          │
│              └───────────────┘    └────────────────┘          │
└─────────────────────────────────────────────────────────────────┘
```

## n8n Custom Nodes

### 1. GosZakup-RK Node

**Описание:** Интеграция с порталом государственных закупок РК

**Файл:** `n8n-nodes/goszakup-rk/GosZakupRK.node.ts`

```typescript
import {
    IExecuteFunctions,
    INodeExecutionData,
    INodeType,
    INodeTypeDescription,
} from 'n8n-workflow';

export class GosZakupRK implements INodeType {
    description: INodeTypeDescription = {
        displayName: 'GosZakup RK',
        name: 'gosZakupRK',
        icon: 'file:goszakup.svg',
        group: ['transform'],
        version: 1,
        description: 'Интеграция с порталом госзакупок РК',
        defaults: {
            name: 'GosZakup RK',
        },
        inputs: ['main'],
        outputs: ['main'],
        properties: [
            {
                displayName: 'Operation',
                name: 'operation',
                type: 'options',
                options: [
                    {
                        name: 'Поиск тендеров',
                        value: 'searchTenders',
                    },
                    {
                        name: 'Получить лот',
                        value: 'getLot',
                    },
                    {
                        name: 'Мониторинг лотов',
                        value: 'monitorLots',
                    },
                ],
                default: 'searchTenders',
            },
            {
                displayName: 'Lot ID',
                name: 'lotId',
                type: 'string',
                displayOptions: {
                    show: {
                        operation: ['getLot'],
                    },
                },
                default: '',
                description: 'ID лота для получения данных',
            },
            {
                displayName: 'Search Query',
                name: 'searchQuery',
                type: 'string',
                displayOptions: {
                    show: {
                        operation: ['searchTenders'],
                    },
                },
                default: '',
                description: 'Поисковый запрос для тендеров',
            },
        ],
    };

    async execute(this: IExecuteFunctions): Promise<INodeExecutionData[][]> {
        const items = this.getInputData();
        const returnData: INodeExecutionData[] = [];

        for (let i = 0; i < items.length; i++) {
            const operation = this.getNodeParameter('operation', i) as string;

            try {
                if (operation === 'getLot') {
                    const lotId = this.getNodeParameter('lotId', i) as string;

                    // Вызов ZakupAI API для получения данных лота
                    const response = await this.helpers.request({
                        method: 'GET',
                        url: `https://goszakup.gov.kz/ru/announce/index/${lotId}`,
                        json: true,
                    });

                    returnData.push({
                        json: {
                            lot_id: lotId,
                            title: response.title,
                            price: response.price,
                            customer: response.customer,
                            deadline: response.deadline,
                            status: response.status,
                            fetched_at: new Date().toISOString(),
                        },
                    });

                } else if (operation === 'searchTenders') {
                    const searchQuery = this.getNodeParameter('searchQuery', i) as string;

                    // Поиск тендеров через API
                    const response = await this.helpers.request({
                        method: 'GET',
                        url: `https://goszakup.gov.kz/api/v1/search`,
                        qs: {
                            query: searchQuery,
                            limit: 50,
                        },
                        json: true,
                    });

                    response.data.forEach((tender: any) => {
                        returnData.push({
                            json: {
                                lot_id: tender.id,
                                title: tender.title,
                                price: tender.price,
                                customer: tender.customer.name,
                                publication_date: tender.published_at,
                            },
                        });
                    });

                } else if (operation === 'monitorLots') {
                    // Мониторинг "горячих" лотов
                    const hotLots = await this.helpers.request({
                        method: 'GET',
                        url: 'http://zakupai-gateway/api/lots/hot',
                        headers: {
                            'X-API-Key': process.env.ZAKUPAI_API_KEY,
                        },
                        json: true,
                    });

                    hotLots.forEach((lot: any) => {
                        returnData.push({
                            json: {
                                ...lot,
                                alert_type: 'hot_lot',
                                checked_at: new Date().toISOString(),
                            },
                        });
                    });
                }

            } catch (error) {
                if (this.continueOnFail()) {
                    returnData.push({
                        json: { error: error.message },
                    });
                } else {
                    throw error;
                }
            }
        }

        return [returnData];
    }
}
```

### 2. Price Aggregator Node

**Описание:** Сбор рыночных цен с разных источников

**Файл:** `n8n-nodes/price-aggregator/PriceAggregator.node.ts`

```typescript
export class PriceAggregator implements INodeType {
    description: INodeTypeDescription = {
        displayName: 'Price Aggregator',
        name: 'priceAggregator',
        icon: 'file:price.svg',
        group: ['transform'],
        version: 1,
        description: 'Агрегация рыночных цен из разных источников',
        properties: [
            {
                displayName: 'Source',
                name: 'source',
                type: 'options',
                options: [
                    { name: '1688.com', value: '1688' },
                    { name: 'Alibaba', value: 'alibaba' },
                    { name: 'Kaspi Магазин', value: 'kaspi' },
                    { name: 'Manual Input', value: 'manual' },
                ],
                default: '1688',
            },
            {
                displayName: 'Product SKU',
                name: 'sku',
                type: 'string',
                default: '',
                description: 'Артикул товара для поиска цены',
            },
        ],
    };

    async execute(this: IExecuteFunctions): Promise<INodeExecutionData[][]> {
        const items = this.getInputData();
        const returnData: INodeExecutionData[] = [];

        for (let i = 0; i < items.length; i++) {
            const source = this.getNodeParameter('source', i) as string;
            const sku = this.getNodeParameter('sku', i) as string;

            try {
                // Вызов ZakupAI Price API
                const priceData = await this.helpers.request({
                    method: 'POST',
                    url: 'http://zakupai-gateway/api/prices/aggregate',
                    headers: {
                        'X-API-Key': process.env.ZAKUPAI_API_KEY,
                    },
                    json: {
                        source: source,
                        sku: sku,
                        search_alternatives: true,
                    },
                });

                returnData.push({
                    json: {
                        sku: sku,
                        source: source,
                        prices: priceData.prices,
                        min_price: priceData.min_price,
                        max_price: priceData.max_price,
                        avg_price: priceData.avg_price,
                        currency: priceData.currency,
                        found_items: priceData.found_items,
                        updated_at: new Date().toISOString(),
                    },
                });

            } catch (error) {
                if (this.continueOnFail()) {
                    returnData.push({
                        json: {
                            sku: sku,
                            source: source,
                            error: error.message
                        },
                    });
                } else {
                    throw error;
                }
            }
        }

        return [returnData];
    }
}
```

### 3. Tender Finance Calculator Node

**Описание:** Финансовые расчеты для тендеров

**Возможности:**

- Расчет НДС
- Анализ маржинальности
- Расчет пени и штрафов
- ROI анализ

### 4. Lot Risk Scoring Node

**Описание:** Оценка рисков участия в лоте

**Возможности:**

- Анализ заказчика
- Проверка конкурентов
- Оценка технических требований
- Расчет вероятности выигрыша

### 5. Doc Builder Node

**Описание:** Автоматическая генерация документов

**Возможности:**

- Коммерческие предложения
- Техническое задание
- Жалобы и возражения
- Договоры и дополнительные соглашения

## Flowise Custom Tools

### 1. Lot Reader Tool

**Описание:** Чтение и анализ текста тендера

**Файл:** `flowise-tools/lot-reader.js`

```javascript
class LotReaderTool {
    constructor() {
        this.name = "lot-reader";
        this.description = "Читает и анализирует тендерную документацию";
    }

    async _call(input) {
        const { lotId, analysisType = "full" } = JSON.parse(input);

        try {
            // Получаем данные лота
            const response = await fetch(`http://zakupai-gateway/api/lots/${lotId}`, {
                headers: {
                    'X-API-Key': process.env.ZAKUPAI_API_KEY,
                }
            });

            const lotData = await response.json();

            // Вызываем Doc Service для TL;DR
            const tldrResponse = await fetch('http://doc-service:8000/tldr', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-API-Key': process.env.ZAKUPAI_API_KEY,
                },
                body: JSON.stringify({
                    lot_id: lotId,
                    include_risks: analysisType === "full",
                    language: "ru"
                })
            });

            const tldr = await tldrResponse.json();

            return {
                lot_id: lotId,
                title: lotData.title,
                summary: tldr.summary,
                key_requirements: tldr.key_requirements,
                estimated_price: lotData.price,
                deadline: lotData.deadline,
                complexity_score: tldr.complexity_score,
                recommended_action: tldr.recommended_action
            };

        } catch (error) {
            throw new Error(`Lot Reader failed: ${error.message}`);
        }
    }
}

module.exports = { LotReaderTool };
```

### 2. Risk Explain Tool

**Описание:** Объяснение рисков участия в тендере

**Файл:** `flowise-tools/risk-explain.js`

```javascript
class RiskExplainTool {
    constructor() {
        this.name = "risk-explain";
        this.description = "Объясняет риски участия в тендере и дает рекомендации";
    }

    async _call(input) {
        const { lotId, riskCategories = "all" } = JSON.parse(input);

        try {
            // Получаем риск-анализ
            const riskResponse = await fetch('http://risk-engine:8000/risk/explain/' + lotId, {
                headers: {
                    'X-API-Key': process.env.ZAKUPAI_API_KEY,
                }
            });

            const riskData = await riskResponse.json();

            // Форматируем объяснения для LLM
            const explanation = {
                overall_risk_score: riskData.score,
                risk_level: this.getRiskLevel(riskData.score),
                detailed_risks: {
                    customer_risk: {
                        score: riskData.customer_risk,
                        explanation: riskData.customer_explanation,
                        mitigation: riskData.customer_mitigation
                    },
                    technical_risk: {
                        score: riskData.technical_risk,
                        explanation: riskData.technical_explanation,
                        mitigation: riskData.technical_mitigation
                    },
                    financial_risk: {
                        score: riskData.financial_risk,
                        explanation: riskData.financial_explanation,
                        mitigation: riskData.financial_mitigation
                    }
                },
                recommendations: riskData.recommendations,
                red_flags: riskData.red_flags,
                green_flags: riskData.green_flags
            };

            return explanation;

        } catch (error) {
            throw new Error(`Risk Explain failed: ${error.message}`);
        }
    }

    getRiskLevel(score) {
        if (score < 0.3) return "Низкий";
        if (score < 0.7) return "Средний";
        return "Высокий";
    }
}

module.exports = { RiskExplainTool };
```

### 3. Finance Calculator Tool

**Описание:** Финансовые расчеты и анализ рентабельности

**Файл:** `flowise-tools/finance-calc.js`

```javascript
class FinanceCalculatorTool {
    constructor() {
        this.name = "finance-calc";
        this.description = "Производит финансовые расчеты для тендера";
    }

    async _call(input) {
        const {
            lotId,
            costPrice,
            proposedPrice,
            vatRate = 0.12,
            calculationType = "full"
        } = JSON.parse(input);

        try {
            const calculations = {};

            // НДС расчеты
            if (calculationType === "full" || calculationType === "vat") {
                const vatResponse = await fetch('http://calc-service:8000/calc/vat', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-API-Key': process.env.ZAKUPAI_API_KEY,
                    },
                    body: JSON.stringify({
                        amount: proposedPrice,
                        vat_rate: vatRate
                    })
                });
                calculations.vat = await vatResponse.json();
            }

            // Маржа и прибыль
            if (calculationType === "full" || calculationType === "margin") {
                const marginResponse = await fetch('http://calc-service:8000/calc/margin', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-API-Key': process.env.ZAKUPAI_API_KEY,
                    },
                    body: JSON.stringify({
                        cost_price: costPrice,
                        selling_price: proposedPrice,
                        quantity: 1
                    })
                });
                calculations.margin = await marginResponse.json();
            }

            // Дополнительные расчеты
            calculations.roi = ((proposedPrice - costPrice) / costPrice * 100).toFixed(2);
            calculations.breakeven_point = costPrice;
            calculations.profit_margin_percent = (((proposedPrice - costPrice) / proposedPrice) * 100).toFixed(2);

            return {
                lot_id: lotId,
                financial_summary: {
                    cost_price: costPrice,
                    proposed_price: proposedPrice,
                    gross_profit: proposedPrice - costPrice,
                    roi_percent: calculations.roi,
                    profit_margin_percent: calculations.profit_margin_percent
                },
                vat_details: calculations.vat,
                margin_analysis: calculations.margin,
                recommendation: this.getRecommendation(calculations.roi)
            };

        } catch (error) {
            throw new Error(`Finance Calculator failed: ${error.message}`);
        }
    }

    getRecommendation(roi) {
        const roiNum = parseFloat(roi);
        if (roiNum > 30) return "Отличная рентабельность - рекомендуем участие";
        if (roiNum > 15) return "Хорошая рентабельность - участие оправдано";
        if (roiNum > 5) return "Низкая рентабельность - требуется анализ рисков";
        return "Убыточный проект - не рекомендуем участие";
    }
}

module.exports = { FinanceCalculatorTool };
```

### 4. Template Generator Tool

**Описание:** Генерация документов и шаблонов

**Возможности:**

- Коммерческие предложения
- Технические спецификации
- Сопроводительные письма
- Жалобы и возражения

## Примеры Workflow

### 1. Автоматический анализ нового лота

```json
{
  "name": "Auto Lot Analysis",
  "nodes": [
    {
      "id": "trigger",
      "type": "n8n-nodes-base.cron",
      "parameters": {
        "triggerTimes": {
          "item": [
            {
              "hour": 9,
              "minute": 0
            }
          ]
        }
      }
    },
    {
      "id": "fetch-new-lots",
      "type": "goszakup-rk",
      "parameters": {
        "operation": "searchTenders",
        "searchQuery": "программное обеспечение"
      }
    },
    {
      "id": "filter-interesting",
      "type": "n8n-nodes-base.function",
      "parameters": {
        "functionCode": "// Фильтруем интересные лоты\nconst items = $input.all();\nconst filtered = items.filter(item => {\n  const price = parseFloat(item.json.price);\n  return price >= 500000 && price <= 10000000;\n});\nreturn filtered;"
      }
    },
    {
      "id": "analyze-risk",
      "type": "lot-risk-scoring",
      "parameters": {
        "lotId": "={{ $json.lot_id }}",
        "analysisDepth": "full"
      }
    },
    {
      "id": "calculate-finances",
      "type": "tender-finance-calc",
      "parameters": {
        "lotId": "={{ $json.lot_id }}",
        "estimatedCost": "={{ $json.price * 0.7 }}",
        "proposedPrice": "={{ $json.price }}"
      }
    },
    {
      "id": "generate-report",
      "type": "doc-builder",
      "parameters": {
        "template": "lot_analysis_report",
        "data": {
          "lot_data": "={{ $('fetch-new-lots').item.json }}",
          "risk_analysis": "={{ $('analyze-risk').item.json }}",
          "financial_calc": "={{ $('calculate-finances').item.json }}"
        }
      }
    },
    {
      "id": "send-notification",
      "type": "n8n-nodes-base.telegram",
      "parameters": {
        "chatId": "@zakupai_alerts",
        "text": "🎯 Найден интересный лот:\n\nЛот: {{ $('fetch-new-lots').item.json.title }}\nЦена: {{ $('fetch-new-lots').item.json.price }} ₸\nРиск: {{ $('analyze-risk').item.json.risk_level }}\nROI: {{ $('calculate-finances').item.json.roi_percent }}%\n\n📊 Подробный отчет: {{ $('generate-report').item.json.report_url }}"
      }
    }
  ],
  "connections": {
    "trigger": { "main": [["fetch-new-lots"]] },
    "fetch-new-lots": { "main": [["filter-interesting"]] },
    "filter-interesting": { "main": [["analyze-risk"]] },
    "analyze-risk": { "main": [["calculate-finances"]] },
    "calculate-finances": { "main": [["generate-report"]] },
    "generate-report": { "main": [["send-notification"]] }
  }
}
```

### 2. Flowise AI Agent для анализа лотов

```json
{
  "name": "Lot Analysis AI Agent",
  "description": "Интеллектуальный агент для анализа тендерных лотов",
  "chatflow": {
    "nodes": [
      {
        "id": "llm",
        "type": "ChatOpenAI",
        "data": {
          "model": "gpt-4",
          "temperature": 0.1,
          "systemMessage": "Ты эксперт по государственным закупкам. Анализируй лоты и давай рекомендации по участию."
        }
      },
      {
        "id": "lotReader",
        "type": "CustomTool",
        "data": {
          "name": "lot-reader",
          "description": "Читает и анализирует тендерную документацию"
        }
      },
      {
        "id": "riskExplain",
        "type": "CustomTool",
        "data": {
          "name": "risk-explain",
          "description": "Объясняет риски участия в тендере"
        }
      },
      {
        "id": "financeCalc",
        "type": "CustomTool",
        "data": {
          "name": "finance-calc",
          "description": "Производит финансовые расчеты для тендера"
        }
      }
    ],
    "edges": [
      {
        "source": "llm",
        "target": "lotReader"
      },
      {
        "source": "llm",
        "target": "riskExplain"
      },
      {
        "source": "llm",
        "target": "financeCalc"
      }
    ]
  },
  "example_conversation": [
    {
      "user": "Проанализируй лот 12345 на участие",
      "assistant": "Анализирую лот 12345...\n\n*Использует lot-reader*\n📋 Основная информация:\n- Название: Разработка веб-приложения\n- Цена: 2,500,000 ₸\n- Срок: 45 дней\n- Заказчик: АО \"Казпочта\"\n\n*Использует risk-explain*\n⚠️ Анализ рисков:\n- Общий риск: Средний (0.45)\n- Риск заказчика: Низкий - надежный государственный заказчик\n- Технический риск: Средний - требования стандартные\n- Финансовый риск: Низкий - цена адекватная\n\n*Использует finance-calc*\n💰 Финансовый анализ:\n- При себестоимости 1,800,000 ₸:\n- Валовая прибыль: 700,000 ₸\n- ROI: 38.89%\n- Рентабельность: 28%\n\n✅ **Рекомендация**: Участие в лоте рекомендуется. Хорошая рентабельность при умеренных рисках."
    }
  ]
}
```

## Установка и настройка

### Docker конфигурация

**n8n service в docker-compose.yml:**

```yaml
n8n:
  image: n8nio/n8n:1.105.4
  container_name: zakupai-n8n
  ports:
    - "5678:5678"
  volumes:
    - n8n_data:/home/node/.n8n
    - ./n8n-nodes:/opt/n8n-nodes:ro
  environment:
    - GENERIC_TIMEZONE=Asia/Almaty
    - N8N_BASIC_AUTH_ACTIVE=false
    - ZAKUPAI_API_KEY=${ZAKUPAI_API_KEY}
    - N8N_CUSTOM_EXTENSIONS=/opt/n8n-nodes
  networks:
    - ai-network
    - zakupai-network
```

**Flowise service в docker-compose.yml:**

```yaml
flowise:
  image: flowiseai/flowise
  container_name: zakupai-flowise
  ports:
    - "3000:3000"
  volumes:
    - flowise_data:/root/.flowise
    - ./flowise-tools:/opt/flowise_tools:ro
  environment:
    - FLOWISE_USERNAME=admin
    - FLOWISE_PASSWORD=admin123
    - ZAKUPAI_API_KEY=${ZAKUPAI_API_KEY}
    - CUSTOM_TOOL_PATH=/opt/flowise_tools
  networks:
    - ai-network
    - zakupai-network
```

### Установка custom nodes

```bash
# n8n custom nodes
cd n8n-nodes
npm install
npm run build
npm link

# В контейнере n8n
npm link zakupai-n8n-nodes

# Flowise custom tools
cd flowise-tools
npm install
npm run build
```

## Мониторинг и алерты

### Метрики workflow

```javascript
// Кастомные метрики для n8n workflows
const prometheus = require('prom-client');

const workflowExecutions = new prometheus.Counter({
    name: 'n8n_workflow_executions_total',
    help: 'Total number of workflow executions',
    labelNames: ['workflow_name', 'status']
});

const workflowDuration = new prometheus.Histogram({
    name: 'n8n_workflow_duration_seconds',
    help: 'Workflow execution duration',
    labelNames: ['workflow_name']
});
```

### Уведомления об ошибках

```json
{
  "name": "Error Notification Workflow",
  "trigger": {
    "type": "webhook",
    "path": "/error-webhook"
  },
  "nodes": [
    {
      "type": "telegram",
      "parameters": {
        "chatId": "@zakupai_admin",
        "text": "🚨 Ошибка в workflow:\n\nWorkflow: {{ $json.workflow_name }}\nОшибка: {{ $json.error_message }}\nВремя: {{ $json.timestamp }}"
      }
    }
  ]
}
```

## Best Practices

### 1. Обработка ошибок

```javascript
// В каждом custom node
try {
    // Основная логика
} catch (error) {
    if (this.continueOnFail()) {
        return [{ json: { error: error.message, timestamp: new Date().toISOString() } }];
    } else {
        throw error;
    }
}
```

### 2. Кэширование данных

```javascript
// Кэширование результатов в Redis
const redis = require('redis');
const client = redis.createClient();

// Проверяем кэш перед API запросом
const cacheKey = `lot_data_${lotId}`;
const cached = await client.get(cacheKey);

if (cached) {
    return JSON.parse(cached);
}

// Делаем запрос и кэшируем на 1 час
const data = await fetchLotData(lotId);
await client.setex(cacheKey, 3600, JSON.stringify(data));
```

### 3. Rate limiting

```javascript
// Rate limiting для external API
const RateLimiter = require('limiter').RateLimiter;
const limiter = new RateLimiter(10, 'minute'); // 10 requests per minute

// Использование в node
await new Promise(resolve => limiter.removeTokens(1, resolve));
// Теперь можем делать запрос
```

## Заключение

Интеграция n8n и Flowise с ZakupAI обеспечивает:

- ✅ **Визуальная автоматизация** - создание workflow без программирования
- ✅ **AI-интеграция** - использование LLM для анализа тендеров
- ✅ **Custom nodes и tools** - специализированные компоненты для госзакупок
- ✅ **Мониторинг workflow** - отслеживание выполнения и ошибок
- ✅ **Масштабируемость** - легкое добавление новых узлов и инструментов
- ✅ **Бизнес-автоматизация** - от мониторинга лотов до генерации документов
