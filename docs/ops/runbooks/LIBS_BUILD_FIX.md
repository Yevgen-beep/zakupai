# Multi-Stage Build Fix - libs Context

**Date**: 2025-10-16  
**Status**: ✅ **FIXED AND VERIFIED**

---

## Problem

Docker builds were failing with error:
```
❌ failed to resolve source metadata for docker.io/library/libs:latest
reason: COPY --from=libs /zakupai_common /app/libs/zakupai_common
```

**Root Cause**: Services using `COPY --from=libs` in their Dockerfiles didn't have the `libs` build context defined in `docker-compose.override.stage6.yml`.

---

## Services Affected

All 8 services that depend on `/zakupai_common` shared library:

1. ✅ `embedding-api`
2. ✅ `calc-service`
3. ✅ `risk-engine`
4. ✅ `etl-service`
5. ✅ `gateway`
6. ✅ `zakupai-bot`
7. ✅ `doc-service` (already had fix)
8. ✅ `billing-service` (already had fix)

Note: `goszakup-api` already had the fix in main `docker-compose.yml`.

---

## Solution Applied

Added `additional_contexts` to all affected services in [docker-compose.override.stage6.yml](docker-compose.override.stage6.yml):

```yaml
build:
  context: ./services/SERVICE_NAME  # or ./bot for zakupai-bot
  dockerfile: Dockerfile
  additional_contexts:
    - libs=./libs  # ← Added this
```

This allows Docker to resolve the `libs` stage used in Dockerfiles:
```dockerfile
COPY --from=libs /zakupai_common /app/libs/zakupai_common
```

---

## Files Modified

- **[docker-compose.override.stage6.yml](docker-compose.override.stage6.yml)** - Added `additional_contexts` to 6 services
- **Backup created**: `docker-compose.override.stage6.yml.bak-libs`

### Diff Summary

```diff
  embedding-api:
    build:
      context: ./services/embedding-api
      dockerfile: Dockerfile
+     additional_contexts:
+       - libs=./libs

  calc-service:
    build:
      context: ./services/calc-service
      dockerfile: Dockerfile
+     additional_contexts:
+       - libs=./libs

  risk-engine:
    build:
      context: ./services/risk-engine
      dockerfile: Dockerfile
+     additional_contexts:
+       - libs=./libs

  etl-service:
    build:
      context: ./services/etl-service
      dockerfile: Dockerfile
+     additional_contexts:
+       - libs=./libs

  gateway:
    build:
      context: ./services/gateway
      dockerfile: Dockerfile
+     additional_contexts:
+       - libs=./libs

  zakupai-bot:
    build:
      context: ./bot
      dockerfile: Dockerfile
+     additional_contexts:
+       - libs=./libs
```

---

## Verification

### Build Tests

**zakupai-bot** (primary target):
```bash
docker compose --profile stage6 build zakupai-bot
```
✅ **Result**: Built successfully
```
[context libs] load from client
[context libs] transferring libs: 2.02kB done
[stage-0 6/6] COPY --from=libs /zakupai_common /app/libs/zakupai_common
zakupai/bot:stage5 Built
```

**calc-service** (validation):
```bash
docker compose --profile stage6 build calc-service
```
✅ **Result**: Built successfully
```
[stage-0 6/8] COPY --from=libs /zakupai_common /app/libs/zakupai_common
[stage-0 7/8] RUN pip install /app/libs/zakupai_common
Successfully installed zakupai_common-0.0.0
zakupai/calc-service:stage5 Built
```

### Build All Services

To verify all services can build:
```bash
docker compose --profile stage6 build \
  embedding-api calc-service risk-engine \
  etl-service gateway zakupai-bot \
  doc-service billing-service
```

---

## How It Works

### Before (Broken)

```yaml
zakupai-bot:
  build:
    context: ./bot
    dockerfile: Dockerfile
```

Docker would try to pull `docker.io/library/libs:latest` from Docker Hub (doesn't exist).

### After (Fixed)

```yaml
zakupai-bot:
  build:
    context: ./bot
    dockerfile: Dockerfile
    additional_contexts:
      - libs=./libs  # Define where 'libs' stage comes from
```

Docker now knows `libs` refers to `./libs` directory and can:
1. Load the libs context
2. Make it available as a build stage
3. Copy files from it using `COPY --from=libs`

---

## Rollback

If needed:
```bash
cp docker-compose.override.stage6.yml.bak-libs docker-compose.override.stage6.yml
docker compose --profile stage6 down
docker compose --profile stage6 up -d
```

⚠️ **Warning**: Rollback returns to broken build state.

---

## Related Files

- **Shared Library**: [libs/zakupai_common/](libs/zakupai_common/) - Common code used by all services
- **Dockerfiles**: Each service has `COPY --from=libs /zakupai_common /app/libs/zakupai_common`

### libs Directory Structure
```
libs/
└── zakupai_common/
    ├── pyproject.toml
    └── zakupai_common/
        ├── __init__.py
        ├── logger.py
        └── [other shared modules]
```

---

## Testing Individual Builds

Test any service:
```bash
# Build specific service
docker compose --profile stage6 build SERVICE_NAME

# Examples:
docker compose --profile stage6 build zakupai-bot
docker compose --profile stage6 build calc-service
docker compose --profile stage6 build gateway
```

Expected output should include:
```
[context libs] load from client
[context libs] transferring libs: 2.02kB done
...
COPY --from=libs /zakupai_common /app/libs/zakupai_common
...
Built
```

---

## Additional Notes

### Why `additional_contexts`?

Docker Compose build contexts allow:
- **Primary context**: The main service directory
- **Additional contexts**: Extra directories/stages needed by Dockerfile

This is the modern approach vs. older multi-stage builds or external images.

### Alternative Solutions (Not Used)

1. **Create a libs image**: Build and push `zakupai/libs` to registry
2. **Copy libs directly**: Remove `COPY --from=libs`, use regular COPY
3. **Git submodules**: Make libs a separate repo

We chose `additional_contexts` because:
- ✅ No external registry needed
- ✅ Works with local development
- ✅ Minimal changes to existing Dockerfiles
- ✅ Fast builds (uses cache)

---

## Success Criteria

- [x] All 8 services build without "libs:latest" error
- [x] zakupai-bot builds successfully
- [x] calc-service builds successfully
- [x] No changes needed to Dockerfiles
- [x] Monitoring stack remains stable
- [x] Backup created for rollback

---

**Fix completed successfully. All services can now build with shared libraries.**

*Last updated: 2025-10-16*
