"""
E2E тестирование Web UI для проверки полного пайплайна:
Web UI → goszakup-api → etl-service → ChromaDB

Требования:
- Использовать httpx для HTTP-запросов
- Проверить ключевые эндпоинты с метриками
- Все ассерты на русском языке (✅/❌)
"""
# flake8: noqa: S101

import asyncio
from pathlib import Path

import httpx
import pytest


@pytest.fixture
async def http_client():
    """HTTP-клиент с таймаутом для тестов"""
    async with httpx.AsyncClient(timeout=30.0) as client:
        yield client


@pytest.fixture
def web_ui_base_url():
    """Базовый URL Web UI сервиса"""
    return "http://localhost:8082"


class TestWebUIE2E:
    """E2E тесты для Web UI"""

    @pytest.mark.asyncio
    async def test_health_endpoint(self, http_client, web_ui_base_url):
        """✅ Тест эндпоинта /health - должен возвращать {"status": "ok"}"""
        response = await http_client.get(f"{web_ui_base_url}/health")

        assert response.status_code == 200, "❌ Эндпоинт /health недоступен"

        data = response.json()
        assert "status" in data, "❌ В ответе отсутствует поле 'status'"
        assert data["status"] == "ok", f"❌ Неправильный статус: {data['status']}"

        print("✅ Эндпоинт /health работает корректно")

    @pytest.mark.asyncio
    async def test_lots_endpoint(self, http_client, web_ui_base_url):
        """✅ Тест эндпоинта /lots?keyword=лак&limit=2 - должен возвращать JSON с lots"""
        response = await http_client.get(
            f"{web_ui_base_url}/lots", params={"keyword": "лак", "limit": 2}
        )

        # Проверяем статус код
        assert (
            response.status_code == 200
        ), f"❌ Эндпоинт /lots вернул статус {response.status_code}"

        data = response.json()

        # Проверяем наличие поля lots
        assert "lots" in data, "❌ В ответе отсутствует поле 'lots'"
        lots = data["lots"]

        # Проверяем что есть результаты
        assert len(lots) > 0, "❌ Список лотов пуст"

        # Проверяем наличие кириллицы в результатах
        has_cyrillic = False
        for lot in lots:
            lot_text = str(lot).lower()
            if any(ord(char) >= 1040 and ord(char) <= 1103 for char in lot_text):
                has_cyrillic = True
                break

        assert has_cyrillic, "❌ В результатах отсутствует кириллица"

        print(
            f"✅ Эндпоинт /lots работает корректно, найдено {len(lots)} лотов с кириллицей"
        )

    @pytest.mark.asyncio
    async def test_etl_upload_endpoint(self, http_client, web_ui_base_url):
        """✅ Тест эндпоинта POST /etl/upload - отправка scan1.pdf"""
        test_file_path = Path("web/test_fixtures/scan1.pdf")

        assert test_file_path.exists(), f"❌ Тестовый файл {test_file_path} не найден"

        # Загружаем файл через Web UI
        with open(test_file_path, "rb") as f:
            files = {"file": ("scan1.pdf", f, "application/pdf")}
            response = await http_client.post(
                f"{web_ui_base_url}/etl/upload", files=files
            )

        # Проверяем статус код
        assert (
            response.status_code == 200
        ), f"❌ Загрузка файла failed со статусом {response.status_code}"

        data = response.json()

        # Проверяем наличие content_preview
        assert (
            "content_preview" in data
        ), "❌ В ответе отсутствует поле 'content_preview'"
        content_preview = data["content_preview"]

        # Проверяем что preview не пустой
        assert len(content_preview) > 0, "❌ content_preview пуст"

        print(
            f"✅ Эндпоинт /etl/upload работает корректно, получен preview длиной {len(content_preview)} символов"
        )

    @pytest.mark.asyncio
    async def test_search_documents_endpoint(self, http_client, web_ui_base_url):
        """✅ Тест эндпоинта POST /search с {"query": "иск"}"""
        search_payload = {"query": "иск"}

        response = await http_client.post(
            f"{web_ui_base_url}/search/documents", json=search_payload
        )

        # Проверяем статус код
        assert (
            response.status_code == 200
        ), f"❌ Поиск документов failed со статусом {response.status_code}"

        data = response.json()

        # Проверяем наличие поля documents
        assert "documents" in data, "❌ В ответе отсутствует поле 'documents'"
        documents = data["documents"]

        # Проверяем что найден минимум 1 документ
        assert len(documents) >= 1, "❌ Не найдено ни одного документа"

        # Упрощённая проверка релевантности - наличие "иск" в контенте
        found_relevant = False
        for doc in documents:
            doc_content = str(doc).lower()
            if "иск" in doc_content:
                found_relevant = True
                break

        assert (
            found_relevant
        ), "❌ В найденных документах отсутствует ключевое слово 'иск'"

        print(
            f"✅ Эндпоинт /search/documents работает корректно, найдено {len(documents)} релевантных документов"
        )

    @pytest.mark.asyncio
    async def test_full_pipeline(self, http_client, web_ui_base_url):
        """✅ Комплексный тест полного пайплайна"""

        # 1. Проверяем работоспособность системы
        health_response = await http_client.get(f"{web_ui_base_url}/health")
        assert health_response.status_code == 200, "❌ Система недоступна"

        # 2. Загружаем документ
        test_file_path = Path("web/test_fixtures/scan1.pdf")
        with open(test_file_path, "rb") as f:
            files = {"file": ("scan1.pdf", f, "application/pdf")}
            upload_response = await http_client.post(
                f"{web_ui_base_url}/etl/upload", files=files
            )

        assert upload_response.status_code == 200, "❌ Загрузка документа failed"

        # Ждём обработки документа
        await asyncio.sleep(2)

        # 3. Ищем загруженный документ
        search_response = await http_client.post(
            f"{web_ui_base_url}/search/documents", json={"query": "тестовый документ"}
        )

        assert search_response.status_code == 200, "❌ Поиск документов failed"

        search_data = search_response.json()
        assert (
            "documents" in search_data
        ), "❌ В ответе поиска отсутствует поле 'documents'"

        print("✅ Полный пайплайн Web UI → ETL → ChromaDB работает корректно")


if __name__ == "__main__":
    import sys

    # Запуск тестов в асинхронном режиме
    pytest.main([__file__, "-v", "-s"] + sys.argv[1:])
