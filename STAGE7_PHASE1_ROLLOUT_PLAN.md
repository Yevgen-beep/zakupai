# Stage 7 Phase 1 Rollout Plan

## ✅ Completed Services

### 1. **calc-service** (Reference Implementation)
- ✅ Pydantic validation (schemas.py)
- ✅ PayloadSizeLimitMiddleware (2MB max)
- ✅ Rate limiter (slowapi, 30/min)
- ✅ Centralized error handlers (422/413/429)
- ✅ Dockerfile with correct build context
- ✅ vault_client import fixed
- ✅ root_path="/calc" (paths corrected)
- ✅ Smoke tests passed

### 2. **risk-engine**
**Modified files:**
- `services/risk-engine/exceptions.py` (created)
- `services/risk-engine/Dockerfile` (updated: build context)
- `services/risk-engine/requirements.txt` (added slowapi>=0.1.9)
- `services/risk-engine/main.py`:
  - Fixed: `from services.common.vault_client` → `from zakupai_common.vault_client`
  - Added: PayloadSizeLimitMiddleware
  - Added: slowapi rate limiter + exception handlers
  - Added: @limiter.limit("30/minute") on /risk/score
- `docker-compose.yml`: context changed to `.`, dockerfile specified

**Endpoints:**
- `/risk/health` (from health_router)
- `/risk/score` (rate limited)
- `/risk/metrics`

**Manual steps required:**
```bash
docker compose build risk-engine
docker compose up -d risk-engine
curl -s http://localhost:7002/risk/health | jq
```

---

## 🚧 Services Requiring main.py Updates

The following services have:
- ✅ `exceptions.py` created
- ✅ `Dockerfile` updated
- ✅ `docker-compose.yml` updated
- ✅ `slowapi` added to requirements.txt
- ⚠️ `main.py` **needs manual update** (add middleware, rate limiter, exception handlers)

### 3. **etl-service**
- Import fix: `from services.common.vault_client` → `from zakupai_common.vault_client`
- root_path: *check if exists*
- Critical endpoints to rate-limit: TBD (review main.py)

### 4. **doc-service**
- root_path="/doc"
- Critical endpoints: TBD

### 5. **billing-service**
- root_path: *check if exists*
- Critical endpoints: TBD

### 6. **embedding-api**
- root_path="/emb"
- Critical endpoints: /embed, /search

### 7. **gateway**
- root_path: *none (proxy)*
- Special case: may not need rate limiter (nginx handles it)

---

## 📋 Next Steps

### For each service (3-7):

1. **Read main.py** and identify:
   - Current middleware stack
   - Existing vault_client imports (fix if needed)
   - Critical POST endpoints (add rate limiter)
   - FastAPI app initialization location

2. **Add to main.py** (after imports):
   ```python
   from slowapi import Limiter, _rate_limit_exceeded_handler
   from slowapi.util import get_remote_address
   from slowapi.errors import RateLimitExceeded
   from fastapi.exceptions import RequestValidationError
   from starlette.responses import JSONResponse
   from exceptions import validation_exception_handler, payload_too_large_handler, rate_limit_handler
   ```

3. **Create PayloadSizeLimitMiddleware** class (if not exists)

4. **After `app = FastAPI(...)`**:
   ```python
   limiter = Limiter(key_func=get_remote_address)
   app.state.limiter = limiter
   
   app.add_exception_handler(RequestValidationError, validation_exception_handler)
   app.add_exception_handler(RateLimitExceeded, rate_limit_handler)
   
   app.add_middleware(PayloadSizeLimitMiddleware)
   # ... existing middlewares
   ```

5. **Add `@limiter.limit("30/minute")`** to critical POST endpoints

6. **Rebuild and test**:
   ```bash
   docker compose build <service>
   docker compose up -d <service>
   curl -s http://localhost:<port>/<root>/health | jq
   ```

---

## 🧪 Testing Checklist (After Manual Updates)

For each service:
- [ ] Health check returns 200
- [ ] Invalid payload returns 422 with proper format
- [ ] Payload >2MB returns 413
- [ ] Rate limit (31+ requests) returns 429
- [ ] Swagger UI accessible

---

## 📊 Expected Outcome

All services conform to **Stage 7 Phase 1 Security Baseline**:
1. Pydantic validation
2. Payload size limits
3. Rate limiting on critical endpoints
4. Centralized error handling
5. Consistent audit logging
6. Vault integration ready

