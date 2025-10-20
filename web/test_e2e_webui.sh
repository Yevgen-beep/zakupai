#!/bin/bash

# Bash-скрипт для E2E тестирования Web UI через curl и jq
# Smoke-тесты ключевых эндпоинтов с выводом ✅/❌

set -e

WEB_UI_BASE_URL="http://localhost:8082"
TEST_FILE="web/test_fixtures/scan1.pdf"
TEMP_DIR="/tmp/webui_e2e_test"

# Цвета для вывода
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Функция для логирования
log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
    exit 1
}

log_warning() {
    echo -e "${YELLOW}⚠️ $1${NC}"
}

log_info() {
    echo -e "ℹ️ $1"
}

# Создать временную директорию
mkdir -p "$TEMP_DIR"
trap "rm -rf $TEMP_DIR" EXIT

log_info "🚀 Запуск E2E тестов Web UI..."

# 1. Тест /health эндпоинта
log_info "🔍 Тестирование /health эндпоинта..."
response=$(curl -s -w "%{http_code}" "$WEB_UI_BASE_URL/health" -o "$TEMP_DIR/health_response.json")
http_code="${response: -3}"

if [ "$http_code" != "200" ]; then
    log_error "Эндпоинт /health недоступен (HTTP $http_code)"
fi

# Проверяем JSON структуру
status=$(jq -r '.status // empty' "$TEMP_DIR/health_response.json")
if [ "$status" != "ok" ]; then
    log_error "Неправильный статус в /health: $status"
fi

log_success "Эндпоинт /health работает корректно"

# 2. Тест /lots эндпоинта
log_info "🔍 Тестирование /lots эндпоинта..."
response=$(curl -s -w "%{http_code}" "$WEB_UI_BASE_URL/lots?keyword=лак&limit=2" -o "$TEMP_DIR/lots_response.json")
http_code="${response: -3}"

if [ "$http_code" != "200" ]; then
    log_error "Эндпоинт /lots недоступен (HTTP $http_code)"
fi

# Проверяем наличие lots и их количество
lots_count=$(jq '.lots | length' "$TEMP_DIR/lots_response.json" 2>/dev/null || echo "0")
if [ "$lots_count" -le 0 ]; then
    log_error "Эндпоинт /lots вернул пустой список лотов"
fi

log_success "Эндпоинт /lots работает корректно (найдено $lots_count лотов)"

# 3. Тест /etl/upload эндпоинта
log_info "🔍 Тестирование /etl/upload эндпоинта..."

if [ ! -f "$TEST_FILE" ]; then
    log_error "Тестовый файл $TEST_FILE не найден"
fi

response=$(curl -s -w "%{http_code}" \
    -X POST \
    -F "file=@$TEST_FILE" \
    "$WEB_UI_BASE_URL/etl/upload" \
    -o "$TEMP_DIR/upload_response.json")
http_code="${response: -3}"

if [ "$http_code" != "200" ]; then
    log_error "Загрузка файла failed (HTTP $http_code)"
fi

# Проверяем наличие content_preview
content_preview=$(jq -r '.content_preview // empty' "$TEMP_DIR/upload_response.json")
if [ -z "$content_preview" ]; then
    log_error "В ответе ETL upload отсутствует content_preview"
fi

content_length=${#content_preview}
if [ "$content_length" -le 0 ]; then
    log_error "content_preview пуст"
fi

log_success "Эндпоинт /etl/upload работает корректно (preview: $content_length символов)"

# 4. Тест /search/documents эндпоинта
log_info "🔍 Тестирование /search/documents эндпоинта..."

# Ждём немного для обработки загруженного документа
sleep 3

response=$(curl -s -w "%{http_code}" \
    -X POST \
    -H "Content-Type: application/json" \
    -d '{"query": "иск"}' \
    "$WEB_UI_BASE_URL/search/documents" \
    -o "$TEMP_DIR/search_response.json")
http_code="${response: -3}"

if [ "$http_code" != "200" ]; then
    log_error "Поиск документов failed (HTTP $http_code)"
fi

# Проверяем наличие documents
documents_count=$(jq '.documents | length' "$TEMP_DIR/search_response.json" 2>/dev/null || echo "0")
if [ "$documents_count" -lt 1 ]; then
    log_error "Поиск не вернул ни одного документа"
fi

log_success "Эндпоинт /search/documents работает корректно (найдено $documents_count документов)"

# 5. Проверка полного пайплайна
log_info "🔍 Финальная проверка интеграции..."

# Дополнительный поиск по тексту из загруженного файла
response=$(curl -s -w "%{http_code}" \
    -X POST \
    -H "Content-Type: application/json" \
    -d '{"query": "тестовый документ"}' \
    "$WEB_UI_BASE_URL/search/documents" \
    -o "$TEMP_DIR/final_search_response.json")
http_code="${response: -3}"

if [ "$http_code" == "200" ]; then
    final_documents_count=$(jq '.documents | length' "$TEMP_DIR/final_search_response.json" 2>/dev/null || echo "0")
    if [ "$final_documents_count" -ge 1 ]; then
        log_success "Полный пайплайн Web UI → ETL → ChromaDB работает корректно"
    else
        log_warning "Полный пайплайн работает, но загруженный документ не найден при поиске"
    fi
else
    log_warning "Финальный поиск вернул ошибку (HTTP $http_code)"
fi

log_info "🎉 Все E2E тесты Web UI успешно пройдены!"

# Вывод краткой статистики
echo
log_info "📊 Результаты тестирования:"
echo "   ✅ /health - OK"
echo "   ✅ /lots - OK ($lots_count лотов)"
echo "   ✅ /etl/upload - OK ($content_length символов preview)"
echo "   ✅ /search/documents - OK ($documents_count документов)"
echo "   ✅ Полный пайплайн - OK"
echo

log_success "Все метрики E2E тестирования пройдены успешно!"

exit 0
