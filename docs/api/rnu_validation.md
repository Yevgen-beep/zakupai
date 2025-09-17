# RNU Validation API Documentation

## Overview

The RNU (Unreliable Suppliers Registry) Validation API allows you to check if a supplier is listed in Kazakhstan's registry of unreliable procurement participants. This API provides caching for optimal performance and reliability.

## Endpoint

```
GET /validate_rnu/{supplier_bin}
```

## Request Parameters

### Path Parameters

| Parameter      | Type   | Required | Description                                        |
| -------------- | ------ | -------- | -------------------------------------------------- |
| `supplier_bin` | string | Yes      | Business Identification Number (exactly 12 digits) |

### Example Request

```javascript
// Using axios in React
import axios from 'axios';

const validateSupplier = async (bin) => {
  try {
    const response = await axios.get(`/validate_rnu/${bin}`);
    return response.data;
  } catch (error) {
    throw error;
  }
};
```

## Response Format

### Success Response (200 OK)

```json
{
  "supplier_bin": "123456789012",
  "is_blocked": false,
  "source": "cache",
  "validated_at": "2025-09-17T10:36:00+05:00"
}
```

### Response Fields

| Field          | Type    | Description                                                        |
| -------------- | ------- | ------------------------------------------------------------------ |
| `supplier_bin` | string  | The validated BIN                                                  |
| `is_blocked`   | boolean | `true` if supplier is in RNU registry, `false` otherwise           |
| `source`       | string  | Data source: `"cache"` (from cache) or `"api"` (from external API) |
| `validated_at` | string  | ISO 8601 timestamp of when validation was performed                |

## Error Responses

### 400 Bad Request

Invalid BIN format (not exactly 12 digits)

```json
{
  "detail": "Invalid BIN format: must be exactly 12 digits"
}
```

### 429 Too Many Requests

Rate limit exceeded for external API

```json
{
  "detail": "Rate limit exceeded, please try again later"
}
```

### 503 Service Unavailable

External RNU service is temporarily unavailable

```json
{
  "detail": "RNU service temporarily unavailable"
}
```

### 500 Internal Server Error

Unexpected server error

```json
{
  "detail": "Internal server error"
}
```

## Caching Strategy

The API uses a two-tier caching system for optimal performance:

1. **Redis Cache** (Primary): 24-hour TTL, fastest response (~100ms)
1. **PostgreSQL Cache** (Secondary): 24-hour TTL, fallback cache (~300ms)
1. **External API** (Last resort): When no cache available (~1-2s)

### Cache Behavior

- Cache hit: Response time \<500ms (95% of requests)
- API call: Response time \<2s (95% of requests)
- Availability target: ≥95%

## Web UI Integration

### Basic Implementation

```jsx
import React, { useState } from 'react';
import axios from 'axios';

const RNUValidator = () => {
  const [bin, setBin] = useState('');
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const validateBin = async () => {
    // Validate BIN format
    if (!/^\d{12}$/.test(bin)) {
      setError('БИН должен содержать ровно 12 цифр');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const response = await axios.get(`/validate_rnu/${bin}`);
      setResult(response.data);
    } catch (err) {
      if (err.response?.status === 400) {
        setError('Некорректный формат БИН');
      } else if (err.response?.status === 429) {
        setError('Превышен лимит запросов. Попробуйте позже.');
      } else if (err.response?.status === 503) {
        setError('Сервис временно недоступен');
      } else {
        setError('Произошла ошибка при проверке');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="rnu-validator">
      <div className="form-group">
        <label htmlFor="bin">БИН поставщика:</label>
        <input
          id="bin"
          type="text"
          value={bin}
          onChange={(e) => setBin(e.target.value.replace(/\D/g, '').slice(0, 12))}
          placeholder="123456789012"
          maxLength={12}
          pattern="\d{12}"
        />
        <button
          onClick={validateBin}
          disabled={loading || bin.length !== 12}
        >
          {loading ? 'Проверяем...' : 'Проверить'}
        </button>
      </div>

      {error && (
        <div className="error-message">
          ❌ {error}
        </div>
      )}

      {result && (
        <div className={`result ${result.is_blocked ? 'blocked' : 'not-blocked'}`}>
          <h3>Результат проверки</h3>
          <p><strong>БИН:</strong> {result.supplier_bin}</p>
          <p>
            <strong>Статус:</strong>
            {result.is_blocked ? (
              <span className="blocked">🔴 Заблокирован в RNU</span>
            ) : (
              <span className="not-blocked">🟢 Не заблокирован</span>
            )}
          </p>
          <p><strong>Проверено:</strong> {new Date(result.validated_at).toLocaleString('ru-RU')}</p>
          <p><strong>Источник:</strong> {result.source === 'cache' ? 'Кэш' : 'API'}</p>
        </div>
      )}
    </div>
  );
};

export default RNUValidator;
```

### CSS Styling

```css
.rnu-validator {
  max-width: 500px;
  margin: 20px auto;
  padding: 20px;
  border: 1px solid #ddd;
  border-radius: 8px;
}

.form-group {
  margin-bottom: 20px;
}

.form-group label {
  display: block;
  margin-bottom: 5px;
  font-weight: bold;
}

.form-group input {
  width: 100%;
  padding: 10px;
  border: 1px solid #ccc;
  border-radius: 4px;
  font-size: 16px;
}

.form-group button {
  margin-top: 10px;
  padding: 10px 20px;
  background-color: #007bff;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}

.form-group button:disabled {
  background-color: #ccc;
  cursor: not-allowed;
}

.error-message {
  color: #dc3545;
  background-color: #f8d7da;
  padding: 10px;
  border-radius: 4px;
  margin: 10px 0;
}

.result {
  margin-top: 20px;
  padding: 15px;
  border-radius: 4px;
}

.result.blocked {
  background-color: #f8d7da;
  border: 1px solid #dc3545;
}

.result.not-blocked {
  background-color: #d4edda;
  border: 1px solid #28a745;
}

.blocked {
  color: #dc3545;
}

.not-blocked {
  color: #28a745;
}
```

## Advanced Features

### TypeScript Support

```typescript
interface RNUValidationResponse {
  supplier_bin: string;
  is_blocked: boolean;
  source: 'cache' | 'api';
  validated_at: string;
}

interface RNUValidationError {
  detail: string;
}

const validateSupplier = async (bin: string): Promise<RNUValidationResponse> => {
  const response = await axios.get<RNUValidationResponse>(`/validate_rnu/${bin}`);
  return response.data;
};
```

### React Hook

```tsx
import { useState, useCallback } from 'react';
import axios from 'axios';

interface UseRNUValidationResult {
  validate: (bin: string) => Promise<void>;
  result: RNUValidationResponse | null;
  loading: boolean;
  error: string | null;
  reset: () => void;
}

export const useRNUValidation = (): UseRNUValidationResult => {
  const [result, setResult] = useState<RNUValidationResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const validate = useCallback(async (bin: string) => {
    if (!/^\d{12}$/.test(bin)) {
      setError('БИН должен содержать ровно 12 цифр');
      return;
    }

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const response = await axios.get<RNUValidationResponse>(`/validate_rnu/${bin}`);
      setResult(response.data);
    } catch (err: any) {
      if (err.response?.status === 400) {
        setError('Некорректный формат БИН');
      } else if (err.response?.status === 429) {
        setError('Превышен лимит запросов. Попробуйте позже.');
      } else if (err.response?.status === 503) {
        setError('Сервис временно недоступен');
      } else {
        setError('Произошла ошибка при проверке');
      }
    } finally {
      setLoading(false);
    }
  }, []);

  const reset = useCallback(() => {
    setResult(null);
    setError(null);
    setLoading(false);
  }, []);

  return { validate, result, loading, error, reset };
};
```

## Performance Monitoring

Monitor the following metrics:

- **Cache Hit Rate**: Should be >80%
- **Response Time**:
  - Cache: \<500ms (95th percentile)
  - API: \<2s (95th percentile)
- **Availability**: >95%
- **Error Rate**: \<5%

## Security Considerations

- BIN validation is performed on both frontend and backend
- No sensitive data is logged
- API rate limiting is applied
- Redis cache is configured with appropriate TTL
- PostgreSQL cache includes data expiration

## Rate Limits

- External API: Limited by goszakup.gov.kz
- Internal caching: No limits (cached responses)
- Retry logic: 3 attempts with exponential backoff

## Support

For technical support or feature requests, please contact the ZakupAI development team.
