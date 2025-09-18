# ZakupAI Flowise API - Week 4.2 Documentation

Enhanced Flowise features with complaint-generator, supplier-finder with modular sources, and comprehensive monitoring.

## Overview

Week 4.2 introduces production-ready Flowise capabilities:

- **Complaint Generator**: AI-powered complaint generation with PDF/Word export, Redis caching, and Flowise integration
- **Modular Supplier Finder**: Multi-source supplier search (Satu.kz, 1688, Alibaba) with rate limiting and fallbacks
- **Enhanced Performance**: \<1s complaint generation, \<1s supplier search, comprehensive monitoring
- **Document Export**: Professional PDF and Word document generation with proper formatting

## Base URL

```
http://localhost:8000
```

______________________________________________________________________

## Complaint Generator API

### Generate Complaint

**Endpoint**: `POST /api/complaint/{lot_id}`

Generate AI-powered complaint documents with caching and fallback support.

#### Request

```http
POST /api/complaint/12345
Content-Type: application/json

{
  "reason": "завышенная цена на товары",
  "date": "2025-01-15"
}
```

#### Request Schema

```json
{
  "reason": {
    "type": "string",
    "description": "Complaint reason",
    "minLength": 5,
    "maxLength": 200,
    "required": true
  },
  "date": {
    "type": "string",
    "format": "date",
    "description": "Complaint date (ISO format YYYY-MM-DD)",
    "pattern": "^\\d{4}-\\d{2}-\\d{2}$",
    "required": false,
    "default": "today's date"
  }
}
```

#### Response

```json
{
  "lot_id": 12345,
  "complaint_text": "ЖАЛОБА #12345\n\nДата: 2025-01-15\n\nЛот: Компьютерное оборудование для школ (ID: 12345)\nЗаказчик: Управление образования г. Алматы\nСумма: 2,500,000.00 тенге\n\nОснование жалобы: завышенная цена на товары\n\n...",
  "reason": "завышенная цена на товары",
  "date": "2025-01-15",
  "source": "flowise",
  "generated_at": "2025-01-15T14:30:45+06:00",
  "formats_available": ["pdf", "word"]
}
```

#### Response Fields

| Field               | Type    | Description                                          |
| ------------------- | ------- | ---------------------------------------------------- |
| `lot_id`            | integer | Lot identifier                                       |
| `complaint_text`    | string  | Generated complaint text                             |
| `reason`            | string  | Complaint reason                                     |
| `date`              | string  | Complaint date                                       |
| `source`            | string  | Generation source: `flowise`, `fallback`, or `cache` |
| `generated_at`      | string  | ISO timestamp of generation                          |
| `formats_available` | array   | Available export formats                             |

#### Source Types

| Source     | Description                  | Cache TTL | Performance Target |
| ---------- | ---------------------------- | --------- | ------------------ |
| `flowise`  | AI-generated via Flowise API | 24h       | \<1s               |
| `fallback` | SQL template-based           | 24h       | \<500ms            |
| `cache`    | Redis cached result          | -         | \<100ms            |

### Download Complaint PDF

**Endpoint**: `GET /api/complaint/{lot_id}/pdf`

Download complaint as professionally formatted PDF document.

#### Request

```http
GET /api/complaint/12345/pdf?reason=завышенная цена&date=2025-01-15
```

#### Parameters

| Parameter | Type   | Required | Description                    |
| --------- | ------ | -------- | ------------------------------ |
| `reason`  | string | Yes      | Complaint reason (URL encoded) |
| `date`    | string | Yes      | Complaint date (YYYY-MM-DD)    |

#### Response

```http
HTTP/1.1 200 OK
Content-Type: application/pdf
Content-Disposition: attachment; filename=complaint_12345_20250115.pdf

%PDF-1.4
[PDF binary content]
```

#### Features

- **Professional Formatting**: ZakupAI logo, proper fonts, 1cm margins
- **Font Support**: Arial Unicode MS with DejaVu Sans fallback for Cyrillic
- **Layout**: Structured header, information table, content, and footer
- **Performance**: \<1 second generation time

### Download Complaint Word

**Endpoint**: `GET /api/complaint/{lot_id}/word`

Download complaint as Microsoft Word document (.docx).

#### Request

```http
GET /api/complaint/12345/word?reason=завышенная цена&date=2025-01-15
```

#### Response

```http
HTTP/1.1 200 OK
Content-Type: application/vnd.openxmlformats-officedocument.wordprocessingml.document
Content-Disposition: attachment; filename=complaint_12345_20250115.docx

[Word document binary content]
```

#### Features

- **Professional Layout**: Headers, tables, proper spacing
- **Cyrillic Support**: Full UTF-8 compatibility
- **Editable**: Can be modified after download
- **Cross-platform**: Compatible with MS Word, LibreOffice, Google Docs

### Error Handling

| Status Code | Description      | Response                                     |
| ----------- | ---------------- | -------------------------------------------- |
| 200         | Success          | Complaint data or file                       |
| 400         | Invalid request  | `{"detail": "Validation error message"}`     |
| 404         | Lot not found    | `{"detail": "Lot not found"}`                |
| 422         | Validation error | `{"detail": "Field validation details"}`     |
| 500         | Generation error | `{"detail": "Failed to generate complaint"}` |

______________________________________________________________________

## Supplier Finder API

### Search Suppliers

**Endpoint**: `GET /api/supplier/{lot_name}`

Search suppliers across multiple sources with filters and rate limiting.

#### Request

```http
GET /api/supplier/мебель?region=KZ&min_budget=10000&max_budget=500000&sources=satu,1688,alibaba
```

#### Parameters

| Parameter    | Type   | Required | Description                                       |
| ------------ | ------ | -------- | ------------------------------------------------- |
| `lot_name`   | string | Yes      | Product/service name to search (URL encoded)      |
| `region`     | string | No       | Filter by region: `KZ`, `RU`, `CN`                |
| `min_budget` | float  | No       | Minimum budget/price filter                       |
| `max_budget` | float  | No       | Maximum budget/price filter                       |
| `sources`    | string | No       | Comma-separated source names: `satu,1688,alibaba` |

#### Response

```json
{
  "lot_name": "мебель",
  "suppliers": [
    {
      "name": "ТОО Мебельная компания Астана",
      "region": "KZ",
      "budget": 125000.00,
      "rating": 4.2,
      "link": "https://satu.kz/supplier/12345",
      "source": "Satu.kz"
    },
    {
      "name": "杭州家具制造有限公司",
      "region": "CN",
      "budget": 8500.00,
      "rating": 4.5,
      "link": "https://1688.com/supplier/56789",
      "source": "1688"
    }
  ],
  "total_found": 8,
  "sources_used": ["Satu.kz", "1688", "Alibaba"],
  "cache_hit": false,
  "latency_ms": 850
}
```

#### Response Schema

```json
{
  "lot_name": "string",
  "suppliers": [
    {
      "name": "string",
      "region": "string (KZ|RU|CN|Unknown)",
      "budget": "number (>=0)",
      "rating": "number (0-5)",
      "link": "string (URL)",
      "source": "string"
    }
  ],
  "total_found": "integer",
  "sources_used": ["string"],
  "cache_hit": "boolean",
  "latency_ms": "integer"
}
```

### Supplier Sources

Modular source configuration with rate limiting and fallbacks.

#### Available Sources

| Source      | Type     | Auth    | Rate Limit | Region Focus    |
| ----------- | -------- | ------- | ---------- | --------------- |
| **Satu.kz** | Mock/API | None    | 1000/day   | Kazakhstan (KZ) |
| **1688**    | RapidAPI | API_KEY | 100/day    | China (CN)      |
| **Alibaba** | RapidAPI | API_KEY | 100/day    | Global/China    |

#### Rate Limiting

- **Per Source**: Individual limits (100-1000 requests/day)
- **Redis Tracking**: `INCR` with 24h TTL
- **Fallback**: Web search when limits exceeded
- **Headers**: Rate limit status in response headers

#### Fallback Chain

1. **Primary**: API/Mock data from configured source
1. **Rate Limited**: Web search fallback (`site:source.com query`)
1. **Timeout/Error**: Generic web search results
1. **Cache**: 48-hour Redis cache for successful results

### Error Handling

| Status Code | Description         | Response                                         |
| ----------- | ------------------- | ------------------------------------------------ |
| 200         | Success             | Supplier data                                    |
| 400         | Invalid parameters  | `{"detail": "Validation error"}`                 |
| 429         | Rate limit exceeded | `{"detail": "Rate limit exceeded for source X"}` |
| 500         | Search error        | `{"detail": "Failed to search suppliers"}`       |

______________________________________________________________________

## Admin API - Supplier Sources

Manage supplier source configurations.

### Get All Sources

**Endpoint**: `GET /api/admin/sources`

Retrieve all supplier source configurations.

#### Response

```json
[
  {
    "id": 1,
    "name": "Satu.kz",
    "url_template": "https://satu.kz/search?q={query}",
    "parser_type": "mock",
    "auth_type": "NONE",
    "credentials_ref": null,
    "rate_limit": 1000,
    "fallback_type": "web_search",
    "active": true
  },
  {
    "id": 2,
    "name": "1688",
    "url_template": "https://rapidapi.com/open-trade-commerce-default/api/otapi-1688",
    "parser_type": "api",
    "auth_type": "API_KEY",
    "credentials_ref": "RAPIDAPI_KEY",
    "rate_limit": 100,
    "fallback_type": "web_search",
    "active": true
  }
]
```

### Create Source

**Endpoint**: `POST /api/admin/sources`

Create a new supplier source configuration.

#### Request

```json
{
  "name": "Custom Source",
  "url_template": "https://api.example.com/search?q={query}",
  "parser_type": "api",
  "auth_type": "API_KEY",
  "credentials_ref": "CUSTOM_API_KEY",
  "rate_limit": 500,
  "fallback_type": "web_search",
  "active": true
}
```

### Update Source

**Endpoint**: `PUT /api/admin/sources/{source_id}`

Update existing supplier source configuration.

### Delete Source

**Endpoint**: `DELETE /api/admin/sources/{source_id}`

Delete supplier source configuration.

______________________________________________________________________

## Performance Monitoring

### Metrics Endpoints

#### Prometheus Metrics

**Endpoint**: `GET /metrics`

Prometheus-compatible metrics for monitoring.

```
# Complaint Generation
complaint_generation_count_total{source="flowise"} 1250
complaint_generation_duration_seconds_bucket{source="flowise",le="0.5"} 800
complaint_generation_duration_seconds_bucket{source="flowise",le="1.0"} 1200
complaint_fallback_count_total 50

# Supplier Search
supplier_search_count_total{source="satu"} 2500
supplier_search_duration_seconds_bucket{source="satu",le="0.5"} 2000
supplier_results_count{source="satu"} 3.2
supplier_fallback_count_total{source="1688"} 15

# Document Generation
document_generation_total{format="pdf"} 800
document_generation_total{format="word"} 200
document_generation_duration_seconds_bucket{format="pdf",le="1.0"} 750

# Cache Performance
redis_cache_hits_total 15000
redis_cache_misses_total 3000
```

#### Performance Targets

| Metric               | Target                    | Monitoring                                 |
| -------------------- | ------------------------- | ------------------------------------------ |
| Complaint Generation | \<1s (95th percentile)    | `complaint_generation_duration_seconds`    |
| Supplier Search      | \<1s (95th percentile)    | `supplier_search_duration_seconds`         |
| Autocomplete         | \<500ms (95th percentile) | `autocomplete_duration_seconds`            |
| PDF Generation       | \<1s (95th percentile)    | `document_generation_duration_seconds`     |
| Cache Hit Rate       | >80%                      | `redis_cache_hits_total / (hits + misses)` |
| Error Rate           | \<5%                      | `http_requests_total{status=~"5.."}`       |

### Health Checks

#### Service Health

**Endpoint**: `GET /health`

```json
{
  "status": "healthy",
  "version": "4.2.0",
  "features": {
    "complaint_generator": "active",
    "supplier_finder": "active",
    "document_export": "active"
  },
  "dependencies": {
    "database": "healthy",
    "redis": "healthy",
    "flowise": "healthy",
    "chromadb": "healthy"
  }
}
```

#### Feature-specific Health

**Endpoint**: `GET /health/flowise`

```json
{
  "status": "healthy",
  "latency_ms": 150,
  "fallback_rate": 0.02,
  "last_success": "2025-01-15T14:30:00Z"
}
```

______________________________________________________________________

## Integration Examples

### JavaScript/React Integration

#### Complaint Generation with Download

```javascript
// Complaint generation and PDF download
async function generateComplaintWithPDF(lotId, reason, date) {
  try {
    // Generate complaint
    const response = await fetch(`/api/complaint/${lotId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ reason, date })
    });

    const complaint = await response.json();

    if (complaint.source === 'cache') {
      console.log('Retrieved from cache ⚡');
    } else if (complaint.source === 'flowise') {
      console.log('Generated by AI 🤖');
    } else {
      console.log('Generated by fallback 📝');
    }

    // Download PDF
    const pdfUrl = `/api/complaint/${lotId}/pdf?reason=${encodeURIComponent(reason)}&date=${date}`;
    const pdfResponse = await fetch(pdfUrl);

    if (pdfResponse.ok) {
      const blob = await pdfResponse.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `complaint_${lotId}_${date.replace(/-/g, '')}.pdf`;
      a.click();
      window.URL.revokeObjectURL(url);
    }

    return complaint;
  } catch (error) {
    console.error('Complaint generation failed:', error);
    throw error;
  }
}
```

#### Supplier Search with Filters

```javascript
// Enhanced supplier search with real-time filtering
class SupplierSearchComponent extends React.Component {
  constructor(props) {
    super(props);
    this.state = {
      query: '',
      suppliers: [],
      loading: false,
      filters: {
        region: '',
        minBudget: '',
        maxBudget: '',
        sources: ['satu', '1688', 'alibaba']
      },
      cache_hit: false,
      latency_ms: 0
    };
  }

  async searchSuppliers() {
    if (!this.state.query || this.state.query.length < 3) return;

    this.setState({ loading: true });

    try {
      const params = new URLSearchParams();
      if (this.state.filters.region) params.append('region', this.state.filters.region);
      if (this.state.filters.minBudget) params.append('min_budget', this.state.filters.minBudget);
      if (this.state.filters.maxBudget) params.append('max_budget', this.state.filters.maxBudget);
      if (this.state.filters.sources.length > 0) params.append('sources', this.state.filters.sources.join(','));

      const response = await fetch(
        `/api/supplier/${encodeURIComponent(this.state.query)}?${params.toString()}`
      );

      const data = await response.json();

      this.setState({
        suppliers: data.suppliers || [],
        cache_hit: data.cache_hit,
        latency_ms: data.latency_ms,
        loading: false
      });

    } catch (error) {
      console.error('Supplier search failed:', error);
      this.setState({ loading: false });
    }
  }

  renderSupplierCard(supplier) {
    const regionFlag = { KZ: '🇰🇿', CN: '🇨🇳', RU: '🇷🇺' }[supplier.region] || '🌍';
    const stars = '⭐'.repeat(Math.floor(supplier.rating));

    return (
      <div key={supplier.link} className="supplier-card">
        <h3>{supplier.name} {regionFlag}</h3>
        <div className="supplier-info">
          <span className="rating">{stars} {supplier.rating.toFixed(1)}</span>
          <span className="budget">{supplier.budget.toLocaleString()} ₸</span>
          <span className="source">{supplier.source}</span>
        </div>
        <a href={supplier.link} target="_blank" rel="noopener noreferrer">
          View Supplier Profile
        </a>
      </div>
    );
  }

  render() {
    return (
      <div className="supplier-search">
        {/* Search interface */}
        <div className="search-controls">
          <input
            type="text"
            placeholder="Поиск поставщиков..."
            value={this.state.query}
            onChange={(e) => this.setState({ query: e.target.value })}
            onKeyPress={(e) => e.key === 'Enter' && this.searchSuppliers()}
          />
          <button onClick={() => this.searchSuppliers()} disabled={this.state.loading}>
            {this.state.loading ? 'Поиск...' : 'Найти'}
          </button>
        </div>

        {/* Filters */}
        <div className="search-filters">
          <select
            value={this.state.filters.region}
            onChange={(e) => this.setState({
              filters: { ...this.state.filters, region: e.target.value }
            })}
          >
            <option value="">Все регионы</option>
            <option value="KZ">🇰🇿 Казахстан</option>
            <option value="CN">🇨🇳 Китай</option>
            <option value="RU">🇷🇺 Россия</option>
          </select>

          <input
            type="number"
            placeholder="Мин. бюджет"
            value={this.state.filters.minBudget}
            onChange={(e) => this.setState({
              filters: { ...this.state.filters, minBudget: e.target.value }
            })}
          />

          <input
            type="number"
            placeholder="Макс. бюджет"
            value={this.state.filters.maxBudget}
            onChange={(e) => this.setState({
              filters: { ...this.state.filters, maxBudget: e.target.value }
            })}
          />
        </div>

        {/* Results */}
        <div className="search-results">
          {this.state.cache_hit && (
            <div className="cache-indicator">⚡ Результаты из кэша ({this.state.latency_ms}ms)</div>
          )}

          <div className="suppliers-grid">
            {this.state.suppliers.map(supplier => this.renderSupplierCard(supplier))}
          </div>

          {this.state.suppliers.length === 0 && !this.state.loading && (
            <div className="no-results">Поставщики не найдены</div>
          )}
        </div>
      </div>
    );
  }
}
```

### Telegram Bot Integration

#### Enhanced Commands

```bash
# Complaint generation with date
/complaint 12345 завышенная цена date=2025-01-15

# Supplier search with filters
/supplier мебель region=KZ sources=satu,1688

# Check complaint with formats
/complaint 12345 качество товара
# Bot response:
# ✅ Жалоба создана для лота 12345 🤖
# Источник: flowise
# Причина: качество товара
#
# 📄 [PDF](http://localhost:8000/api/complaint/12345/pdf?reason=качество товара&date=2025-01-15)
# 📝 [Word](http://localhost:8000/api/complaint/12345/word?reason=качество товара&date=2025-01-15)
#
# [Web UI link](http://localhost:8000/complaint/12345)
```

______________________________________________________________________

## Security & Best Practices

### Input Validation

- **Complaint Reason**: 5-200 characters, XSS protection
- **Date Validation**: ISO format, not in future
- **File Size Limits**: 5MB for PDF/Word generation
- **Rate Limiting**: Per-IP and per-user limits

### Authentication

- **API Keys**: Required for admin endpoints
- **CORS**: Configured for allowed origins
- **SQL Injection**: Parameterized queries only
- **File Access**: Temporary file cleanup

### Performance Optimization

- **Redis Caching**: 24h for complaints, 48h for suppliers
- **Connection Pooling**: Database and HTTP clients
- **Async Processing**: Parallel supplier source queries
- **Fallback Strategy**: Multiple levels of fallbacks

### Monitoring & Alerting

- **Performance Alerts**: Latency thresholds
- **Error Rate Monitoring**: 5xx response tracking
- **Fallback Tracking**: Source unavailability alerts
- **Resource Monitoring**: Memory, CPU, disk usage

______________________________________________________________________

This completes the comprehensive API documentation for Week 4.2 ZakupAI Flowise features, providing production-ready complaint generation and supplier search capabilities with proper monitoring and integration examples.
