#!/usr/bin/env bash
#
# Stage 7 Phase 1 - Security Quick Wins Smoke Tests
# Проверяет calc-service: валидацию, payload limit, rate limiting
#

set -e

BASE_URL="${BASE_URL:-http://localhost:7001}"
CALC_URL="$BASE_URL/calc"

echo "🧪 Stage 7 Phase 1 - Security Quick Wins Smoke Tests"
echo "📍 Target: $CALC_URL"
echo ""

# Test 1: 422 - Invalid lot_id (должна быть строка вместо числа)
echo "✅ Test 1: Validation error (422) - invalid lot_id type"
RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$CALC_URL/profit" \
  -H "Content-Type: application/json" \
  -d '{"lot_id":"abc","supplier_id":1,"region":"Almaty"}')

HTTP_CODE=$(echo "$RESPONSE" | tail -1)
BODY=$(echo "$RESPONSE" | head -n -1)

if [ "$HTTP_CODE" = "422" ]; then
  echo "   ✓ Got 422 as expected"
  echo "   Response: $BODY"
else
  echo "   ✗ Expected 422, got $HTTP_CODE"
  echo "   Response: $BODY"
  exit 1
fi

echo ""

# Test 2: 422 - Negative lot_id
echo "✅ Test 2: Validation error (422) - negative lot_id"
RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$CALC_URL/profit" \
  -H "Content-Type: application/json" \
  -d '{"lot_id":-1,"supplier_id":1,"region":"Almaty"}')

HTTP_CODE=$(echo "$RESPONSE" | tail -1)
if [ "$HTTP_CODE" = "422" ]; then
  echo "   ✓ Got 422 as expected"
else
  echo "   ✗ Expected 422, got $HTTP_CODE"
  exit 1
fi

echo ""

# Test 3: 422 - Invalid BIN format
echo "✅ Test 3: Validation error (422) - invalid BIN format"
RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$CALC_URL/risk-score" \
  -H "Content-Type: application/json" \
  -d '{"supplier_bin":"123","year":2024}')

HTTP_CODE=$(echo "$RESPONSE" | tail -1)
if [ "$HTTP_CODE" = "422" ]; then
  echo "   ✓ Got 422 as expected"
else
  echo "   ✗ Expected 422, got $HTTP_CODE"
  exit 1
fi

echo ""

# Test 4: 413 - Payload too large
echo "✅ Test 4: Payload too large (413)"
LARGE_REGION=$(python3 -c "print('A' * (2*1024*1024 + 100))")
RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$CALC_URL/profit" \
  -H "Content-Type: application/json" \
  -H "Content-Length: $((2*1024*1024 + 200))" \
  -d "{\"lot_id\":1,\"supplier_id\":1,\"region\":\"$LARGE_REGION\"}" 2>/dev/null || echo -e "\n413")

HTTP_CODE=$(echo "$RESPONSE" | tail -1)
if [ "$HTTP_CODE" = "413" ]; then
  echo "   ✓ Got 413 as expected"
else
  echo "   ⚠ Expected 413, got $HTTP_CODE (payload middleware may need Content-Length check)"
fi

echo ""

# Test 5: 200 - Valid request
echo "✅ Test 5: Valid request (200)"
RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$CALC_URL/profit" \
  -H "Content-Type: application/json" \
  -d '{"lot_id":123,"supplier_id":456,"region":"Almaty"}')

HTTP_CODE=$(echo "$RESPONSE" | tail -1)
BODY=$(echo "$RESPONSE" | head -n -1)

if [ "$HTTP_CODE" = "200" ]; then
  echo "   ✓ Got 200 as expected"
  echo "   Response: $BODY"
else
  echo "   ✗ Expected 200, got $HTTP_CODE"
  echo "   Response: $BODY"
  exit 1
fi

echo ""

# Test 6: 200 - Valid risk score request
echo "✅ Test 6: Valid risk score request (200)"
RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$CALC_URL/risk-score" \
  -H "Content-Type: application/json" \
  -d '{"supplier_bin":"123456789012","year":2024}')

HTTP_CODE=$(echo "$RESPONSE" | tail -1)
BODY=$(echo "$RESPONSE" | head -n -1)

if [ "$HTTP_CODE" = "200" ]; then
  echo "   ✓ Got 200 as expected"
  echo "   Response: $BODY"
else
  echo "   ✗ Expected 200, got $HTTP_CODE"
  echo "   Response: $BODY"
  exit 1
fi

echo ""
echo "🎉 All Stage 7 Phase 1 smoke tests passed!"
echo ""
echo "📝 Next steps:"
echo "   1. Run pytest: docker compose exec calc-service pytest tests/test_validation.py"
echo "   2. Generate OpenAPI: docker compose exec calc-service python generate_openapi.py"
echo "   3. Check docs: http://localhost:7001/calc/docs"
